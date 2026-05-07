from datetime import datetime
from typing import Any, override

import pandas as pd
import yfinance as yf
from loguru import logger

from src.exceptions import DownloadError
from src.sources.base import DataSource

YAHOO_TIMEFRAMES = ["1d", "1wk", "1mo"]

YFINANCE_INTERVAL_MAP = {
    "1d": "1d",
    "1wk": "1wk",
    "1mo": "1mo",
}


class YahooSource(DataSource):
    """Data source for traditional markets (stocks, forex, commodities) via yfinance."""

    @override
    def supported_timeframes(self) -> list[str]:
        """Return the list of timeframes supported by Yahoo Finance."""
        return YAHOO_TIMEFRAMES

    @override
    def validate_symbol(self, symbol: str) -> bool:
        """Return True if the symbol is alphanumeric without slashes."""
        return "/" not in symbol and symbol.isalnum()

    @override
    def download(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Fetch OHLCV data from Yahoo Finance for the given symbol and date range."""
        if timeframe not in YFINANCE_INTERVAL_MAP:
            available = ", ".join(YAHOO_TIMEFRAMES)
            raise DownloadError(
                f"Yahoo source does not support timeframe '{timeframe}' — available: {available}"
            )

        interval = YFINANCE_INTERVAL_MAP[timeframe]

        logger.info(
            "Downloading {} {} via yfinance ({} to {})",
            symbol,
            interval,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )

        try:
            df = yf.download(
                symbol,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval=interval,
                progress=False,
                auto_adjust=True,
            )
        except (ValueError, KeyError, ConnectionError) as e:
            raise DownloadError(f"Yahoo Finance download failed for {symbol}: {e}") from e

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.reset_index()

        column_map = {
            "Date": "timestamp",
            "Datetime": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        df = df.rename(columns=column_map)

        required = ["timestamp", "open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise DownloadError(f"Yahoo response missing columns: {missing}")

        df = df[required]
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

        return df

    @override
    def get_metadata(self, symbol: str) -> dict[str, Any]:
        """Return asset metadata from Yahoo Finance ticker info."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                "asset_type": info.get("quoteType", "equity").lower(),
                "base_currency": symbol,
                "quote_currency": info.get("currency", "USD"),
                "description": info.get("longName", f"{symbol} on Yahoo Finance"),
            }
        except (ValueError, KeyError, AttributeError) as e:
            logger.warning("Failed to fetch Yahoo metadata for {}: {}", symbol, e)
            return {
                "asset_type": "equity",
                "base_currency": symbol,
                "quote_currency": "USD",
                "description": f"{symbol} on Yahoo Finance",
            }
