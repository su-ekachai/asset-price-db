from src.sources.base import DataSource
from src.sources.ccxt_source import CcxtSource
from src.sources.yahoo import YahooSource


def create_source(exchange: str, rate_limit_pause: float = 0.5) -> DataSource:
    """Factory that instantiates the appropriate DataSource for the given exchange name."""
    if exchange == "yahoo":
        return YahooSource()
    return CcxtSource(exchange_name=exchange, rate_limit_pause=rate_limit_pause)
