import re
from dataclasses import dataclass, field
from datetime import datetime
from importlib.resources import path, read_text
from typing import Final, Optional

import packaging.utils

import warehub
from warehub.database import Table

__all__ = [
    "Directory",
    "Template",
    "Project",
    "Release",
    "File",
    "FileName",
]


class Directory:
    FILES: Final[str] = "files"
    PROJECT: Final[str] = "project"
    SIMPLE: Final[str] = "simple"
    PYPI: Final[str] = "pypi"

    LIST: Final[set[str]] = {FILES, PROJECT, SIMPLE, PYPI}


class Template:
    # STYLE: Final[str] = read_text(warehub.__title__, "style.css")
    # HOMEPAGE: Final[str] = read_text(warehub.__title__, "homepage.html")
    with path(warehub.__title__, "templates") as path:
        HOMEPAGE: Final[str] = (path / "homepage.html").read_text()
        RELEASE: Final[str] = (path / "release.html").read_text()
        SIMPLE: Final[str] = (path / "simple.html").read_text()
        STYLE: Final[str] = (path / "style.css").read_text()


@dataclass
class Project(Table):
    name: str
    created: datetime = field(default_factory=datetime.now)
    documentation: Optional[str] = None
    total_size: int = 0

    def __repr__(self) -> str:
        return f"Project(name={self.name}, created={self.created})"

    @property
    def normalized_name(self):
        return packaging.utils.canonicalize_name(self.name)


@dataclass
class Release(Table):
    project_id: int
    version: str
    created: datetime = field(default_factory=datetime.now)
    author: Optional[str] = None
    author_email: Optional[str] = None
    maintainer: Optional[str] = None
    maintainer_email: Optional[str] = None
    summary: Optional[str] = None
    description: dict[str, str] = field(default_factory=dict)
    keywords: Optional[str] = None
    classifiers: list[str] = field(default_factory=list)
    license: Optional[str] = None
    platform: Optional[str] = None
    home_page: Optional[str] = None
    download_url: Optional[str] = None
    requires_python: Optional[str] = None
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    project_urls: list[str] = field(default_factory=list)
    uploader: Optional[str] = None  # User that created the issue
    uploaded_via: Optional[str] = None
    yanked: bool = False
    yanked_reason: Optional[str] = None

    @property
    def is_pre_release(self):
        return re.match(rf"(a|b|rc)(0|[1-9][0-9]*)", self.version) is not None

    @property
    def urls(self):
        _urls = {}

        if self.home_page:
            _urls["Homepage"] = self.home_page
        if self.download_url:
            _urls["Download"] = self.download_url

        for url_spec in self.project_urls:
            name, _, url = url_spec.partition(",")
            name = name.strip()
            url = url.strip()
            if name and url:
                _urls[name] = url

        return _urls

    # TODO
    # @property
    # def github_repo_info_url(self):
    #     for url in self.urls.values():
    #         parsed = urlparse(url)
    #         segments = parsed.path.strip("/").split("/")
    #         if parsed.netloc in {"github.com", "www.github.com"} and len(segments) >= 2:
    #             user_name, repo_name = segments[:2]
    #             return f"https://api.github.com/repos/{user_name}/{repo_name}"

    @property
    def has_meta(self):
        return any(
            (
                self.license,
                self.keywords,
                self.author,
                self.author_email,
                self.maintainer,
                self.maintainer_email,
                self.requires_python,
            )
        )


@dataclass
class File(Table):
    release_id: int
    name: str
    python_version: Optional[str] = None
    package_type: Optional[str] = None
    comment_text: Optional[str] = None
    size: int = -1
    has_signature: bool = False
    md5_digest: Optional[str] = None
    sha256_digest: Optional[str] = None
    blake2_256_digest: Optional[str] = None
    upload_time: datetime = field(default_factory=datetime.now)
    uploaded_via: Optional[str] = None

    @property
    def pgp_name(self):
        return self.name + ".asc"


@dataclass
class FileName(Table):
    name: str
