from __future__ import annotations

import email.utils
import hashlib
import io
import re
import shutil
from cgi import parse_header
from pathlib import Path
from types import NoneType
from typing import Any, Optional, Type, Union, get_args, get_origin

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version
from pkginfo import BDist, SDist, Wheel
from pkginfo.distribution import HEADER_ATTRS
from rfc3986 import uri_reference
from rfc3986.exceptions import ValidationError
from rfc3986.validators import Validator
from trove_classifiers import classifiers, deprecated_classifiers

from warehub.config import Config
from warehub.database import Database
from warehub.exceptions import InvalidDistribution
from warehub.model import Directory, File, FileName, Project, Release
from warehub.utils import file_size_str

ONE_KB = 1024
ONE_MB = ONE_KB * ONE_KB
ONE_GB = ONE_KB * ONE_KB * ONE_KB

MAX_SIG_SIZE = 8 * ONE_KB
MAX_FILE_SIZE = 100 * ONE_MB
MAX_PROJECT_SIZE = 10 * ONE_GB

DIST_TYPES = {
    "bdist_wheel": Wheel,
    "bdist_egg": BDist,
    "sdist": SDist,
}

DIST_EXTENSIONS = {
    ".whl": "bdist_wheel",
    ".egg": "bdist_egg",
    ".tar.bz2": "sdist",
    ".tar.gz": "sdist",
    ".zip": "sdist",
}

DIST_VERSION = {
    "bdist_wheel": re.compile(
        (
            r"^(?P<namever>(?P<name>.+?)(-(?P<ver>\d.+?))?)"
            r"((-(?P<build>\d.*?))?-(?P<pyver>.+?)-(?P<abi>.+?)-(?P<plat>.+?)"
            r"\.whl|\.dist-info)$"
        ),
        re.VERBOSE,
    ),
    "bdist_egg": re.compile(
        (
            r"^(?P<namever>(?P<name>.+?)(-(?P<ver>\d.+?))?)"
            r"((-(?P<build>\d.*?))?-(?P<pyver>.+?)-(?P<abi>.+?)-(?P<plat>.+?)"
            r"\.egg|\.egg-info)$"
        ),
        re.VERBOSE,
    ),
}


def add_package(package: Package) -> None:
    projects = Database.get(Project, where=Project.name == package.name)
    if len(projects) == 0:
        project = Project(
            name=package.name,
        )
        Database.put(Project, project)
    elif len(projects) > 1:
        raise ValueError(f"Multiple Projects found with name '{package.name}'")
    else:
        project = projects[0]

    releases = Database.get(
        Release,
        where=(
            (Release.project_id == project.id) & (Release.version == package.version)
        ),
    )
    if len(releases) == 0:
        release = Release(
            project_id=project.id,
            version=package.version,
            author=package.author,
            author_email=package.author_email,
            maintainer=package.maintainer,
            maintainer_email=package.maintainer_email,
            summary=package.summary,
            description={
                "raw": package.description or "",
                "content_type": package.description_content_type,
            },
            keywords=package.keywords,
            classifiers=package.classifiers,
            license=package.license,
            platform=package.platform,
            home_page=package.home_page,
            download_url=package.download_url,
            requires_python=package.requires_python,
            dependencies={
                "requires": package.requires or [],
                "provides": package.provides or [],
                "obsoletes": package.obsoletes or [],
                "requires_dist": package.requires_dist or [],
                "provides_dist": package.provides_dist or [],
                "obsoletes_dist": package.obsoletes_dist or [],
                "requires_external": package.requires_external or [],
            },
            project_urls=package.project_urls or [],
            # uploader=package.uploader,
            # uploaded_via=package.uploaded_via,
            # yanked=package.yanked,
            # yanked_reason=package.yanked_reason,
        )
        Database.put(Release, release)
    elif len(releases) > 1:
        raise ValueError(f"Multiple Releases found with name '{package.name}'")
    else:
        release = releases[0]

    filenames = Database.get(FileName, where=FileName.name == package.file.name)
    if len(filenames) > 0:
        raise ValueError(f"File already exists with that name: {package.file.name}")
    Database.put(FileName, FileName(package.file.name))

    # TODO - Check for multiple sdist
    # TODO - Check for valid dist file
    # TODO - Check that if it's a binary wheel, it's on a supported platform

    if package.gpg_signature is not None:
        has_signature = True

        filenames = Database.get(
            FileName, where=FileName.name == package.signed_file.name
        )
        if len(filenames) > 0:
            raise ValueError(
                f"File already exists with that name: {package.signed_file.name}"
            )

        Database.put(FileName, FileName(package.signed_file.name))
    else:
        has_signature = False

    file = File(
        release_id=release.id,
        name=package.file.name,
        python_version=package.pyversion,
        package_type=package.filetype,
        comment_text=package.comment,
        size=package.file.stat().st_size,
        has_signature=has_signature,
        md5_digest=package.md5_digest,
        sha256_digest=package.sha256_digest,
        blake2_256_digest=package.blake2_256_digest,
        # uploaded_via=,
    )
    Database.put(File, file)

    file_size = package.file.stat().st_size
    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"File too large. Limit is {file_size_str(MAX_FILE_SIZE)}")
    project.total_size += file_size

    if has_signature:
        file_size = package.signed_file.stat().st_size
        if file_size > MAX_SIG_SIZE:
            raise ValueError(
                f"Signature file too large. Limit is {file_size_str(MAX_SIG_SIZE)}"
            )
        project.total_size += file_size

    if project.total_size > MAX_PROJECT_SIZE:
        raise ValueError(
            f"Project is now too large. Limit is {file_size_str(MAX_PROJECT_SIZE)}"
        )

    shutil.copy(package.file, Config.path / Directory.FILES / package.file.name)
    if has_signature:
        shutil.copy(
            package.signed_file,
            Config.path / Directory.FILES / package.signed_file.name,
        )
    Database.commit()


class Package:
    def __init__(self, file: Path, comment: Optional[str]):
        self.file: Path = file
        self.comment: Optional[str] = comment

        self.signed_file: Path = self.file.with_name(self.file.name + ".asc")
        self.gpg_signature: Optional[Path] = None

        hashes = {
            "md5": hashlib.md5(),
            "sha256": hashlib.sha256(),
            "blake2_256": hashlib.blake2b(digest_size=256 // 8),
        }

        with self.file.open("rb") as fp:
            for content in iter(lambda: fp.read(io.DEFAULT_BUFFER_SIZE), b""):
                for hash in hashes.values():
                    hash.update(content)

        self.md5_digest: str = hashes["md5"].hexdigest().lower()
        self.sha256_digest: str = validate_hash(
            "Use a valid, hex-encoded, SHA256 message digest.",
            hashes["sha256"].hexdigest().lower(),
        )
        self.blake2_256_digest: str = validate_hash(
            "Use a valid, hex-encoded, BLAKE2 message digest.",
            hashes["blake2_256"].hexdigest().lower(),
        )

        self.filetype: str = ""
        for ext, file_type in DIST_EXTENSIONS.items():
            if self.file.name.endswith(ext):
                try:
                    metadata = DIST_TYPES[file_type](self.file)  # Convert to str?
                except EOFError:
                    raise InvalidDistribution(
                        f"Invalid distribution file: '{self.file.name}'"
                    )
                else:
                    self.filetype = file_type
                    break
        else:
            raise InvalidDistribution(
                f"Unknown distribution format: '{self.file.name}'"
            )

        # If pkginfo encounters a metadata version it doesn't support, it may
        # give us back empty metadata. At the very least, we should have a name
        # and version
        if not (metadata.name and metadata.version):
            supported_metadata = list(HEADER_ATTRS)
            raise InvalidDistribution(
                "Invalid distribution metadata. "
                "This version of twine supports Metadata-Version "
                f'{", ".join(supported_metadata[:-1])}, and {supported_metadata[-1]}'
            )

        self.pyversion: Optional[str] = None
        if self.filetype in DIST_VERSION:
            self.pyversion = "any"
            if (m := DIST_VERSION[self.filetype].match(self.file.name)) is not None:
                self.pyversion = m.group("pyver")

        self.metadata_version: str = validate_metadata_version(
            sanitize(str, metadata.metadata_version)
        )
        # version 1.0
        self.name: str = validate_name(
            re.sub("[^A-Za-z0-9.]+", "-", sanitize(str, metadata.name))
        )
        self.version: str = str(Version(sanitize(str, metadata.version)))
        self.author: Optional[str] = sanitize(Optional[str], metadata.author)
        self.author_email: Optional[str] = validate_email(
            sanitize(Optional[str], metadata.author_email)
        )
        self.summary: Optional[str] = validate_summary(
            sanitize(Optional[str], metadata.summary)
        )
        self.description: Optional[str] = sanitize(Optional[str], metadata.description)
        self.keywords: Optional[str] = sanitize(Optional[str], metadata.keywords)
        self.license: Optional[str] = sanitize(Optional[str], metadata.license)
        self.platform: Optional[str] = sanitize(Optional[str], metadata.platforms)
        self.home_page: Optional[str] = validate_uri(
            sanitize(Optional[str], metadata.home_page)
        )
        self.download_url: Optional[str] = validate_uri(
            sanitize(Optional[str], metadata.download_url)
        )
        self.supported_platforms: Optional[str] = sanitize(
            Optional[str], metadata.supported_platforms
        )
        # version 1.1
        self.classifiers: list = validate_classifiers(
            sanitize(list, metadata.classifiers)
        )
        self.requires: Optional[list] = validate_legacy_non_dist(
            sanitize(Optional[list], metadata.requires)
        )
        self.provides: Optional[list] = validate_legacy_non_dist(
            sanitize(Optional[list], metadata.provides)
        )
        self.obsoletes: Optional[list] = validate_legacy_non_dist(
            sanitize(Optional[list], metadata.obsoletes)
        )
        # version 1.2
        self.maintainer: Optional[str] = sanitize(Optional[str], metadata.maintainer)
        self.maintainer_email: Optional[str] = validate_email(
            sanitize(Optional[str], metadata.maintainer_email)
        )
        self.requires_python: Optional[str] = validate_pep440_specifier(
            sanitize(Optional[str], metadata.requires_python)
        )
        self.requires_dist: Optional[list] = validate_legacy_dist(
            sanitize(Optional[list], metadata.requires_dist)
        )
        self.provides_dist: Optional[list] = validate_legacy_dist(
            sanitize(Optional[list], metadata.provides_dist)
        )
        self.obsoletes_dist: Optional[list] = validate_legacy_dist(
            sanitize(Optional[list], metadata.obsoletes_dist)
        )
        self.requires_external: Optional[list] = validate_requires_external(
            sanitize(Optional[list], metadata.requires_external)
        )
        self.project_urls: Optional[list] = validate_project_urls(
            sanitize(Optional[list], metadata.project_urls)
        )
        # version 2.1
        self.description_content_type: Optional[
            str
        ] = validate_description_content_type(
            sanitize(Optional[str], metadata.description_content_type)
        )
        self.provides_extras: Optional[list] = sanitize(
            Optional[list], metadata.provides_extras
        )
        # version 2.2
        self.dynamic: Optional[list] = sanitize(Optional[list], metadata.dynamic)

    def add_gpg_signature(self, signature_file: Path) -> None:
        if self.gpg_signature is not None:
            raise InvalidDistribution("GPG Signature can only be added once")

        self.gpg_signature = signature_file


def validate_hash(message: str, hash: str) -> str:
    if re.match(r"^[A-F0-9]{64}$", hash, re.IGNORECASE) is None:
        raise ValueError(message)
    return hash


def sanitize(type: Type, value: Any) -> Any:
    types = get_args(type)
    optional = get_origin(type) is Union and NoneType in types
    type = types[0] if optional else type

    if isinstance(value, (list, tuple)) and type not in (list, tuple):
        value = value[0] if len(value) > 0 else None

    if value is None:
        if not optional:
            raise ValueError(f"missing required field")
    elif not isinstance(value, type):
        value = type(value)

    if isinstance(value, str):
        if value.strip() == "UNKNOWN":
            value = None
        elif "\x00" in value:
            value = value.replace("\x00", "\\x00")
    return value


def validate_metadata_version(value):
    if value not in ["1.0", "1.1", "1.2", "2.0", "2.1"]:
        raise ValueError("Use a known metadata version.")
    return value


def validate_name(value):
    if (
        re.match(r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$", value, re.IGNORECASE)
        is None
    ):
        raise ValueError(
            "Start and end with a letter or numeral containing "
            "only ASCII numeric and '.', '_' and '-'."
        )
    return value


def validate_email(value):
    if value is None:
        return value
    pattern = re.compile(
        (
            r"([a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|\""
            r"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*\")"
            r"@((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
            r"|\[(?:(?:2(?:5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])\.){3}"
            r"(?:(?:2(?:5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:"
            r"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)])"
        ),
        re.IGNORECASE,
    )

    addresses = email.utils.getaddresses([value])

    for real_name, address in addresses:
        if pattern.match(address) is None:
            raise ValueError("Use a valid email address")
    return value


def validate_summary(value):
    if value is None:
        return value
    if len(value or "") > 512:
        raise ValueError("Summary is too long")
    if re.match(r"^.+$", value) is None:
        raise ValueError("Use a single line only.")
    return value


def validate_description_content_type(value):
    def _raise(message):
        raise ValueError(f"Invalid description content type: {message}")

    content_type, parameters = parse_header(value)
    if content_type not in {"text/plain", "text/x-rst", "text/markdown"}:
        _raise("type/subtype is not valid")

    charset = parameters.get("charset")
    if charset and charset != "UTF-8":
        _raise("Use a valid charset")

    valid_markdown_variants = {"CommonMark", "GFM"}

    variant = parameters.get("variant")
    if (
        content_type == "text/markdown"
        and variant
        and variant not in valid_markdown_variants
    ):
        _raise(
            f'Use a valid variant, expected one of {", ".join(valid_markdown_variants)}'
        )
    return value


def validate_classifiers(value):
    invalid_classifiers = set(value or []) & deprecated_classifiers.keys()
    if invalid_classifiers:
        first_invalid_classifier_name = sorted(invalid_classifiers)[0]
        deprecated_by = deprecated_classifiers[first_invalid_classifier_name]

        if deprecated_by:
            raise ValueError(
                f"Classifier {first_invalid_classifier_name!r} has been "
                "deprecated, use the following classifier(s) instead: "
                f"{deprecated_by}"
            )
        else:
            raise ValueError(
                f"Classifier {first_invalid_classifier_name!r} has been deprecated."
            )

    invalid = sorted(set(value or []) - classifiers)

    if invalid:
        if len(invalid) == 1:
            raise ValueError(f"Classifier {invalid[0]!r} is not a valid classifier.")
        else:
            raise ValueError(f"Classifiers {invalid!r} are not valid classifiers.")
    return value


def validate_uri(value):
    if value is None:
        return value
    if not is_valid_uri(value):
        raise ValueError(f"Invalid URI '{value}'")
    return value


def validate_pep440_specifier(value):
    try:
        SpecifierSet(value)
    except InvalidSpecifier:
        raise ValueError("Invalid specifier in requirement.") from None


def validate_legacy_non_dist(value):
    for datum in value:
        try:
            req = Requirement(datum.replace("_", ""))
        except InvalidRequirement:
            raise ValueError("Invalid requirement: {!r}".format(datum)) from None

        if req.url is not None:
            raise ValueError("Can't direct dependency: {!r}".format(datum))

        if any(
            not identifier.isalnum() or identifier[0].isdigit()
            for identifier in req.name.split(".")
        ):
            raise ValueError("Use a valid Python identifier.")
    return value


def validate_legacy_dist(value):
    for datum in value:
        try:
            req = Requirement(datum)
        except InvalidRequirement:
            raise ValueError("Invalid requirement: {!r}.".format(datum)) from None

        if req.url is not None:
            raise ValueError("Can't have direct dependency: {!r}".format(datum))
    return value


def validate_requires_external(value):
    for datum in value:
        parsed = re.search(r"^(?P<name>\S+)(?: \((?P<specifier>\S+)\))?$", datum)
        if parsed is None:
            raise ValueError("Invalid requirement.")
        name, specifier = parsed.groupdict()["name"], parsed.groupdict()["specifier"]

        if specifier is not None:
            validate_pep440_specifier(specifier)
    return value


def validate_project_urls(value):
    for datum in value:
        try:
            label, url = datum.split(", ", 1)
        except ValueError:
            raise ValueError("Use both a label and an URL.") from None

        if not label:
            raise ValueError("Use a label.")

        if len(label) > 32:
            raise ValueError("Use 32 characters or less.")

        if not url:
            raise ValueError("Use an URL.")

        if not is_valid_uri(str(url), require_authority=False):
            raise ValueError("Use valid URL.")
    return value


def is_valid_uri(
    uri,
    require_scheme: bool = True,
    allowed_schemes: list[str] = None,
    require_authority: bool = True,
):
    if allowed_schemes is None:
        allowed_schemes = ["http", "https"]

    uri = uri_reference(uri).normalize()
    validator = Validator().allow_schemes(*allowed_schemes)
    if require_scheme:
        validator.require_presence_of("scheme")
    if require_authority:
        validator.require_presence_of("host")

    validator.check_validity_of("scheme", "host", "port", "path", "query")

    try:
        validator.validate(uri)
    except ValidationError:
        return False

    return True
