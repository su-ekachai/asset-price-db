import fcntl
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from loguru import logger

from src.db.repository import OHLCVRepository
from src.exceptions import ConfigurationError, DatabaseError, DownloadError
from src.sources.base import DataSource
from src.sources.registry import create_source
from src.watchlist import WatchlistEntry, parse_lookback_days


@dataclass(kw_only=True)
class SyncResult:
    """Outcome of syncing a single symbol (status, rows inserted, duration)."""

    symbol: str
    exchange: str
    timeframe: str
    rows_inserted: int
    status: str  # "synced", "skipped", "failed", "dry_run"
    duration: float = 0.0
    message: str = ""


class SyncService:
    """Watchlist-driven sync service that downloads delta data for each symbol to present."""

    def __init__(self, repository: OHLCVRepository, rate_limit_pause: float = 0.5):
        self._repository = repository
        self._rate_limit_pause = rate_limit_pause
        self._sources: dict[str, DataSource] = {}

    def _get_source(self, exchange: str) -> DataSource:
        if exchange not in self._sources:
            self._sources[exchange] = create_source(
                exchange, rate_limit_pause=self._rate_limit_pause
            )
        return self._sources[exchange]

    def sync_symbol(self, entry: WatchlistEntry, dry_run: bool = False) -> SyncResult:
        """Sync a single symbol to present and return the outcome as SyncResult."""
        start_time = time.time()

        source = self._get_source(entry.exchange)

        last_ts = self._repository.get_last_timestamp(entry.symbol, entry.exchange, entry.timeframe)

        now = datetime.now(UTC)

        if last_ts is None:
            lookback_days = parse_lookback_days(entry.lookback)
            start = now - timedelta(days=lookback_days)
        else:
            # Resume AT the last stored candle, not after it: the previous sync may
            # have stored a still-forming candle, and DEDUP overwrites it with final
            # values on refetch. Starting past it would freeze incomplete data forever.
            start = last_ts

        if start >= now:
            return SyncResult(
                symbol=entry.symbol,
                exchange=entry.exchange,
                timeframe=entry.timeframe,
                rows_inserted=0,
                status="skipped",
                duration=time.time() - start_time,
                message="Already up to date",
            )

        if dry_run:
            return SyncResult(
                symbol=entry.symbol,
                exchange=entry.exchange,
                timeframe=entry.timeframe,
                rows_inserted=0,
                status="dry_run",
                duration=time.time() - start_time,
                message=f"Would download from {start.strftime('%Y-%m-%d %H:%M')} to now",
            )

        try:
            df = source.download(entry.symbol, entry.timeframe, start, now)

            if df.empty:
                return SyncResult(
                    symbol=entry.symbol,
                    exchange=entry.exchange,
                    timeframe=entry.timeframe,
                    rows_inserted=0,
                    status="skipped",
                    duration=time.time() - start_time,
                    message="No new data available",
                )

            with self._repository.batch():
                rows = self._repository.insert_candles(
                    df, entry.symbol, entry.exchange, entry.timeframe
                )
                self._repository.log_download(
                    entry.symbol, entry.exchange, entry.timeframe, start, now, rows
                )

            return SyncResult(
                symbol=entry.symbol,
                exchange=entry.exchange,
                timeframe=entry.timeframe,
                rows_inserted=rows,
                status="synced",
                duration=time.time() - start_time,
            )

        except (DownloadError, DatabaseError) as e:
            logger.error("Sync failed for {} ({}): {}", entry.symbol, type(e).__name__, e)
            return SyncResult(
                symbol=entry.symbol,
                exchange=entry.exchange,
                timeframe=entry.timeframe,
                rows_inserted=0,
                status="failed",
                duration=time.time() - start_time,
                message=str(e),
            )
        except Exception as e:
            logger.opt(exception=True).error("Unexpected error syncing {}", entry.symbol)
            return SyncResult(
                symbol=entry.symbol,
                exchange=entry.exchange,
                timeframe=entry.timeframe,
                rows_inserted=0,
                status="failed",
                duration=time.time() - start_time,
                message=f"Unexpected error: {e}",
            )

    def sync_all(
        self,
        entries: list[WatchlistEntry],
        dry_run: bool = False,
        on_result: Callable[[WatchlistEntry, SyncResult], None] | None = None,
    ) -> list[SyncResult]:
        """Sync all watchlist entries sequentially and return results per symbol.

        Holds an exclusive lock for the whole batch so overlapping runs (e.g. a cron
        sync outlasting its interval) cannot interleave. `on_result` is invoked after
        each symbol completes (used by the CLI for progress display).
        """
        lock_file_path = Path("/tmp/ohlcv-sync.lock")
        lock_file_path.parent.mkdir(parents=True, exist_ok=True)

        lock_file = lock_file_path.open("w")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            lock_file.close()
            logger.warning("Another sync process is already running")
            raise ConfigurationError("Another sync process is already running") from e

        try:
            results: list[SyncResult] = []
            for entry in entries:
                result = self.sync_symbol(entry, dry_run=dry_run)
                results.append(result)
                if on_result:
                    on_result(entry, result)
                logger.info(
                    "[{}] {} ({}/{}): {} rows in {:.1f}s{}",
                    result.status,
                    entry.symbol,
                    entry.exchange,
                    entry.timeframe,
                    result.rows_inserted,
                    result.duration,
                    f" — {result.message}" if result.message else "",
                )

            synced = sum(1 for r in results if r.status == "synced")
            total_rows = sum(r.rows_inserted for r in results)
            logger.info(
                "Sync batch complete: {}/{} succeeded, {} rows inserted",
                synced,
                len(entries),
                total_rows,
            )
            return results
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
