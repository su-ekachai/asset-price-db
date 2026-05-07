from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import pandas as pd


class DataSource(ABC):
    """Abstract base class defining the contract for OHLCV data providers."""

    @abstractmethod
    def download(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Fetch candle data for the given symbol and date range."""

    @abstractmethod
    def get_metadata(self, symbol: str) -> dict[str, Any]:
        """Return asset metadata (asset_type, base_currency, quote_currency, description)."""

    @abstractmethod
    def supported_timeframes(self) -> list[str]:
        """Return the list of valid timeframe strings for this source."""

    @abstractmethod
    def validate_symbol(self, symbol: str) -> bool:
        """Return True if the symbol format is valid for this source."""
