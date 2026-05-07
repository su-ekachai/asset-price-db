from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd
from loguru import logger

from src.db.repository import OHLCVRepository

TIMEFRAME_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "8h": 480,
    "12h": 720,
    "1d": 1440,
    "3d": 4320,
    "1wk": 10080,
    "1mo": 43200,
}


@dataclass(kw_only=True)
class Gap:
    """A detected period of missing candle data between two timestamps."""

    start: datetime
    end: datetime
    missing_candles: int


@dataclass(kw_only=True)
class Anomaly:
    """A single data quality issue at a specific timestamp."""

    timestamp: datetime
    anomaly_type: str
    details: str


@dataclass(kw_only=True)
class HealthReport:
    """Summary of QuestDB connectivity and data statistics."""

    connected: bool
    tables_exist: bool
    total_rows: int = 0
    symbol_count: int = 0
    errors: list[str] = field(default_factory=list)


class IntegrityService:
    """Data quality validation: gap detection, anomaly detection, and health checks."""

    def __init__(self, repository: OHLCVRepository):
        self._repo = repository

    def find_gaps(self, symbol: str, exchange: str, timeframe: str) -> list[Gap]:
        """Find missing time periods based on expected candle frequency."""
        df = self._repo.get_candles(symbol, exchange, timeframe)
        if df.empty:
            return []

        interval_minutes = TIMEFRAME_MINUTES.get(timeframe)
        if not interval_minutes:
            logger.warning("Unknown timeframe '{}', cannot detect gaps", timeframe)
            return []

        expected_delta = timedelta(minutes=interval_minutes)
        timestamps = pd.to_datetime(df["timestamp"]).sort_values().reset_index(drop=True)

        gaps: list[Gap] = []
        for i in range(1, len(timestamps)):
            actual_delta = timestamps[i] - timestamps[i - 1]
            if actual_delta > expected_delta * 1.5:
                missing = int(actual_delta / expected_delta) - 1
                gaps.append(
                    Gap(
                        start=timestamps[i - 1].to_pydatetime(),
                        end=timestamps[i].to_pydatetime(),
                        missing_candles=missing,
                    )
                )

        return gaps

    def find_anomalies(self, symbol: str, exchange: str, timeframe: str) -> list[Anomaly]:
        """Detect data quality issues."""
        df = self._repo.get_candles(symbol, exchange, timeframe)
        if df.empty:
            return []

        anomalies: list[Anomaly] = []

        # Vectorized OHLC violation detection
        highs = df["high"].astype(float)
        lows = df["low"].astype(float)
        ohlc_mask = highs < lows
        for ts in df.loc[ohlc_mask, "timestamp"]:
            ts_dt = pd.Timestamp(ts).to_pydatetime()
            assert isinstance(ts_dt, datetime)
            anomalies.append(
                Anomaly(
                    timestamp=ts_dt,
                    anomaly_type="ohlc_violation",
                    details="High < Low",
                )
            )

        # Vectorized zero volume detection
        zero_vol_mask = df["volume"] == 0
        for ts in df.loc[zero_vol_mask, "timestamp"]:
            ts_dt = pd.Timestamp(ts).to_pydatetime()
            assert isinstance(ts_dt, datetime)
            anomalies.append(
                Anomaly(
                    timestamp=ts_dt,
                    anomaly_type="zero_volume",
                    details="Volume is zero",
                )
            )

        # Sudden >50% moves in a single candle typically indicate bad data or exchange glitches
        if len(df) > 1:
            closes = df["close"].astype(float)
            pct_change = closes.pct_change().abs()
            spikes = df[pct_change > 0.5]
            for _, row in spikes.iterrows():
                ts_dt = pd.Timestamp(row["timestamp"]).to_pydatetime()
                assert isinstance(ts_dt, datetime)
                anomalies.append(
                    Anomaly(
                        timestamp=ts_dt,
                        anomaly_type="price_spike",
                        details="Close price changed >50% in single candle",
                    )
                )

        # Duplicates indicate source-side bugs or ingestion retries without dedup
        timestamps = df["timestamp"]
        duplicates = df[timestamps.duplicated(keep=False)]
        seen_ts = set()
        for _, row in duplicates.iterrows():
            ts = pd.Timestamp(row["timestamp"])
            if ts not in seen_ts:
                seen_ts.add(ts)
                ts_dt = ts.to_pydatetime()
                assert isinstance(ts_dt, datetime)
                anomalies.append(
                    Anomaly(
                        timestamp=ts_dt,
                        anomaly_type="duplicate",
                        details="Duplicate timestamp detected",
                    )
                )

        return anomalies

    def check_health(self) -> HealthReport:
        """Verify QuestDB connectivity, table existence, basic stats."""
        try:
            result = self._repo._reader.query("SELECT count() FROM ohlcv")
            total_rows = result[0][0] if result else 0
        except Exception as e:
            logger.warning("Health check query failed: {}", e)
            return HealthReport(
                connected=False,
                tables_exist=False,
                errors=[str(e)],
            )

        try:
            symbols_df = self._repo.get_symbols()
            symbol_count = len(symbols_df)
        except Exception as e:
            logger.warning("Failed to query symbol count: {}", e)
            symbol_count = 0

        return HealthReport(
            connected=True,
            tables_exist=True,
            total_rows=total_rows,
            symbol_count=symbol_count,
        )
