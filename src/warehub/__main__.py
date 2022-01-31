import argparse
import http
import importlib.metadata
import sys
from typing import Any

import colorama
import requests
from packaging.requirements import Requirement

import warehub
from warehub.exceptions import WarehubException


def list_deps_and_versions() -> list[tuple[str, str]]:
    requires = importlib.metadata.requires("warehub")
    deps = [Requirement(r).name for r in requires]
    return [(dep, importlib.metadata.version(dep)) for dep in deps]


def dep_versions() -> str:
    return ", ".join(
        "{}: {}".format(*dependency) for dependency in list_deps_and_versions()
    )


def main() -> Any:
    entry_points = importlib.metadata.entry_points()
    commands = entry_points["warehub.commands"]

    parser = argparse.ArgumentParser(prog="warehub")

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s version {warehub.__version__} ({dep_versions()})",
    )
    parser.add_argument(
        "--no-color",
        default=False,
        required=False,
        action="store_true",
        help="disable colored output",
    )
    parser.add_argument(
        "command",
        choices=commands.names,
    )
    parser.add_argument(
        "args",
        help=argparse.SUPPRESS,
        nargs=argparse.REMAINDER,
    )

    args = parser.parse_args(sys.argv[1:])

    try:
        main = commands[args.command].load()

        result = main(args.args)
    except requests.HTTPError as exc:
        status_code = exc.response.status_code
        status_phrase = http.HTTPStatus(status_code).phrase
        result = (
            f"{exc.__class__.__name__}: {status_code} {status_phrase}"
            f" from {exc.response.url}\n"
            f"{exc.response.reason}"
        )
    except WarehubException as exc:
        result = f"{exc.__class__.__name__}: {exc.args[0]}"

    if isinstance(result, str):
        pre_style, post_style = "", ""
        if not args.no_color:
            colorama.init()
            pre_style, post_style = colorama.Fore.RED, colorama.Style.RESET_ALL
        return f"{pre_style}{result}{post_style}"
    return result


if __name__ == "__main__":
    sys.exit(main())
