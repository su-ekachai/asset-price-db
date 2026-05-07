from collections.abc import Mapping
from datetime import datetime

import pandas as pd
from loguru import logger

from src.db.repository import OHLCVRepository
from src.exceptions import DatabaseError, DownloadError
from src.sources.base import DataSource


class DownloadService:
    """Orchestrates a single download operation: fetch, validate, store, and log."""

    def __init__(self, repository: OHLCVRepository, sources: Mapping[str, DataSource]):
        self.repository = repository
        self.sources = sources

    def download(
        self, symbol: str, exchange: str, timeframe: str, start: datetime, end: datetime
    ) -> int:
        """Download candle data from the source, insert into repository, return row count."""
        if exchange not in self.sources:
            raise DownloadError(f"Unsupported exchange: {exchange}")

        source = self.sources[exchange]
        logger.info("Downloading {} {} from {}...", symbol, timeframe, exchange)

        df = source.download(symbol, timeframe, start, end)

        if df.empty:
            logger.warning("No data returned")
            return 0

        now = pd.Timestamp.now("UTC")
        if (df["timestamp"] > now).any():
            logger.error("Data contains future timestamps. Aborting.")
            return 0

        with self.repository.batch():
            try:
                meta = source.get_metadata(symbol)
                self.repository.register_asset(
                    symbol=symbol,
                    exchange=exchange,
                    asset_type=meta.get("asset_type", "UNKNOWN"),
                    base_currency=meta.get("base_currency"),
                    quote_currency=meta.get("quote_currency"),
                    description=meta.get("description"),
                )
            except (DatabaseError, KeyError, ValueError) as e:
                logger.warning("Failed to register asset metadata for {}: {}", symbol, e)

            rows = self.repository.insert_candles(df, symbol, exchange, timeframe)
            self.repository.log_download(symbol, exchange, timeframe, start, end, rows)

        logger.info("Inserted {} rows for {}", rows, symbol)
        return rows
