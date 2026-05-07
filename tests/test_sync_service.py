from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd

from src.services.sync import SyncService
from src.watchlist import WatchlistEntry


def _make_entry(**kwargs) -> WatchlistEntry:
    defaults = {
        "symbol": "BTC/USDT",
        "exchange": "binance",
        "timeframe": "1m",
        "lookback": "30d",
    }
    defaults.update(kwargs)
    return WatchlistEntry(**defaults)


def test_sync_symbol_no_existing_data(mocker):
    mock_repo = MagicMock()
    mock_repo.get_last_timestamp.return_value = None

    mock_source = MagicMock()
    mock_source.download.return_value = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2024-01-01", tz="UTC")],
            "open": [42000.0],
            "high": [42100.0],
            "low": [41900.0],
            "close": [42050.0],
            "volume": [1.5],
        }
    )
    mocker.patch("src.services.sync.create_source", return_value=mock_source)

    mock_repo.insert_candles.return_value = 1
    mock_repo.batch.return_value.__enter__ = MagicMock()
    mock_repo.batch.return_value.__exit__ = MagicMock(return_value=False)

    service = SyncService(mock_repo)
    entry = _make_entry()
    result = service.sync_symbol(entry)

    assert result.status == "synced"
    assert result.rows_inserted == 1
    mock_source.download.assert_called_once()


def test_sync_symbol_already_up_to_date(mocker):
    mock_repo = MagicMock()
    future = datetime.now(UTC) + timedelta(hours=1)
    mock_repo.get_last_timestamp.return_value = future

    mocker.patch("src.services.sync.create_source", return_value=MagicMock())

    service = SyncService(mock_repo)
    entry = _make_entry()
    result = service.sync_symbol(entry)

    assert result.status == "skipped"
    assert result.message == "Already up to date"


def test_sync_symbol_dry_run(mocker):
    mock_repo = MagicMock()
    mock_repo.get_last_timestamp.return_value = None

    mocker.patch("src.services.sync.create_source", return_value=MagicMock())

    service = SyncService(mock_repo)
    entry = _make_entry()
    result = service.sync_symbol(entry, dry_run=True)

    assert result.status == "dry_run"
    assert "Would download" in result.message


def test_sync_symbol_download_error(mocker):
    mock_repo = MagicMock()
    mock_repo.get_last_timestamp.return_value = None

    mock_source = MagicMock()
    mock_source.download.side_effect = Exception("connection timeout")
    mocker.patch("src.services.sync.create_source", return_value=mock_source)

    service = SyncService(mock_repo)
    entry = _make_entry()
    result = service.sync_symbol(entry)

    assert result.status == "failed"
    assert "connection timeout" in result.message


def test_sync_symbol_empty_download(mocker):
    mock_repo = MagicMock()
    mock_repo.get_last_timestamp.return_value = None

    mock_source = MagicMock()
    mock_source.download.return_value = pd.DataFrame()
    mocker.patch("src.services.sync.create_source", return_value=mock_source)

    service = SyncService(mock_repo)
    entry = _make_entry()
    result = service.sync_symbol(entry)

    assert result.status == "skipped"
    assert result.message == "No new data available"


def test_sync_all(mocker):
    mock_repo = MagicMock()
    mock_repo.get_last_timestamp.return_value = None

    mock_source = MagicMock()
    mock_source.download.return_value = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2024-01-01", tz="UTC")],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [500.0],
        }
    )
    mocker.patch("src.services.sync.create_source", return_value=mock_source)

    mock_repo.insert_candles.return_value = 1
    mock_repo.batch.return_value.__enter__ = MagicMock()
    mock_repo.batch.return_value.__exit__ = MagicMock(return_value=False)

    service = SyncService(mock_repo)
    entries = [_make_entry(symbol="BTC/USDT"), _make_entry(symbol="ETH/USDT")]
    results = service.sync_all(entries)

    assert len(results) == 2
    assert all(r.status == "synced" for r in results)
