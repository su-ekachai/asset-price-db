import sys
from dataclasses import dataclass

from loguru import logger

from src.config import AppConfig, load_config


@dataclass(kw_only=True)
class State:
    """Module-level singleton holding CLI session state (verbosity and configuration)."""

    verbose: int = 0
    config: AppConfig | None = None

    @property
    def cfg(self) -> AppConfig:
        assert self.config is not None
        return self.config


state = State()


def init_state(verbose: int = 0) -> None:
    state.verbose = verbose
    _setup_logging(verbose)
    state.config = load_config()


def _setup_logging(verbose: int) -> None:
    logger.remove()
    level = "WARNING" if verbose == 0 else "INFO" if verbose == 1 else "DEBUG"
    logger.add(sys.stderr, level=level)
