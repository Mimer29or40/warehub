from __future__ import annotations

import functools
import json
import logging
import pprint
from dataclasses import Field
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from pathlib import Path
from typing import Dict, Optional

import warehub
from warehub.utils import parse_url

logger = logging.getLogger(warehub.__title__)


def _raise(field: Field, message: str) -> None:
    attrs = {a: getattr(field, a) for a in field.__slots__}
    raise ValueError(message.format(**attrs))


def _warn(field: Field, message: str) -> None:
    attrs = {a: getattr(field, a) for a in field.__slots__}
    logger.warning(message.format(**attrs))


@dataclass(frozen=True)
class Config:
    path: Path = field(
        default=".",
        metadata={
            "on_missing": functools.partial(
                _raise,
                message="Config must specify '{name}'. Default is '{default}'",
            ),
            "convert": (lambda string: Path(string).resolve()),
        },
    )
    database: str = field(
        default="data.json",
        metadata={
            "on_missing": functools.partial(
                _raise,
                message="Config must specify '{name}'. Default is '{default}'",
            ),
        },
    )
    url: str = field(
        default="",
        metadata={
            "on_missing": functools.partial(
                _raise,
                message="Config must specify '{name}'. Usually "
                "'https://<user>.github.io/<repo_name/'",
            ),
            "convert": parse_url,
        },
    )
    title: Optional[str] = field(
        default="Personal Python Package Index",
        metadata={
            "on_missing": functools.partial(
                _warn,
                message="Config does not specify '{name}'. Using Default: '{default}'",
            ),
        },
    )
    description: Optional[str] = field(
        default="Welcome to your private Python package index!",
        metadata={
            "on_missing": functools.partial(
                _warn,
                message="Config does not specify '{name}'. Using Default: '{default}'",
            ),
        },
    )
    image_url: Optional[str] = field(
        default="https://pypi.org/static/images/logo-small.95de8436.svg",
        metadata={
            "on_missing": functools.partial(
                _warn,
                message="Config does not specify '{name}'. Using Default: '{default}'",
            ),
            "convert": parse_url,
        },
    )

    @classmethod
    def load(cls, file: Path):
        if not file.exists():
            logger.info("Generating Default Config")
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(asdict(cls()), indent=4))

        # This may error out if the json is malformed
        loaded: Dict[str, str] = json.loads(file.read_text())

        for cls_field in fields(cls):
            metadata = cls_field.metadata
            if cls_field.name not in loaded or loaded[cls_field.name] == "":
                metadata["on_missing"](cls_field)
                loaded[cls_field.name] = cls_field.default
            if "convert" in metadata:
                loaded[cls_field.name] = metadata["convert"](loaded[cls_field.name])

        if not loaded["url"].endswith("/"):
            loaded["url"] += "/"

        logger.info(pprint.pformat(cls(**loaded)))

        for key, value in loaded.items():
            setattr(cls, key, value)
