import json
import logging
import pprint
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import requests

import warehub
from warehub.arguments import AddArgs
from warehub.arguments import Arguments
from warehub.arguments import GenerateArgs
from warehub.arguments import YankArgs
from warehub.config import Config
from warehub.database import Database
from warehub.generate import generate_homepage
from warehub.generate import generate_json_pages
from warehub.generate import generate_project_pages
from warehub.generate import generate_simple_pages
from warehub.model import Directory
from warehub.package import Package
from warehub.package import add_package
from warehub.utils import delete_path
from warehub.utils import file_size_str
from warehub.utils import parse_url

logger = logging.getLogger(warehub.__title__)


def init(args: List[str]):
    """Execute the ``init`` command.

    :param args:
        The command-line arguments.
    """
    generic_args: Arguments = Arguments.from_args(args)

    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.DEBUG if generic_args.verbose else logging.WARNING)

    logger.info(pprint.pformat(generic_args))

    if not generic_args.config.exists():
        logger.info("Generating Default Config")
        generic_args.config.parent.mkdir(parents=True, exist_ok=True)
        generic_args.config.write_text(json.dumps(asdict(Config()), indent=4))

    logger.debug("Generating Database File")
    Database.file(Config.path / Config.database)
    Database.commit()

    logger.debug("Generating File Structure")
    for directory in Directory.LIST:
        (Config.path / directory).mkdir(parents=True, exist_ok=True)


# TODO - This should be renamed to github and add should be for specific file urls
def add(args: List[str]):
    """Execute the ``add`` command.

    :param args:
        The command-line arguments.
    """
    add_args: AddArgs = AddArgs.from_args(args)

    setup(add_args)

    return add_impl(add_args)


def generate(args: List[str]):
    """Execute the ``generate`` command.

    :param args:
        The command-line arguments.
    """
    generate_args: GenerateArgs = GenerateArgs.from_args(args)

    setup(generate_args)

    return generate_impl(generate_args)


def yank(args: List[str]):
    """Execute the ``yank`` command.

    :param args:
        The command-line arguments.
    """
    yank_args: YankArgs = YankArgs.from_args(args)

    setup(yank_args)

    return yank_impl(yank_args)


def setup(args: Arguments) -> None:
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)

    logger.info(pprint.pformat(args))

    Config.load(args.config)

    Database.file(Config.path / Config.database)

    for directory in Directory.LIST:
        (Config.path / directory).mkdir(parents=True, exist_ok=True)


def add_impl(args: AddArgs):
    kwargs: Dict[str, Any] = {}
    if args.token is not None:
        kwargs["headers"] = {"Authorization": "token " + str(args.token)}
        logger.debug("Token Provided")
    elif args.username is not None or args.password is not None:
        kwargs["auth"] = (args.username or "", args.password or "")
        logger.debug("Username and Password provided")

    file_urls: List[Tuple[str, str]] = []
    for repo_path in args.repositories:
        repo_url = parse_url(args.domain + f"repos/{repo_path}/releases")
        logger.info(f"Getting Releases from: {repo_url}")
        response = requests.get(repo_url, **kwargs)
        releases_obj = response.json()
        logger.debug(f"Response Code: {response.status_code}")
        if response.status_code != requests.codes.ok:
            logger.warning(
                f"Could not get information on release for "
                f"'{repo_url}': {releases_obj['message']}"
            )
            continue
        for info in releases_obj:
            for asset in info["assets"]:
                file_urls.append((asset["name"], asset["url"]))
    if len(file_urls) == 0:
        logger.info("No Files to Download")
        return

    logger.info(f"Found {len(file_urls)} files")
    with tempfile.TemporaryDirectory() as temp:
        temp_dir = Path(temp)

        downloaded_files: List[Path] = []
        for file_name, file_url in file_urls:
            headers = kwargs.setdefault("headers", {})
            headers.update({"Accept": "application/octet-stream"})
            download = requests.get(file_url, **kwargs)
            logger.debug(f"Response Code: {download.status_code}")
            if download.status_code != requests.codes.ok:
                logger.warning(
                    f"Could not download '{file_url}': " f"{download.status_code}"
                )
                continue

            file = temp_dir / file_name
            file.write_bytes(download.content)

            logger.info(f"Downloaded File: {file_url}\n  to: {file.absolute()}")

            downloaded_files.append(file)

        signatures: Dict[str, Path] = {
            f.name: f for f in downloaded_files if f.suffix == ".asc"
        }
        logger.debug("Signature Files:\n" + pprint.pformat(signatures))

        added: Set[str] = set()
        for file in downloaded_files:
            try:
                if file.suffix != ".asc":
                    package = Package(file, None)

                    if (signed_name := package.signed_file.name) in signatures:
                        package.gpg_signature = signatures[signed_name]

                    logger.debug(
                        f"Package created for file: '{package.file.name}' "
                        f"({file_size_str(package.file)})"
                    )
                    if package.gpg_signature:
                        logger.debug(f"\tSigned with {package.signed_file}")

                    add_package(package)

                    added.add(Config.url + f"simple/{package.name}/{package.version}/")

            except Exception as e:
                logger.exception(
                    f"Exception found when processing file: {file.name}", exc_info=e
                )

        if len(added) > 0:
            if not args.no_generate:
                generate_args: GenerateArgs = GenerateArgs(args.verbose, args.config)

                logger.info(pprint.pformat(generate_args))

                generate_impl(generate_args)

            logger.info("View new Packages at:")
            for url in added:
                logger.info(f"\t{url}")


def generate_impl(args: GenerateArgs):
    logger.debug("Deleting Existing Files")
    for directory in [Directory.PROJECT, Directory.SIMPLE, Directory.PYPI]:
        for child in (Config.path / directory).glob("*"):
            delete_path(child)

    generate_homepage()

    generate_project_pages()

    generate_simple_pages()

    generate_json_pages()


def yank_impl(args: YankArgs):
    pass
