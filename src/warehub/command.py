import logging
import pprint
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

import requests

import warehub
from warehub.arguments import AddArgs, Arguments, GenerateArgs, YankArgs
from warehub.config import Config
from warehub.database import Database
from warehub.model import Directories
from warehub.package import Package, add_package
from warehub.utils import file_size_str, parse_url

__all__ = [
    "add",
    "generate",
    "yank",
]

logger = logging.getLogger(warehub.__title__)


def add(args: List[str]):
    """Execute the ``add`` command.
    :param args:
        The command-line arguments.
    """
    return add_impl(AddArgs.from_args(args))


def generate(args: List[str]):
    """Execute the ``generate`` command.
    :param args:
        The command-line arguments.
    """
    return generate_impl(GenerateArgs.from_args(args))


def yank(args: List[str]):
    """Execute the ``yank`` command.
    :param args:
        The command-line arguments.
    """
    return yank_impl(YankArgs.from_args(args))


def setup(args: Arguments) -> None:
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.DEBUG if args.verbose else logging.WARNING)

    logger.info(pprint.pformat(args))

    Config.load(args.config)

    Database.file(Config.path / Config.database)

    for directory in Directories.LIST:
        (Config.path / directory).mkdir(parents=True, exist_ok=True)


def add_impl(args: AddArgs):
    setup(args)

    auth: Optional[tuple[Optional[str], Optional[str]]] = (
        (args.username or "", args.password or "")
        if args.username or args.password
        else None
    )
    if auth is not None:
        logger.debug("Authentication provided")

    file_urls: list[str] = []
    for repo_path in args.repositories:
        repo_url = parse_url(args.domain + f"repos/{repo_path}/releases")
        logger.info(f"Getting Releases from: {repo_url}")
        response = requests.get(repo_url, auth=auth)
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
                file_urls.append(asset["browser_download_url"])
    if len(file_urls) == 0:
        logger.info("No Files to Download")
        return

    logger.info(f"Found {len(file_urls)} files")
    with tempfile.TemporaryDirectory() as temp:
        temp_dir = Path(temp)

        downloaded_files: list[Path] = []
        for file_url in file_urls:
            download = requests.get(file_url, auth=auth)
            logger.debug(f"Response Code: {download.status_code}")
            if download.status_code != requests.codes.ok:
                logger.warning(
                    f"Could not download '{file_url}': " f"{download.status_code}"
                )
                continue

            file = temp_dir / file_url.split("/")[-1]
            file.write_bytes(download.content)

            logger.info(f"Downloaded File: {file_url}\n  to: {file.absolute()}")

            downloaded_files.append(file)

        signatures: dict[str, Path] = {
            f.name: f for f in downloaded_files if f.suffix == ".asc"
        }
        logger.debug(f"Signature Files:\n" + pprint.pformat(signatures))

        added: set[str] = set()
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
            logger.info(f"View new")


def generate_impl(args: GenerateArgs):
    setup(args)


def yank_impl(args: YankArgs):
    setup(args)
