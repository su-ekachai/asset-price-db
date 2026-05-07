import pathlib
import re
from dataclasses import dataclass

import yaml
from loguru import logger

from src.exceptions import ConfigurationError


@dataclass(kw_only=True)
class WatchlistEntry:
    """Single symbol configuration from symbols.yaml."""

    symbol: str
    exchange: str
    timeframe: str
    lookback: str = "30d"


@dataclass(kw_only=True)
class Watchlist:
    """Parsed watchlist containing all symbol configurations."""

    symbols: list[WatchlistEntry]


_LOOKBACK_PATTERN = re.compile(r"^(\d+)(d|w|mo|y)$")

LOOKBACK_TO_DAYS = {
    "d": 1,
    "w": 7,
    "mo": 30,
    "y": 365,
}


def parse_lookback_days(lookback: str) -> int:
    """Parse a lookback string like '30d', '2w', '6mo', '1y' into days."""
    match = _LOOKBACK_PATTERN.match(lookback)
    if not match:
        raise ConfigurationError(
            f"Invalid lookback format '{lookback}'. "
            "Use Nd, Nw, Nmo, or Ny (e.g., '30d', '2w', '6mo', '1y')."
        )
    amount = int(match.group(1))
    unit = match.group(2)
    return amount * LOOKBACK_TO_DAYS[unit]


def load_watchlist(path: str | pathlib.Path = "symbols.yaml") -> Watchlist:
    """Load and validate watchlist from YAML file."""
    logger.debug("Loading watchlist from {}", path)
    file_path = pathlib.Path(path)
    if not file_path.exists():
        raise ConfigurationError(f"Watchlist file not found: {file_path}")

    with file_path.open("r") as f:
        data = yaml.safe_load(f)

    if not data or "symbols" not in data:
        raise ConfigurationError("Watchlist YAML must contain a 'symbols' key.")

    entries: list[WatchlistEntry] = []
    for i, item in enumerate(data["symbols"]):
        if not isinstance(item, dict):
            raise ConfigurationError(f"Entry {i} must be a mapping.")

        symbol = item.get("symbol")
        exchange = item.get("exchange")
        timeframe = item.get("timeframe")

        if not symbol or not exchange or not timeframe:
            raise ConfigurationError(
                f"Entry {i} missing required fields (symbol, exchange, timeframe)."
            )

        lookback = item.get("lookback", "30d")
        parse_lookback_days(lookback)

        entries.append(
            WatchlistEntry(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                lookback=lookback,
            )
        )

    if not entries:
        raise ConfigurationError("Watchlist must contain at least one symbol.")

    logger.debug("Watchlist loaded: {} symbols", len(entries))
    return Watchlist(symbols=entries)
