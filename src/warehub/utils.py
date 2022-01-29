import os
from argparse import Action, ArgumentParser, Namespace
from typing import Optional, Sequence, Any, Union

__all__ = [
    'EnvironmentDefault',
]


class EnvironmentDefault(Action):
    """Get values from environment variable."""
    
    def __init__(
            self,
            env: str,
            required: bool = True,
            default: Optional[str] = None,
            **kwargs: Any
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
