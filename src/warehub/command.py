import cgi
import json
import logging
import pprint
import sys
import tempfile
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, DefaultDict, List, Optional

import readme_renderer.markdown
import readme_renderer.rst
import requests

import warehub
from warehub.arguments import AddArgs, Arguments, GenerateArgs, YankArgs
from warehub.config import Config
from warehub.database import Database
from warehub.model import Directory, File, Project, Release, Template
from warehub.package import Package, add_package
from warehub.utils import delete_path, file_size_str, parse_url

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
    kwargs: dict[str, Any] = {}
    if args.token is not None:
        kwargs["headers"] = {"Authorization": "token " + str(args.token)}
        logger.debug("Token Provided")
    elif args.username is not None or args.password is not None:
        kwargs["auth"] = (args.username or "", args.password or "")
        logger.debug("Username and Password provided")

    file_urls: list[tuple[str, str]] = []
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

        downloaded_files: list[Path] = []
        for file_name, file_url in file_urls:
            headers = kwargs.setdefault('headers', {})
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
            if not args.no_generate:
                generate_args: GenerateArgs = GenerateArgs(args.verbose, args.config)

                logger.info(pprint.pformat(generate_args))

                generate_impl(generate_args)

            logger.info(f"View new Packages at:")
            for url in added:
                logger.info(f"\t{url}")


def generate_impl(args: GenerateArgs):
    logger.debug("Deleting Existing Files")
    for directory in [Directory.PROJECT, Directory.SIMPLE, Directory.PYPI]:
        for child in (Config.path / directory).glob("*"):
            delete_path(child)

    logger.info("Generating Homepage")
    projects_listing = ""
    for project in Database.get(Project):
        releases = Database.get(Release, where=Release.project_id == project.id)

        if len(releases) < 1:
            # This should never happen because a project is always created
            # with at least one release, but you never know...
            logger.warning(f"Projects does not have any release: {project}")
            continue

        latest = releases[0]
        for release in releases:
            if not release.yanked and release.version > latest.version:
                latest = release

        indent = " " * 4
        projects_listing += (
            f'\n{indent}<a class="card" href="{Config.url}{Directory.PROJECT}/{project.name}/">'
            f'\n{indent}    {project.name}<span class="version">{latest.version}</span>'
            f'\n{indent}    <span class="description">{latest.summary}</span>'
            f"\n{indent}</a>"
        )

    homepage_template = Template.HOMEPAGE

    for string, value in [
        ("%%WAREHUB_VERSION%%", warehub.__version__),
        ("%%STYLE%%", "".join("\n        " + s for s in Template.STYLE.splitlines())),
        ("%%URL%%", Config.url),
        ("%%TITLE%%", Config.title),
        ("%%DESCRIPTION%%", Config.description),
        ("%%IMAGE%%", Config.image_url),
        ("%%PACKAGES%%", projects_listing),
    ]:
        homepage_template = homepage_template.replace(string, value)

    homepage = Config.path / "index.html"
    homepage.write_text(homepage_template)

    logger.info("Generating Project Release Pages")

    def generate_release_page(
        path: Path, project: Project, release: Release, show_version: bool = False
    ):
        renderers = {
            "text/plain": None,
            "text/x-rst": readme_renderer.rst,
            "text/markdown": readme_renderer.markdown,
        }

        links = ""
        for name, url in release.urls.items():
            indent = " " * 20
            links += f'\n{indent}<li><a href="{url}" rel="nofollow">{name}</a></li>'

        meta = ""
        for name, check, string in {
            ("License", release.license, release.license),
            (
                "Author",
                release.author,
                f'<a href="mailto:{release.author_email}">{release.author}</a>',
            ),
            (
                "Maintainer",
                release.maintainer,
                f'<a href="mailto:{release.maintainer_email}">{release.maintainer}</a>',
            ),
            ("Requires", release.requires_python, release.requires_python),
            ("Platform", release.platform, release.platform),
        }:
            if check is not None:
                indent = " " * 16
                meta += (
                    f'\n{indent}<p class="elem"><strong>{name}: </strong>{string}</p>'
                )

        classifiers: DefaultDict[str, list[str]] = defaultdict(list)
        for classifier in release.classifiers:
            group, tag = classifier.split(" :: ", 1)
            classifiers[group].append(tag)

        classifiers_str = ""
        for group, tags in classifiers.items():
            tags_str = ""
            for tag in sorted(tags):
                indent = " " * 28
                tags_str += f"\n{indent}<li>{tag}</li>"
            indent = " " * 20
            classifiers_str += "\n".join(
                [
                    f"",
                    f"{indent}<li>",
                    f"{indent}    <strong>{group}</strong>",
                    f"{indent}    <ul>{tags_str}",
                    f"{indent}    </ul>",
                    f"{indent}</li>",
                ]
            )

        description = release.description["raw"]
        content_type, params = cgi.parse_header(release.description["content_type"])
        renderer = renderers.get(content_type, readme_renderer.rst)

        if description in {None, "UNKNOWN\n\n\n"}:
            description = ""
        elif renderer:
            description = renderer.render(description, **params) or ""

        releases = ""
        for r in Database.get(Release, where=Release.project_id == project.id):
            indent = " " * 16
            # TODO - Pre-Release?, Yanked?, etc
            releases += "\n".join(
                [
                    f"",
                    f'{indent}<a class="card" href="{Config.url}{Directory.PROJECT}/{project.name}/{r.version}/">',
                    f'{indent}    <span class="version">{r.version}</span>',
                    f"{indent}</a>",
                ]
            )

        files = ""
        for f in Database.get(File, where=File.release_id == release.id):
            indent = " " * 16
            files += "\n".join(
                [
                    f"",
                    f'{indent}<a class="card" href="{Config.url}{Directory.FILES}/{f.name}">',
                    f"{indent}    {f.name}",
                    f"{indent}</a>",
                ]
            )

        template = Template.RELEASE

        for string, value in [
            ("%%WAREHUB_VERSION%%", warehub.__version__),
            (
                "%%STYLE%%",
                "".join("\n        " + s for s in Template.STYLE.splitlines()),
            ),
            ("%%URL%%", Config.url),
            ("%%TITLE%%", Config.title),
            ("%%IMAGE%%", Config.image_url),
            ("%%NAME%%", project.name),
            ("%%VERSION%%", release.version),
            ("%%PIP_VERSION%%", f"=={release.version}" if show_version else ""),
            ("%%SUMMARY%%", release.summary or ""),
            ("%%LINKS%%", links),
            ("%%META%%", meta),
            ("%%CLASSIFIERS%%", classifiers_str),
            ("%%DESCRIPTION%%", description),
            ("%%RELEASES%%", releases),
            ("%%FILES%%", files),
        ]:
            template = template.replace(string, value)

        file = path / "index.html"
        file.write_text(template)

    for project in Database.get(Project):
        releases = Database.get(Release, where=Release.project_id == project.id)

        if len(releases) < 1:
            # This should never happen because a project is always created
            # with at least one release, but you never know...
            logger.warning("Projects does not have any release:", project)

        project_dir = Config.path / Directory.PROJECT / project.name
        project_dir.mkdir(parents=True, exist_ok=True)

        latest = releases[0]
        for release in releases:
            if release.version > latest.version:
                latest = release

            release_dir = project_dir / release.version
            release_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Generating Release Page for:")
            logger.info(pprint.pformat(release))
            generate_release_page(release_dir, project, release, True)

        logger.info("Generating Project Page for:")
        logger.info(pprint.pformat(project))
        generate_release_page(project_dir, project, latest)

    logger.info("Generating Simple Pages")

    def create_simple(link_list: str) -> str:
        template = Template.SIMPLE

        for string, value in [
            ("%%WAREHUB_VERSION%%", warehub.__version__),
            ("%%TITLE%%", Config.title),
            ("%%IMAGE%%", Config.image_url),
            ("%%LIST%%", link_list),
        ]:
            template = template.replace(string, value)
        return template

    project_list = ""
    for project in Database.get(Project):
        releases = Database.get(Release, where=Release.project_id == project.id)

        if len(releases) < 1:
            # This should never happen because a project is always created
            # with at least one release, but you never know...
            logger.warning("Projects does not have any release:", project)
            continue

        f_list = ""
        for release in releases:
            if not release.yanked:
                for file in Database.get(File, where=File.release_id == release.id):
                    f_list += f'\n    <a href="{Config.url}{Directory.FILES}/{file.name}">{file.name}</a><br/>'

        project_dir = Config.path / Directory.SIMPLE / project.name
        project_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Generating Simple File list for {project}")
        template = create_simple(f_list)

        project_file = project_dir / "index.html"
        project_file.write_text(template)

        project_list += (
            f'\n    <a class="card" href="{project.name}/">{project.name}</a><br/>'
        )

    logger.info("Generating Simple Project List")
    template = create_simple(project_list)

    landing = Config.path / Directory.SIMPLE / "index.html"
    landing.write_text(template)

    logger.info("Generating Json Pages")

    def create_json(path: Path, project: Project, release: Release):
        dir = path / "json"
        dir.mkdir(parents=True, exist_ok=True)

        releases = {}
        for r in Database.get(Release, where=Release.project_id == project.id):
            releases[r.version] = [
                {
                    "filename": f.name,
                    "python_version": f.python_version,
                    "packagetype": f.package_type,
                    "comment_text": f.comment_text,
                    "size": f.size,
                    "has_sig": f.has_signature,
                    "md5_digest": f.md5_digest,
                    "digests": {
                        "md5": f.md5_digest,
                        "sha256": f.sha256_digest,
                        "blake2_256": f.blake2_256_digest,
                    },
                    "downloads": (-1),
                    "upload_time": f.upload_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "upload_time_iso_8601": f.upload_time.strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    ),
                    "url": f"{Config.url}{Directory.FILES}/{f.name}",
                    "requires_python": r.requires_python if r.requires_python else None,
                    "yanked": r.yanked,
                    "yanked_reason": r.yanked_reason or None,
                }
                for f in Database.get(File, where=File.release_id == r.id)
            ]

        file = dir / "index.json"
        file.write_text(
            json.dumps(
                {
                    "info": {
                        "name": project.name,
                        "version": release.version,
                        "summary": release.summary,
                        "description_content_type": release.description["content_type"],
                        "description": release.description["raw"],
                        "keywords": release.keywords,
                        "license": release.license,
                        "classifiers": release.classifiers,
                        "author": release.author,
                        "author_email": release.author_email,
                        "maintainer": release.maintainer,
                        "maintainer_email": release.maintainer_email,
                        "requires_python": release.requires_python,
                        "platform": release.platform,
                        "downloads": {
                            "last_day": -1,
                            "last_week": -1,
                            "last_month": -1,
                        },
                        "package_url": f"{Config.url}{Directory.PROJECT}/{project.name}",
                        "project_url": f"{Config.url}{Directory.PROJECT}/{project.name}",
                        "project_urls": release.urls,
                        "release_url": f"{Config.url}{Directory.PROJECT}/{project.name}/{release.version}",
                        "requires_dist": release.dependencies["requires_dist"],
                        "docs_url": None,
                        "bugtrack_url": None,
                        "home_page": release.home_page,
                        "download_url": release.download_url,
                        "yanked": release.yanked,
                        "yanked_reason": release.yanked_reason or None,
                    },
                    "urls": releases[release.version],
                    "releases": releases,
                    "vulnerabilities": [],
                    "last_serial": (-1),
                },
                indent=4,
            )
        )

    for project in Database.get(Project):
        releases = Database.get(Release, where=Release.project_id == project.id)

        if len(releases) < 1:
            # This should never happen because a project is always created
            # with at least one release, but you never know...
            logger.warning("Projects does not have any release:", project)
            continue

        project_dir = Config.path / Directory.PYPI / project.name
        project_dir.mkdir(parents=True, exist_ok=True)

        latest: Optional[Release] = None
        for release in releases:
            if not release.yanked:
                if latest is None or release.version > latest.version:
                    latest = release

                create_json(project_dir / release.version, project, release)

        if latest is not None:
            create_json(project_dir, project, latest)


def yank_impl(args: YankArgs):
    pass
