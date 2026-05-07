class AssetPriceDBError(Exception):
    """Base exception for all OHLCV data store operations."""


class DownloadError(AssetPriceDBError):
    """Raised when a data source fails to return candle data."""


class RateLimitError(DownloadError):
    """Raised when an exchange API enforces rate limiting."""


class NetworkError(DownloadError):
    """Raised when a network request fails after all retries."""


class ConfigurationError(AssetPriceDBError):
    """Raised when configuration is invalid or missing required values."""


class DatabaseError(AssetPriceDBError):
    """Raised when a database operation fails."""
