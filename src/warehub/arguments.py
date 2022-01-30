from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import List, Optional, Type, TypeVar

import warehub
from warehub.utils import EnvironmentDefault, parse_url

__all__ = [
    "Arguments",
    "AddArgs",
    "GenerateArgs",
    "YankArgs",
]

T = TypeVar("T")


@dataclass(frozen=True)
class Arguments:
    verbose: bool = field(
        metadata={
            "name_or_flags": ["-v", "--verbose"],
            "default": False,
            "required": False,
            "action": "store_true",
            "help": "show verbose output",
        }
    )
    config: Path = field(
        metadata={
            "name_or_flags": ["-c", "--config"],
            "default": "./config.json",
            "required": False,
            "help": "The path to the config file. [default: ./config.json]",
            "convert": (lambda string: Path(string).resolve()),
        }
    )

    @classmethod
    def from_args(cls: Type[T], args: list[str]) -> T:
        """Generate the Settings from parsed arguments."""

        parser = ArgumentParser(prog=f"{warehub.__title__} {cls.__name__.lower()}")

        for field in fields(cls):
            metadata = dict(field.metadata)
            metadata.pop("convert", None)
            name_or_flags = tuple(
                metadata.pop("name_or_flags") if "name_or_flags" in metadata else []
            )
            parser.add_argument(*name_or_flags, **metadata)

        parsed = vars(parser.parse_args(args))

        for field in fields(cls):
            metadata = field.metadata
            if "convert" in metadata and (value := parsed[field.name]) is not None:
                parsed[field.name] = metadata["convert"](value)

        return cls(**parsed)


@dataclass(frozen=True)
class AddArgs(Arguments):
    username: Optional[str] = field(
        metadata={
            "name_or_flags": ["-u", "--username"],
            "action": EnvironmentDefault,
            "env": "WAREHUB_USERNAME",
            "required": False,
            "help": "The username to authenticate to the repository "
            "(package index) as. (Can also be set via "
            "%(env)s environment variable.) "
            "[default: env.WAREHUB_USERNAME]",
        }
    )
    password: Optional[str] = field(
        metadata={
            "name_or_flags": ["-p", "--password"],
            "action": EnvironmentDefault,
            "env": "WAREHUB_PASSWORD",
            "required": False,
            "help": "The password to authenticate to the repository "
            "(package index) with. (Can also be set via "
            "%(env)s environment variable.) "
            "[default: env.WAREHUB_PASSWORD]",
        }
    )
    domain: str = field(
        metadata={
            "name_or_flags": ["-d", "--domain"],
            "default": "https://api.github.com/",
            "required": False,
            "help": "The domain to access the Github api from. This "
            "will only change for Github Enterprise users. "
            "[default: https://api.github.com/]",
            "convert": parse_url,
        }
    )
    repositories: List[str] = field(
        metadata={
            "name_or_flags": ["repositories"],
            "nargs": "+",
            "metavar": "repo",
            "help": "The Github repository paths to upload to the index. "
            "Usually <user>/<repo_name>.",
        }
    )
    generate: Optional[Path] = field(
        metadata={
            "name_or_flags": ["-g", "--generate"],
            "nargs": "?",
            "default": None,
            "const": ".",
            "help": "Generate the file structure if any new releases "
            "were added at the path provided. [default: .]",
            "convert": (lambda string: Path(string).resolve()),
        }
    )


@dataclass(frozen=True)
class GenerateArgs(Arguments):
    path: Optional[Path] = field(
        metadata={
            "name_or_flags": ["path"],
            "nargs": "?",
            "help": "The path to the directory to output the generated "
            "files to. [default: .]",
            "convert": (lambda string: Path(string).resolve()),
        }
    )


@dataclass(frozen=True)
class YankArgs(Arguments):
    project: str = field(
        metadata={
            "name_or_flags": ["project"],
            "help": "The name of the project to yank.",
        }
    )
    release: str = field(
        metadata={
            "name_or_flags": ["release"],
            "help": "The name of the release to yank.",
        }
    )
    comment: Optional[str] = field(
        metadata={
            "name_or_flags": ["comment"],
            "nargs": "?",
            "help": "The reason for the yanking. [default: None]",
        }
    )
