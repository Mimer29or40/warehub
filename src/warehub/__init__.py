import importlib.metadata

__all__ = (
    "__metadata_version__",
    "__title__",
    "__version__",
    "__summary__",
    "__author__",
    "__maintainer__",
    "__license__",
    "__url__",
    "__download_url__",
    "__project_urls__",
    "__data_dir__",
)

from pathlib import Path
from typing import Dict, Final, Optional

metadata = importlib.metadata.metadata(__name__)

__metadata_version__: Final[Optional[str]] = metadata.get("metadata-version", None)

__title__: Final[Optional[str]] = metadata.get("name", None)
__version__: Final[Optional[str]] = metadata.get("version", None)
__summary__: Final[Optional[str]] = metadata.get("summary", None)
__author__: Final[Optional[str]] = metadata.get("author", None)
__maintainer__: Final[Optional[str]] = metadata.get("maintainer", __author__)
__license__: Final[Optional[str]] = metadata.get("license", None)
__url__: Final[Optional[str]] = metadata.get("home-page", None)
__download_url__: Final[Optional[str]] = metadata.get("download-url", None)
__project_urls__: Final[Dict[str, str]] = {
    values[0].strip(): values[1].strip()
    for url_str in metadata.get_all("project-url", tuple())
    if (values := url_str.split(","))
}

__copyright__: Final[str] = f"Copyright 2022 {__author__}"

__data_dir__: Final[Path] = Path(__file__).parent.resolve()
