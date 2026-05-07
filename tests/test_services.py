from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.exceptions import DownloadError
from src.services.downloader import DownloadService


def test_download_service():
    mock_repo = MagicMock()
    mock_repo.insert_candles.return_value = 1
    mock_repo.batch.return_value.__enter__ = MagicMock(return_value=None)
    mock_repo.batch.return_value.__exit__ = MagicMock(return_value=False)

    mock_source = MagicMock()
    mock_source.download.return_value = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2024-01-01T00:00:00Z")],
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [102.0],
            "volume": [10.0],
        }
    )

    sources = {"binance": mock_source}
    service = DownloadService(mock_repo, sources)

    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 1, 0, 1)

    inserted = service.download("BTCUSDT", "binance", "1m", start, end)

    assert inserted == 1
    mock_repo.insert_candles.assert_called_once()
    mock_repo.log_download.assert_called_once()


def test_download_registers_asset():
    mock_repo = MagicMock()
    mock_repo.batch.return_value.__enter__ = MagicMock(return_value=None)
    mock_repo.batch.return_value.__exit__ = MagicMock(return_value=False)
    mock_source = MagicMock()

    mock_source.download.return_value = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2024-01-01T00:00:00Z")],
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [102.0],
            "volume": [10.0],
        }
    )
    mock_source.get_metadata.return_value = {
        "asset_type": "crypto",
        "base_currency": "BTC",
        "quote_currency": "USDT",
        "description": "Test Asset",
    }

    service = DownloadService(mock_repo, {"binance": mock_source})
    service.download("BTCUSDT", "binance", "1m", datetime(2024, 1, 1), datetime(2024, 1, 2))

    mock_source.get_metadata.assert_called_once_with("BTCUSDT")
    mock_repo.register_asset.assert_called_once_with(
        symbol="BTCUSDT",
        exchange="binance",
        asset_type="crypto",
        base_currency="BTC",
        quote_currency="USDT",
        description="Test Asset",
    )


def test_download_unsupported_exchange():
    mock_repo = MagicMock()
    service = DownloadService(mock_repo, {"binance": MagicMock()})

    with pytest.raises(DownloadError, match="Unsupported exchange"):
        service.download("BTC/USDT", "kraken", "1m", datetime(2024, 1, 1), datetime(2024, 1, 2))


def test_download_empty_data():
    mock_repo = MagicMock()
    mock_source = MagicMock()
    mock_source.download.return_value = pd.DataFrame()

    service = DownloadService(mock_repo, {"binance": mock_source})
    result = service.download(
        "BTC/USDT", "binance", "1m", datetime(2024, 1, 1), datetime(2024, 1, 2)
    )

    assert result == 0
    mock_repo.insert_candles.assert_not_called()


def test_download_future_timestamps_rejected():
    mock_repo = MagicMock()
    mock_repo.batch.return_value.__enter__ = MagicMock(return_value=None)
    mock_repo.batch.return_value.__exit__ = MagicMock(return_value=False)
    mock_source = MagicMock()

    future = pd.Timestamp.now("UTC") + pd.Timedelta(days=10)
    mock_source.download.return_value = pd.DataFrame(
        {
            "timestamp": [future],
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [102.0],
            "volume": [10.0],
        }
    )

    service = DownloadService(mock_repo, {"binance": mock_source})
    result = service.download(
        "BTC/USDT", "binance", "1m", datetime(2024, 1, 1), datetime(2024, 12, 31)
    )

    assert result == 0
    mock_repo.insert_candles.assert_not_called()


def test_download_metadata_failure_continues():
    mock_repo = MagicMock()
    mock_repo.batch.return_value.__enter__ = MagicMock(return_value=None)
    mock_repo.batch.return_value.__exit__ = MagicMock(return_value=False)
    mock_repo.insert_candles.return_value = 1
    mock_source = MagicMock()

    mock_source.download.return_value = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2024-01-01T00:00:00Z")],
            "open": [100.0],
            "high": [105.0],
            "low": [95.0],
            "close": [102.0],
            "volume": [10.0],
        }
    )
    mock_source.get_metadata.side_effect = KeyError("missing field")

    service = DownloadService(mock_repo, {"binance": mock_source})
    result = service.download(
        "BTC/USDT", "binance", "1m", datetime(2024, 1, 1), datetime(2024, 1, 2)
    )

    assert result == 1
    mock_repo.insert_candles.assert_called_once()
    mock_repo.register_asset.assert_not_called()
