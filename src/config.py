import os
import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml
from loguru import logger

type JSONDict = dict[str, Any]


@dataclass(kw_only=True)
class DatabaseConfig:
    """Connection parameters for QuestDB (ILP writes + PostgreSQL reads)."""

    host: str = "localhost"
    ilp_port: int = 9000
    pg_port: int = 8812
    user: str = "admin"
    password: str = "quest"


@dataclass(kw_only=True)
class DownloadConfig:
    """Default parameters for download operations."""

    default_exchange: str = "binance"
    default_timeframe: str = "1m"
    chunk_size: int = 1000
    rate_limit_pause: float = 0.5


@dataclass(kw_only=True)
class AppConfig:
    """Top-level application configuration combining all subsystems."""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    exchanges: JSONDict = field(default_factory=dict)


def _apply_env_overrides(config: AppConfig) -> AppConfig:
    """Apply environment variable overrides (highest priority)."""
    if val := os.environ.get("QUESTDB_HOST"):
        config.database.host = val
    if val := os.environ.get("QUESTDB_ILP_PORT"):
        config.database.ilp_port = int(val)
    if val := os.environ.get("QUESTDB_PG_PORT"):
        config.database.pg_port = int(val)
    if val := os.environ.get("QUESTDB_USER"):
        config.database.user = val
    if val := os.environ.get("QUESTDB_PASSWORD"):
        config.database.password = val
    return config


def load_config(path: str | pathlib.Path = "config.yaml") -> AppConfig:
    """Load configuration with precedence: environment variables > YAML > defaults."""
    file_path = pathlib.Path(path)
    if not file_path.exists():
        config = _apply_env_overrides(AppConfig())
        logger.debug(
            "Configuration loaded: host={}, ilp_port={}, pg_port={}",
            config.database.host,
            config.database.ilp_port,
            config.database.pg_port,
        )
        return config

    with file_path.open("r") as f:
        data = yaml.safe_load(f) or {}

    db_data = data.get("database", {})
    dl_data = data.get("download", {})
    exchanges = data.get("exchanges", {})

    config = AppConfig(
        database=DatabaseConfig(**db_data),
        download=DownloadConfig(**dl_data),
        exchanges=exchanges,
    )
    config = _apply_env_overrides(config)
    logger.debug(
        "Configuration loaded: host={}, ilp_port={}, pg_port={}",
        config.database.host,
        config.database.ilp_port,
        config.database.pg_port,
    )
    return config
