import sys
from typing import Any

from warehub import command


def main() -> Any:
    return command.dispatch(sys.argv[1:])


if __name__ == '__main__':
    sys.exit(main())
