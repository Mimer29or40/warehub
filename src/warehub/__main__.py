import sys
from typing import Any

from warehub.command import dispatch


def main() -> Any:
    return dispatch(sys.argv[1:])


if __name__ == '__main__':
    sys.exit(main())
