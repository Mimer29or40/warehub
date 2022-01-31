import os
import urllib.parse
from argparse import Action, ArgumentParser, Namespace
from pathlib import Path
from typing import Any, Optional, Sequence, Union


def file_size_str(file_or_size: Union[Path, int]) -> str:
    if isinstance(file_or_size, Path):
        size = file_or_size.stat().st_size
    else:
        size = file_or_size
    suffix = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    i = 0
    while size > 1024 and i < len(suffix) - 1:
        size = size // 1024
        i += 1
    return f"{size} {suffix[i]}"


def delete_path(path: Path) -> None:
    if path.is_dir():
        for child in path.glob("*"):
            delete_path(child)
        path.rmdir()
    else:
        path.unlink(missing_ok=True)


class EnvironmentDefault(Action):
    """Get values from environment variable."""

    def __init__(
        self,
        env: str,
        required: bool = True,
        default: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        default = os.environ.get(env, default)
        self.env = env
        if default:
            required = False
        super().__init__(default=default, required=required, **kwargs)

    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: Union[str, Sequence[Any], None],
        option_string: Optional[str] = None,
    ) -> None:
        setattr(namespace, self.dest, values)


def parse_url(url: str) -> str:
    return urllib.parse.urlparse(url).geturl()
