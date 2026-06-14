from unittest.mock import MagicMock

import pandas as pd

from src.exceptions import DatabaseError
from src.services.integrity import IntegrityService


def test_find_gaps_with_known_gap():
    mock_repo = MagicMock()
    # 1m data with a 5-minute gap between row 2 and 3
    mock_repo.get_candles.return_value = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01 00:00",
                    "2024-01-01 00:01",
                    "2024-01-01 00:06",  # 5-min gap (missing 3 candles)
                    "2024-01-01 00:07",
                ],
                utc=True,
            ),
            "open": [100, 101, 102, 103],
            "high": [101, 102, 103, 104],
            "low": [99, 100, 101, 102],
            "close": [100.5, 101.5, 102.5, 103.5],
            "volume": [10, 11, 12, 13],
        }
    )

    service = IntegrityService(mock_repo)
    gaps = service.find_gaps("BTC/USDT", "binance", "1m")

    assert len(gaps) == 1
    assert gaps[0].missing_candles == 4


def test_find_gaps_no_gaps():
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-01-01 00:00", "2024-01-01 00:01", "2024-01-01 00:02"], utc=True
            ),
            "open": [100, 101, 102],
            "high": [101, 102, 103],
            "low": [99, 100, 101],
            "close": [100.5, 101.5, 102.5],
            "volume": [10, 11, 12],
        }
    )

    service = IntegrityService(mock_repo)
    gaps = service.find_gaps("BTC/USDT", "binance", "1m")

    assert len(gaps) == 0


def test_find_gaps_empty_data():
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame()

    service = IntegrityService(mock_repo)
    gaps = service.find_gaps("BTC/USDT", "binance", "1m")

    assert gaps == []


def test_find_anomalies_ohlc_violation():
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01 00:00"], utc=True),
            "open": [100],
            "high": [95],  # high < low = violation
            "low": [99],
            "close": [100],
            "volume": [10],
        }
    )

    service = IntegrityService(mock_repo)
    anomalies = service.find_anomalies("BTC/USDT", "binance", "1m")

    types = [a.anomaly_type for a in anomalies]
    assert "ohlc_violation" in types


def test_find_anomalies_zero_volume():
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01 00:00"], utc=True),
            "open": [100],
            "high": [101],
            "low": [99],
            "close": [100],
            "volume": [0],
        }
    )

    service = IntegrityService(mock_repo)
    anomalies = service.find_anomalies("BTC/USDT", "binance", "1m")

    types = [a.anomaly_type for a in anomalies]
    assert "zero_volume" in types


def test_find_anomalies_price_spike():
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:01"], utc=True),
            "open": [100, 200],
            "high": [101, 201],
            "low": [99, 199],
            "close": [100, 200],  # 100% jump
            "volume": [10, 10],
        }
    )

    service = IntegrityService(mock_repo)
    anomalies = service.find_anomalies("BTC/USDT", "binance", "1m")

    types = [a.anomaly_type for a in anomalies]
    assert "price_spike" in types


def test_find_anomalies_empty_data():
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame()

    service = IntegrityService(mock_repo)
    anomalies = service.find_anomalies("BTC/USDT", "binance", "1m")

    assert anomalies == []


def test_check_health_connected():
    mock_repo = MagicMock()
    mock_repo.count_candles.return_value = 1000
    mock_repo.get_symbols.return_value = pd.DataFrame({"symbol": ["BTC/USDT", "ETH/USDT"]})

    service = IntegrityService(mock_repo)
    report = service.check_health()

    assert report.connected is True
    assert report.tables_exist is True
    assert report.total_rows == 1000
    assert report.symbol_count == 2


def test_check_health_not_connected():
    mock_repo = MagicMock()
    mock_repo.count_candles.side_effect = DatabaseError("connection refused")

    service = IntegrityService(mock_repo)
    report = service.check_health()

    assert report.connected is False
    assert "connection refused" in report.errors[0]


def test_find_gaps_unknown_timeframe():
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01 00:00", "2024-01-01 01:00"], utc=True),
            "open": [100, 101],
            "high": [101, 102],
            "low": [99, 100],
            "close": [100, 101],
            "volume": [10, 11],
        }
    )

    service = IntegrityService(mock_repo)
    gaps = service.find_gaps("BTC/USDT", "binance", "99x")

    assert gaps == []


def test_find_anomalies_duplicates():
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-01-01 00:00", "2024-01-01 00:00", "2024-01-01 00:01"], utc=True
            ),
            "open": [100, 100, 101],
            "high": [101, 101, 102],
            "low": [99, 99, 100],
            "close": [100, 100, 101],
            "volume": [10, 10, 11],
        }
    )

    service = IntegrityService(mock_repo)
    anomalies = service.find_anomalies("BTC/USDT", "binance", "1m")

    types = [a.anomaly_type for a in anomalies]
    assert "duplicate" in types


def test_check_health_symbol_query_fails():
    mock_repo = MagicMock()
    mock_repo.count_candles.return_value = 500
    mock_repo.get_symbols.side_effect = DatabaseError("symbol query failed")

    service = IntegrityService(mock_repo)
    report = service.check_health()

    assert report.connected is True
    assert report.total_rows == 500
    assert report.symbol_count == 0
