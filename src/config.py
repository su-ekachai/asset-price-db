import os
import pathlib
from dataclasses import dataclass, field

import yaml
from loguru import logger

from src.exceptions import ConfigurationError


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

    rate_limit_pause: float = 0.5


@dataclass(kw_only=True)
class AppConfig:
    """Top-level application configuration combining all subsystems."""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)


def _env_port(name: str) -> int | None:
    """Read a port number from the environment, validating type and range."""
    val = os.environ.get(name)
    if not val:
        return None
    try:
        port = int(val)
    except ValueError:
        raise ConfigurationError(f"{name} must be an integer, got '{val}'") from None
    if not 1 <= port <= 65535:
        raise ConfigurationError(f"{name} must be between 1 and 65535, got {port}")
    return port


def _apply_env_overrides(config: AppConfig) -> AppConfig:
    """Apply environment variable overrides (highest priority)."""
    if val := os.environ.get("QUESTDB_HOST"):
        config.database.host = val
    if port := _env_port("QUESTDB_ILP_PORT"):
        config.database.ilp_port = port
    if port := _env_port("QUESTDB_PG_PORT"):
        config.database.pg_port = port
    if val := os.environ.get("QUESTDB_USER"):
        config.database.user = val
    if val := os.environ.get("QUESTDB_PASSWORD"):
        config.database.password = val
    return config


def _validate_for_production(config: AppConfig) -> None:
    """Warn about insecure configurations when connecting to non-local hosts."""
    db = config.database
    is_local = db.host in ("localhost", "127.0.0.1")

    if not is_local:
        # Check for default credentials
        if db.user == "admin" and db.password == "quest":
            logger.warning(
                "Using default credentials (admin/quest) for non-local host '{}'. "
                "This is insecure for production environments. "
                "Set QUESTDB_USER and QUESTDB_PASSWORD environment variables.",
                db.host,
            )

        # Check for unencrypted connections
        ilp_tls_enabled = os.environ.get("QUESTDB_ILP_TLS")
        sslmode = os.environ.get("QUESTDB_SSLMODE", "disable")

        if not ilp_tls_enabled and sslmode == "disable":
            logger.warning(
                "Unencrypted connection to non-local host '{}'. "
                "Set QUESTDB_ILP_TLS=1 and QUESTDB_SSLMODE=require for production.",
                db.host,
            )


def load_config(path: str | pathlib.Path = "config.yaml") -> AppConfig:
    """Load configuration with precedence: environment variables > YAML > defaults."""
    file_path = pathlib.Path(path)
    if file_path.exists():
        with file_path.open("r") as f:
            data = yaml.safe_load(f) or {}
        config = AppConfig(
            database=DatabaseConfig(**data.get("database", {})),
            download=DownloadConfig(**data.get("download", {})),
        )
    else:
        config = AppConfig()

    config = _apply_env_overrides(config)
    _validate_for_production(config)
    logger.debug(
        "Configuration loaded: host={}, ilp_port={}, pg_port={}",
        config.database.host,
        config.database.ilp_port,
        config.database.pg_port,
    )
    return config
