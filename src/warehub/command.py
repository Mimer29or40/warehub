import argparse
import logging
import pprint
import sys
from typing import Any, List, Tuple

import colorama
import importlib_metadata
from packaging import requirements

import warehub
from warehub import config, exceptions, settings

global_args = argparse.Namespace()


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
    except exceptions.WarehubException as exc:
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
    return add_impl(settings.Add.from_args(args))


def generate(args: List[str]):
    """Execute the ``generate`` command.
    :param args:
        The command-line arguments.
    """
    return generate_impl(settings.Generate.from_args(args))


def yank(args: List[str]):
    """Execute the ``yank`` command.
    :param args:
        The command-line arguments.
    """
    return yank_impl(settings.Yank.from_args(args))


def _setup(settings: settings.Settings):
    logger = logging.getLogger(warehub.__title__)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.INFO if settings.verbose else logging.WARNING)
    
    logger.info(pprint.pformat(settings))
    
    config.load(settings.config)


def add_impl(settings: settings.Add):
    _setup(settings)


def generate_impl(settings: settings.Generate):
    _setup(settings)


def yank_impl(settings: settings.Yank):
    _setup(settings)
