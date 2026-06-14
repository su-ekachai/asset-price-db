import random
import time
from datetime import datetime
from typing import Any, override

import ccxt
import pandas as pd
from loguru import logger

from src.exceptions import DownloadError, NetworkError, RateLimitError
from src.sources.base import DataSource


class CcxtSource(DataSource):
    """Data source for any ccxt-supported cryptocurrency exchange."""

    def __init__(self, exchange_name: str, rate_limit_pause: float = 0.5) -> None:
        exchange_class = getattr(ccxt, exchange_name, None)
        if exchange_class is None:
            raise DownloadError(f"Unknown exchange: {exchange_name}")
        self.exchange: ccxt.Exchange = exchange_class({"enableRateLimit": True})
        self._exchange_name = exchange_name
        self._rate_limit_pause = rate_limit_pause
        self._markets_loaded = False

    @override
    def supported_timeframes(self) -> list[str]:
        """Return the list of timeframes supported by this exchange."""
        return list(self.exchange.timeframes.keys()) if self.exchange.timeframes else []

    @override
    def validate_symbol(self, symbol: str) -> bool:
        """Return True if the symbol contains a slash separator (e.g. BTC/USDT)."""
        return "/" in symbol

    @override
    def download(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Fetch OHLCV candles from the exchange via ccxt with retry logic."""
        logger.info(
            "Downloading {} {} from {} ({} to {})",
            symbol,
            timeframe,
            self._exchange_name,
            start.isoformat(),
            end.isoformat(),
        )
        start_ts = int(start.timestamp() * 1000)
        end_ts = int(end.timestamp() * 1000)

        all_ohlcv: list[list[Any]] = []
        current_ts = start_ts
        consecutive_failures = 0
        max_retries = 3

        while current_ts < end_ts:
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=current_ts, limit=1000)
                if not ohlcv:
                    break

                all_ohlcv.extend(ohlcv)
                current_ts = ohlcv[-1][0] + 1
                consecutive_failures = 0

            except ccxt.RateLimitExceeded as e:
                consecutive_failures += 1
                if consecutive_failures >= max_retries:
                    raise RateLimitError(f"Rate limit exceeded after {max_retries} retries") from e
                wait = (
                    self._rate_limit_pause
                    * (2 ** (consecutive_failures - 1))
                    * random.uniform(0.5, 1.5)
                )
                logger.warning(
                    "Rate limited on {}: {}. Pausing {:.1f}s (attempt {}/{})",
                    self._exchange_name,
                    e,
                    wait,
                    consecutive_failures,
                    max_retries,
                )
                time.sleep(wait)

            except ccxt.NetworkError as e:
                consecutive_failures += 1
                if consecutive_failures >= max_retries:
                    raise NetworkError(f"Network error after {max_retries} retries: {e}") from e
                wait = (
                    self._rate_limit_pause
                    * (2 ** (consecutive_failures - 1))
                    * random.uniform(0.5, 1.5)
                )
                logger.warning(
                    "Network error on {} (attempt {}/{}): {}. Retrying in {:.1f}s",
                    self._exchange_name,
                    consecutive_failures,
                    max_retries,
                    e,
                    wait,
                )
                time.sleep(wait)

            except ccxt.ExchangeError as e:
                raise DownloadError(
                    f"Exchange error for {symbol} on {self._exchange_name}: {e}"
                ) from e

        logger.info("Download complete: {} candles for {}", len(all_ohlcv), symbol)

        if not all_ohlcv:
            return pd.DataFrame()

        df = pd.DataFrame(
            all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

        if not df.empty and end:
            df = df[df["timestamp"] <= pd.to_datetime(end, utc=True)]

        return df

    @override
    def get_metadata(self, symbol: str) -> dict[str, Any]:
        """Return crypto asset metadata from exchange market info."""
        try:
            if not self._markets_loaded:
                self.exchange.load_markets()
                self._markets_loaded = True
            market = self.exchange.market(symbol)
            return {
                "asset_type": "crypto",
                "base_currency": market.get("base", "UNKNOWN"),
                "quote_currency": market.get("quote", "UNKNOWN"),
                "description": f"{self._exchange_name.capitalize()} {symbol} Spot Market",
            }
        except ccxt.BaseError as e:
            logger.warning(
                "Failed to fetch metadata for {} on {}: {}",
                symbol,
                self._exchange_name,
                e,
            )
            return {
                "asset_type": "crypto",
                "base_currency": "UNKNOWN",
                "quote_currency": "UNKNOWN",
                "description": f"Unknown {symbol} on {self._exchange_name}",
            }
