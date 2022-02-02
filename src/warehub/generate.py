import cgi
import json
import logging
import pprint
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, List, Optional, cast

import readme_renderer.markdown
import readme_renderer.rst

import warehub
from warehub.config import Config
from warehub.database import Database
from warehub.model import Directory
from warehub.model import File
from warehub.model import Project
from warehub.model import Release
from warehub.model import Template

logger = logging.getLogger(warehub.__name__)


def generate_homepage():
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
            f'\n{indent}<a class="card" href="{Config.url}{Directory.PROJECT}/'
            f'{project.name}/">'
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


def generate_project_pages():
    logger.info("Generating Project Release Pages")

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
            meta += f'\n{indent}<p class="elem"><strong>{name}: </strong>{string}</p>'

    classifiers: DefaultDict[str, List[str]] = defaultdict(list)
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
                "",
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
                "",
                f'{indent}<a class="card" href="{Config.url}{Directory.PROJECT}/'
                f'{project.name}/{r.version}/">',
                f'{indent}    <span class="version">{r.version}</span>',
                f"{indent}</a>",
            ]
        )

    files = ""
    for f in Database.get(File, where=File.release_id == release.id):
        indent = " " * 16
        files += "\n".join(
            [
                "",
                f'{indent}<a class="card" href="{Config.url}{Directory.FILES}/'
                f'{f.name}">',
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


def generate_simple_pages():
    logger.info("Generating Simple Pages")

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
                    f_list += (
                        f'\n    <a href="{Config.url}{Directory.FILES}/'
                        f'{file.name}">{file.name}</a><br/>'
                    )

        project_dir = Config.path / Directory.SIMPLE / project.name
        project_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Generating Simple File list for {project}")
        template = generate_simple_page(f_list)

        project_file = project_dir / "index.html"
        project_file.write_text(template)

        project_list += (
            f'\n    <a class="card" href="{project.name}/">{project.name}</a><br/>'
        )
    logger.info("Generating Simple Project List")
    template = generate_simple_page(project_list)
    landing = Config.path / Directory.SIMPLE / "index.html"
    landing.write_text(template)


def generate_simple_page(link_list: str) -> str:
    template = Template.SIMPLE

    for string, value in [
        ("%%WAREHUB_VERSION%%", warehub.__version__),
        ("%%TITLE%%", Config.title),
        ("%%IMAGE%%", Config.image_url),
        ("%%LIST%%", link_list),
    ]:
        template = cast(str, template.replace(string, value))
    return template


def generate_json_pages():
    logger.info("Generating Json Pages")

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

                generate_json_page(project_dir / release.version, project, release)

        if latest is not None:
            generate_json_page(project_dir, project, latest)


def generate_json_page(path: Path, project: Project, release: Release):
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
                "upload_time_iso_8601": f.upload_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
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
                    "package_url": f"{Config.url}{Directory.PROJECT}/"
                    f"{project.name}",
                    "project_url": f"{Config.url}{Directory.PROJECT}/"
                    f"{project.name}",
                    "project_urls": release.urls,
                    "release_url": f"{Config.url}{Directory.PROJECT}/"
                    f"{project.name}/{release.version}",
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
