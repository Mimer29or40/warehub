from __future__ import annotations

import functools
import json
import logging
import pprint
from dataclasses import dataclass, field, Field, fields, asdict
from pathlib import Path
from typing import Optional

import warehub

__all__ = [
    'load',
    'config',
]

logger = logging.getLogger(warehub.__title__)


def _raise(field: Field, message: str) -> None:
    raise ValueError(message.format(**vars(field)))


def _warn(field: Field, message: str) -> None:
    logger.warning(message.format(**vars(field)))


@dataclass(frozen=True)
class Config:
    database: str = field(
        default='./data.json',
        metadata={
            'on_missing': functools.partial(
                _raise,
                message='Config must specify \'{name}\'. Default is \'{default}\'',
            )
        },
    )
    url: str = field(
        default='',
        metadata={
            'on_missing': functools.partial(
                _raise,
                message='Config must specify \'{name}\'. Usually \'https://<user>.github.io/<repo_name/\'',
            ),
        },
    )
    title: Optional[str] = field(
        default='Personal Python Package Index',
        metadata={
            'on_missing': functools.partial(
                _warn,
                message='Config does not specify \'{name}\'. Using Default: \'{default}\'',
            ),
        },
    )
    description: Optional[str] = field(
        default='Welcome to your private Python package index!',
        metadata={
            'on_missing': functools.partial(
                _warn,
                message='Config does not specify \'{name}\'. Using Default: \'{default}\'',
            ),
        },
    )
    image_url: Optional[str] = field(
        default='https://pypi.org/static/images/logo-small.95de8436.svg',
        metadata={
            'on_missing': functools.partial(
                _warn,
                message='Config does not specify \'{name}\'. Using Default: \'{default}\'',
            ),
        },
    )


config: Config


def load(path: str) -> None:
    global config
    
    config_file: Path = Path(path).resolve()
    
    if not config_file.exists():
        logger.info('Generating Default Config')
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps(asdict(Config()), indent=4))
    
    # This may error out if the json is malformed
    loaded: dict[str, str] = json.loads(config_file.read_text())
    
    for field in fields(Config):
        if field.name not in loaded or loaded[field.name] == '':
            field.metadata['on_missing'](field)
            loaded[field.name] = field.default

    config = Config(**loaded)
    
    logger.info(pprint.pformat(config))

