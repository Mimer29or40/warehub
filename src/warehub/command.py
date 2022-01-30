import argparse
import logging
import pprint
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Tuple, Optional

import colorama
import importlib_metadata
import requests as requests
from packaging import requirements

import warehub
from warehub.config import Config
from warehub.arguments import AddArgs, GenerateArgs, YankArgs, Arguments
from warehub.database import Database
from warehub.exceptions import WarehubException
from warehub.model import Directories
from warehub.package import Package, add_package
from warehub.utils import parse_url, file_size_str

__all__ = [
    'dispatch',
    'add',
    'generate',
    'yank',
]

logger = logging.getLogger(warehub.__title__)


def list_dependencies_and_versions() -> List[Tuple[str, str]]:
    requires = importlib_metadata.requires('warehub')  # type: ignore[no-untyped-call] # python/importlib_metadata#288  # noqa: E501
    deps = [requirements.Requirement(r).name for r in requires]
    return [(dep, importlib_metadata.version(dep)) for dep in deps]  # type: ignore[no-untyped-call] # python/importlib_metadata#288  # noqa: E501


def dep_versions() -> str:
    return ', '.join(
        '{}: {}'.format(*dependency) for dependency in list_dependencies_and_versions()
    )


def dispatch(argv: List[str]) -> Any:
    commands = importlib_metadata.entry_points(group='warehub.commands')
    
    parser = argparse.ArgumentParser(prog='warehub')
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s version {warehub.__version__} ({dep_versions()})',
    )
    parser.add_argument(
        '--no-color',
        default=False,
        required=False,
        action='store_true',
        help='disable colored output',
    )
    parser.add_argument(
        'command',
        choices=commands.names,
    )
    parser.add_argument(
        'args',
        help=argparse.SUPPRESS,
        nargs=argparse.REMAINDER,
    )
    
    args = parser.parse_args(argv)
    
    try:
        main = commands[args.command].load()
        
        result = main(args.args)
    # except requests.HTTPError as exc:
    #     status_code = exc.response.status_code
    #     status_phrase = http.HTTPStatus(status_code).phrase
    #     result = (
    #         f'{exc.__class__.__name__}: {status_code} {status_phrase}'
    #         f' from {exc.response.url}\n'
    #         f'{exc.response.reason}'
    #     )
    except WarehubException as exc:
        result = f'{exc.__class__.__name__}: {exc.args[0]}'
    
    if isinstance(result, str):
        pre_style, post_style = '', ''
        if not args.no_color:
            colorama.init()
            pre_style, post_style = colorama.Fore.RED, colorama.Style.RESET_ALL
        return f'{pre_style}{result}{post_style}'
    return result


def add(args: List[str]):
    """Execute the ``add`` command.
    :param args:
        The command-line arguments.
    """
    return add_impl(AddArgs.from_args(args))


def generate(args: List[str]):
    """Execute the ``generate`` command.
    :param args:
        The command-line arguments.
    """
    return generate_impl(GenerateArgs.from_args(args))


def yank(args: List[str]):
    """Execute the ``yank`` command.
    :param args:
        The command-line arguments.
    """
    return yank_impl(YankArgs.from_args(args))


def setup(args: Arguments) -> None:
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.DEBUG if args.verbose else logging.WARNING)
    
    logger.info(pprint.pformat(args))
    
    Config.load(args.config)
    
    Database.file(Config.path / Config.database)
    
    for directory in Directories.LIST:
        (Config.path / directory).mkdir(parents=True, exist_ok=True)


def add_impl(args: AddArgs):
    setup(args)
    
    auth: Optional[tuple[Optional[str], Optional[str]]] = (
        (args.username or '', args.password or '')
        if args.username or args.password else None
    )
    if auth is not None:
        logger.debug('Authentication provided')
    
    file_urls: list[str] = []
    for repo_path in args.repositories:
        repo_url = parse_url(args.domain + f'repos/{repo_path}/releases')
        logger.info(f'Getting Releases from: {repo_url}')
        response = requests.get(repo_url, auth=auth)
        releases_obj = response.json()
        logger.debug(f'Response Code: {response.status_code}')
        if response.status_code != requests.codes.ok:
            logger.warning(f'Could not get information on release for '
                           f'\'{repo_url}\': {releases_obj["message"]}')
            continue
        for info in releases_obj:
            for asset in info['assets']:
                file_urls.append(asset['browser_download_url'])
    if len(file_urls) == 0:
        logger.info('No Files to Download')
        return
    
    logger.info(f'Found {len(file_urls)} files')
    with tempfile.TemporaryDirectory() as temp:
        temp_dir = Path(temp)
        
        downloaded_files: list[Path] = []
        for file_url in file_urls:
            download = requests.get(file_url, auth=auth)
            logger.debug(f'Response Code: {download.status_code}')
            if download.status_code != requests.codes.ok:
                logger.warning(f'Could not download \'{file_url}\': '
                               f'{download.status_code}')
                continue
            
            file = temp_dir / file_url.split('/')[-1]
            file.write_bytes(download.content)
            
            logger.info(f'Downloaded File: {file_url}\n  to: {file.absolute()}')
            
            downloaded_files.append(file)
        
        signatures: dict[str, Path] = {f.name: f for f in downloaded_files if f.suffix == '.asc'}
        logger.debug(f'Signature Files:\n' + pprint.pformat(signatures))
        
        added: set[str] = set()
        for file in downloaded_files:
            try:
                if file.suffix != '.asc':
                    package = Package(file, None)
                    
                    if (signed_name := package.signed_file.name) in signatures:
                        package.gpg_signature = signatures[signed_name]
                    
                    logger.debug(
                        f'Package created for file: \'{package.file.name}\' '
                        f'({file_size_str(package.file)})')
                    if package.gpg_signature:
                        logger.debug(f'\tSigned with {package.signed_file}')
                    
                    # add_package(package)
                    
                    added.add(Config.url + f'simple/{package.name}/{package.version}/')
            
            except Exception as e:
                logger.exception(
                    f'Exception found when processing file: {file.name}',
                    exc_info=e
                )


def generate_impl(args: GenerateArgs):
    setup(args)


def yank_impl(args: YankArgs):
    setup(args)
