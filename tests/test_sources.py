from datetime import datetime

import ccxt
import pytest

from src.exceptions import DownloadError, RateLimitError
from src.sources.ccxt_source import CcxtSource


def test_ccxt_source_download(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value

    mock_exchange_instance.fetch_ohlcv.side_effect = [
        [[1704067200000, 42000.0, 42100.0, 41900.0, 42050.0, 1.5]],
        [],
    ]

    source = CcxtSource(exchange_name="binance")
    start = datetime(2024, 1, 1)
    end = datetime(2024, 1, 2)

    df = source.download("BTC/USDT", "1m", start, end)

    assert not df.empty
    assert len(df) == 1
    assert df.iloc[0]["open"] == 42000.0
    mock_exchange_instance.fetch_ohlcv.assert_called()


def test_ccxt_source_download_empty(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value
    mock_exchange_instance.fetch_ohlcv.return_value = []

    source = CcxtSource(exchange_name="binance")
    df = source.download("BTC/USDT", "1m", datetime(2024, 1, 1), datetime(2024, 1, 2))

    assert df.empty


def test_ccxt_source_get_metadata(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value
    mock_exchange_instance.market.return_value = {
        "base": "BTC",
        "quote": "USDT",
    }

    source = CcxtSource(exchange_name="binance")
    meta = source.get_metadata("BTC/USDT")

    assert meta["asset_type"] == "crypto"
    assert meta["base_currency"] == "BTC"
    assert meta["quote_currency"] == "USDT"
    assert "BTC/USDT" in meta["description"]
    mock_exchange_instance.load_markets.assert_called_once()
    mock_exchange_instance.market.assert_called_with("BTC/USDT")


def test_ccxt_metadata_caches_markets(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value
    mock_exchange_instance.market.return_value = {"base": "BTC", "quote": "USDT"}

    source = CcxtSource(exchange_name="binance")
    source.get_metadata("BTC/USDT")
    source.get_metadata("ETH/USDT")

    mock_exchange_instance.load_markets.assert_called_once()


def test_ccxt_retries_on_rate_limit(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value
    mocker.patch("src.sources.ccxt_source.time.sleep")

    mock_exchange_instance.fetch_ohlcv.side_effect = [
        ccxt.RateLimitExceeded("rate limited"),
        [[1704067200000, 42000.0, 42100.0, 41900.0, 42050.0, 1.5]],
        [],
    ]

    source = CcxtSource(exchange_name="binance", rate_limit_pause=0.1)
    df = source.download("BTC/USDT", "1m", datetime(2024, 1, 1), datetime(2024, 1, 2))

    assert not df.empty
    assert len(df) == 1


def test_ccxt_raises_on_persistent_rate_limit(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value
    mocker.patch("src.sources.ccxt_source.time.sleep")

    mock_exchange_instance.fetch_ohlcv.side_effect = ccxt.RateLimitExceeded("rate limited")

    source = CcxtSource(exchange_name="binance", rate_limit_pause=0.1)
    with pytest.raises(RateLimitError):
        source.download("BTC/USDT", "1m", datetime(2024, 1, 1), datetime(2024, 1, 2))


def test_ccxt_retries_on_network_error(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value
    mocker.patch("src.sources.ccxt_source.time.sleep")

    mock_exchange_instance.fetch_ohlcv.side_effect = [
        ccxt.NetworkError("timeout"),
        [[1704067200000, 42000.0, 42100.0, 41900.0, 42050.0, 1.5]],
        [],
    ]

    source = CcxtSource(exchange_name="binance", rate_limit_pause=0.1)
    df = source.download("BTC/USDT", "1m", datetime(2024, 1, 1), datetime(2024, 1, 2))

    assert not df.empty


def test_ccxt_raises_on_exchange_error(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value

    mock_exchange_instance.fetch_ohlcv.side_effect = ccxt.ExchangeError("invalid symbol")

    source = CcxtSource(exchange_name="binance")
    with pytest.raises(DownloadError, match="Exchange error"):
        source.download("INVALID", "1m", datetime(2024, 1, 1), datetime(2024, 1, 2))


def test_ccxt_unknown_exchange():
    with pytest.raises(DownloadError, match="Unknown exchange"):
        CcxtSource(exchange_name="nonexistent_exchange_xyz")


def test_ccxt_supported_timeframes(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value
    mock_exchange_instance.timeframes = {"1m": "1m", "5m": "5m", "1h": "1h", "1d": "1d"}

    source = CcxtSource(exchange_name="binance")
    timeframes = source.supported_timeframes()

    assert "1m" in timeframes
    assert "1d" in timeframes


def test_ccxt_validate_symbol(mocker):
    mocker.patch("ccxt.binance")
    source = CcxtSource(exchange_name="binance")

    assert source.validate_symbol("BTC/USDT") is True
    assert source.validate_symbol("BTCUSDT") is False
    assert source.validate_symbol("AAPL") is False


def test_ccxt_get_metadata_fallback_on_error(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value
    mock_exchange_instance.load_markets.side_effect = ccxt.BaseError("API unavailable")

    source = CcxtSource(exchange_name="binance")
    meta = source.get_metadata("BTC/USDT")

    assert meta["asset_type"] == "crypto"
    assert meta["base_currency"] == "UNKNOWN"
    assert meta["quote_currency"] == "UNKNOWN"
    assert "Unknown" in meta["description"]


def test_ccxt_raises_on_persistent_network_error(mocker):
    mock_exchange_class = mocker.patch("ccxt.binance")
    mock_exchange_instance = mock_exchange_class.return_value
    mocker.patch("src.sources.ccxt_source.time.sleep")

    mock_exchange_instance.fetch_ohlcv.side_effect = ccxt.NetworkError("timeout")

    source = CcxtSource(exchange_name="binance", rate_limit_pause=0.1)

    from src.exceptions import NetworkError

    with pytest.raises(NetworkError):
        source.download("BTC/USDT", "1m", datetime(2024, 1, 1), datetime(2024, 1, 2))
