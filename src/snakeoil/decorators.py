"""Various decorator utilities."""

from functools import wraps
from typing import Callable, Generator, ParamSpec, TypeVar

P = ParamSpec("P")
T_yield = TypeVar("T_yield")
T_send = TypeVar("T_send")
T_return = TypeVar("T_return")


def coroutine(
    func: Callable[P, Generator[T_yield, T_send, T_return]],
) -> Callable[P, Generator[T_yield, T_send, T_return]]:
    """Prime a coroutine for input."""

    @wraps(func)
    def prime(
        *args: P.args, **kwargs: P.kwargs
    ) -> Generator[T_yield, T_send, T_return]:
        cr = func(*args, **kwargs)
        next(cr)
        return cr

    return prime
