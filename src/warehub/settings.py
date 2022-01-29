from __future__ import annotations

import argparse
from dataclasses import dataclass, fields, field
from typing import TypeVar, Type, List, Optional

import warehub
from warehub import utils

T = TypeVar('T')


@dataclass(frozen=True)
class Settings:
    verbose: bool = field(metadata={
        'name_or_flags': ['-v', '--verbose'],
        'default':       False,
        'required':      False,
        'action':        'store_true',
        'help':          'show verbose output',
    })
    config: str = field(metadata={
        'name_or_flags': ['-c', '--config'],
        'default':       './config.json',
        'required':      False,
        'help':          'The path to the config file. [default: ./config.json]',
    })
    
    @classmethod
    def from_args(cls: Type[T], args: list[str]) -> T:
        """Generate the Settings from parsed arguments."""
        
        parser = argparse.ArgumentParser(prog=f'{warehub.__title__} {cls.__name__.lower()}')
        
        for field in fields(cls):
            metadata = dict(field.metadata)
            name_or_flags = tuple(metadata.pop('name_or_flags') if 'name_or_flags' in metadata else [])
            parser.add_argument(*name_or_flags, **metadata)
        
        return cls(**vars(parser.parse_args(args)))


@dataclass(frozen=True)
class Add(Settings):
    username: Optional[str] = field(metadata={
        'name_or_flags': ['-u', '--username'],
        'action':        utils.EnvironmentDefault,
        'env':           'WAREHUB_USERNAME',
        'required':      False,
        'help':          'The username to authenticate to the repository '
                         '(package index) as. (Can also be set via '
                         '%(env)s environment variable.) '
                         '[default: env.WAREHUB_USERNAME]',
    })
    password: Optional[str] = field(metadata={
        'name_or_flags': ['-p', '--password'],
        'action':        utils.EnvironmentDefault,
        'env':           'WAREHUB_PASSWORD',
        'required':      False,
        'help':          'The password to authenticate to the repository '
                         '(package index) with. (Can also be set via '
                         '%(env)s environment variable.) '
                         '[default: env.WAREHUB_PASSWORD]',
    })
    domain: str = field(metadata={
        'name_or_flags': ['-d', '--domain'],
        'default':       'https://api.github.com/',
        'required':      False,
        'help':          'The domain to access the Github api from. This '
                         'will only change for Github Enterprise users. '
                         '[default: https://api.github.com/]',
    })
    repositories: List[str] = field(metadata={
        'name_or_flags': ['repositories'],
        'nargs':         '+',
        'metavar':       'repo',
        'help':          'The Github repository paths to upload to the index. '
                         'Usually <user>/<repo_name>.',
    })
    generate: Optional[str] = field(metadata={
        'name_or_flags': ['-g', '--generate'],
        'nargs':         '?',
        'default':       None,
        'const':         '.',
        'help':          'Generate the file structure if any new releases '
                         'were added at the path provided. [default: .]',
    })


@dataclass(frozen=True)
class Generate(Settings):
    path: Optional[str] = field(metadata={
        'name_or_flags': ['path'],
        'nargs':         '?',
        'help':          'The path to the directory to output the generated '
                         'files to. [default: .]',
    })


@dataclass(frozen=True)
class Yank(Settings):
    project: str = field(metadata={
        'name_or_flags': ['project'],
        'help':          'The name of the project to yank.',
    })
    release: str = field(metadata={
        'name_or_flags': ['release'],
        'help':          'The name of the release to yank.',
    })
    comment: Optional[str] = field(metadata={
        'name_or_flags': ['comment'],
        'nargs':         '?',
        'help':          'The reason for the yanking. [default: None]',
    })
