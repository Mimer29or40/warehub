import os
from argparse import Action, ArgumentParser, Namespace
from typing import Optional, Sequence, Any, Union


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


class EnvironmentFlag(Action):
    """Set boolean flag from environment variable."""
    
    def __init__(
            self,
            env: str,
            **kwargs: Any
    ) -> None:
        default = self.bool_from_env(os.environ.get(env))
        self.env = env
        super().__init__(default=default, nargs=0, **kwargs)
    
    def __call__(
            self,
            parser: ArgumentParser,
            namespace: Namespace,
            values: Union[str, Sequence[Any], None],
            option_string: Optional[str] = None,
    ) -> None:
        setattr(namespace, self.dest, True)
    
    @staticmethod
    def bool_from_env(val: Optional[str]) -> bool:
        """Allow '0' and 'false' and 'no' to be False."""
        false_like = {'0', 'false', 'no'}
        return bool(val and val.lower() not in false_like)
