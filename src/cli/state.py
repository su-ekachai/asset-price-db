import os
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
        if self.config is None:
            raise RuntimeError("CLI state not initialized: init_state() must run first")
        return self.config


state = State()


def init_state(verbose: int = 0) -> None:
    state.verbose = verbose
    _setup_logging(verbose)
    state.config = load_config()


def _setup_logging(verbose: int) -> None:
    logger.remove()
    level = "WARNING" if verbose == 0 else "INFO" if verbose == 1 else "DEBUG"

    log_format = os.getenv("OHLCV_LOG_FORMAT", "text")
    use_json = log_format.lower() == "json"

    logger.add(sys.stderr, level=level, serialize=use_json)

    log_file = os.getenv("OHLCV_LOG_FILE")
    if log_file:
        logger.add(
            log_file,
            level=level,
            serialize=use_json,
            rotation="50 MB",
            retention="7 days",
        )
