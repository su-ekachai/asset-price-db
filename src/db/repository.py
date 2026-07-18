from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime

import pandas as pd
from loguru import logger

from src.db.connection import QuestDBReader, QuestDBWriter

# Fixed designated timestamp for the assets table: DEDUP keys are
# (created_at, symbol, exchange), so re-registrations only upsert (rather than
# append a new row) when the timestamp is identical across calls.
_ASSET_REGISTRY_TS = datetime(2000, 1, 1, tzinfo=UTC)


class OHLCVRepository:
    """Data access layer for OHLCV candle storage and retrieval."""

    def __init__(self, writer: QuestDBWriter, reader: QuestDBReader):
        self._writer = writer
        self._reader = reader

    @contextmanager
    def batch(self) -> Generator[None, None, None]:
        """Context manager delegating to the writer's batch connection."""
        with self._writer.batch():
            yield

    def insert_candles(self, df: pd.DataFrame, symbol: str, exchange: str, timeframe: str) -> int:
        """Batch-insert candle data and return the number of rows written."""
        logger.debug("Inserting {} candles: {}/{}/{}", len(df), symbol, exchange, timeframe)
        if df.empty:
            return 0

        df = df.copy()

        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], utc=True)
            # Guard both write paths (download and sync): future timestamps are
            # clock skew or bad source data — drop them, keep the valid rows.
            future = ts > pd.Timestamp.now("UTC")
            if future.any():
                logger.warning(
                    "Dropping {} candles with future timestamps: {}/{}/{}",
                    int(future.sum()),
                    symbol,
                    exchange,
                    timeframe,
                )
                df = df.loc[~future]
                ts = ts.loc[~future]
                if df.empty:
                    return 0
            df["timestamp"] = ts.dt.tz_localize(None).dt.as_unit("us")

        df["symbol"] = symbol
        df["exchange"] = exchange
        df["timeframe"] = timeframe

        self._writer.insert_dataframe(
            df=df,
            table_name="ohlcv",
            symbols=["symbol", "exchange", "timeframe"],
            at="timestamp",
        )
        return len(df)

    def log_download(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        rows: int,
    ) -> None:
        """Record a download operation in the download_log table."""
        self._writer.insert_row(
            table_name="download_log",
            symbols={"symbol": symbol, "exchange": exchange, "timeframe": timeframe},
            columns={"start_time": start, "end_time": end, "rows_inserted": rows},
            at=datetime.now(UTC),
        )

    def get_last_timestamp(self, symbol: str, exchange: str, timeframe: str) -> datetime | None:
        """Return the most recent timestamp for a symbol, or None if no data exists."""
        rows = self._reader.query(
            "SELECT max(timestamp) FROM ohlcv "
            "WHERE symbol = %s AND exchange = %s AND timeframe = %s",
            (symbol, exchange, timeframe),
        )
        if rows and rows[0][0] is not None:
            ts = rows[0][0]
            if ts.tzinfo is None:
                return ts.replace(tzinfo=UTC)
            return ts
        return None

    def get_candles(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Query candle data with optional date range and row limit filters."""
        sql = (
            "SELECT timestamp, open, high, low, close, volume FROM ohlcv "
            "WHERE symbol = %s AND exchange = %s AND timeframe = %s"
        )
        params: list[str | datetime | int] = [symbol, exchange, timeframe]

        if start:
            sql += " AND timestamp >= %s"
            params.append(start)
        if end:
            sql += " AND timestamp <= %s"
            params.append(end)

        sql += " ORDER BY timestamp"

        if limit:
            sql += " LIMIT %s"
            params.append(limit)

        return self._reader.query_df(sql, tuple(params))

    def count_candles(self) -> int:
        """Return the total number of stored candles."""
        rows = self._reader.query("SELECT count() FROM ohlcv")
        return int(rows[0][0]) if rows else 0

    def get_symbols(self) -> pd.DataFrame:
        """Return all stored symbol/exchange/timeframe combinations with row counts."""
        sql = (
            "SELECT symbol, exchange, timeframe, count() as rows, max(timestamp) as last_update "
            "FROM ohlcv GROUP BY symbol, exchange, timeframe ORDER BY symbol"
        )
        return self._reader.query_df(sql)

    def register_asset(
        self,
        symbol: str,
        exchange: str,
        asset_type: str,
        base_currency: str | None,
        quote_currency: str | None,
        description: str | None,
    ) -> None:
        """Upsert asset metadata into the assets table."""
        self._writer.insert_row(
            table_name="assets",
            symbols={
                "symbol": symbol,
                "exchange": exchange,
                "asset_type": asset_type,
                "base_currency": base_currency or "UNKNOWN",
                "quote_currency": quote_currency or "UNKNOWN",
            },
            columns={"description": description or ""},
            at=_ASSET_REGISTRY_TS,
        )
