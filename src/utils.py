import functools
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from loguru import logger

P = ParamSpec("P")
R = TypeVar("R")


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that retries a function on specified exceptions with exponential backoff."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        name = getattr(func, "__name__", repr(func))

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception: Exception = Exception("unreachable")
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        break
                    wait = delay * (backoff ** (attempt - 1))
                    logger.warning(
                        "Retry {}/{} for {}: {}. Waiting {:.1f}s",
                        attempt,
                        max_attempts,
                        name,
                        e,
                        wait,
                    )
                    time.sleep(wait)
            raise last_exception

        return wrapper

    return decorator
