from datetime import UTC, datetime

import pandas as pd
import pytest

from src.exceptions import DownloadError
from src.sources.yahoo import YahooSource


def test_yahoo_supported_timeframes():
    source = YahooSource()
    tf = source.supported_timeframes()
    assert "1d" in tf
    assert "1wk" in tf
    assert "1mo" in tf
    assert "1m" not in tf


def test_yahoo_validate_symbol():
    source = YahooSource()
    assert source.validate_symbol("AAPL") is True
    assert source.validate_symbol("MSFT") is True
    assert source.validate_symbol("BTC/USDT") is False
    assert source.validate_symbol("AAPL.X") is False


def test_yahoo_download(mocker):
    mock_yf = mocker.patch("src.sources.yahoo.yf.download")
    mock_yf.return_value = pd.DataFrame(
        {
            "Date": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")],
            "Open": [185.0, 186.0],
            "High": [186.0, 187.0],
            "Low": [184.0, 185.0],
            "Close": [185.5, 186.5],
            "Volume": [1000000, 1100000],
        }
    )

    source = YahooSource()
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 4, tzinfo=UTC)

    df = source.download("AAPL", "1d", start, end)

    assert not df.empty
    assert len(df) == 2
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df.iloc[0]["open"] == 185.0


def test_yahoo_download_empty(mocker):
    mock_yf = mocker.patch("src.sources.yahoo.yf.download")
    mock_yf.return_value = pd.DataFrame()

    source = YahooSource()
    df = source.download(
        "AAPL",
        "1d",
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 2, tzinfo=UTC),
    )

    assert df.empty


def test_yahoo_download_unsupported_timeframe():
    source = YahooSource()
    with pytest.raises(DownloadError, match="does not support timeframe"):
        source.download(
            "AAPL",
            "1m",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 2, tzinfo=UTC),
        )


def test_yahoo_download_exception(mocker):
    mock_yf = mocker.patch("src.sources.yahoo.yf.download")
    mock_yf.side_effect = ConnectionError("network error")

    source = YahooSource()
    with pytest.raises(DownloadError, match="Yahoo Finance download failed"):
        source.download(
            "AAPL",
            "1d",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 2, tzinfo=UTC),
        )


def test_yahoo_get_metadata(mocker):
    mock_ticker_cls = mocker.patch("src.sources.yahoo.yf.Ticker")
    mock_ticker = mock_ticker_cls.return_value
    mock_ticker.info = {
        "quoteType": "EQUITY",
        "currency": "USD",
        "longName": "Apple Inc.",
    }

    source = YahooSource()
    meta = source.get_metadata("AAPL")

    assert meta["asset_type"] == "equity"
    assert meta["base_currency"] == "AAPL"
    assert meta["quote_currency"] == "USD"
    assert "Apple Inc." in meta["description"]


def test_yahoo_get_metadata_fallback(mocker):
    mock_ticker_cls = mocker.patch("src.sources.yahoo.yf.Ticker")
    mock_ticker_cls.side_effect = ValueError("API error")

    source = YahooSource()
    meta = source.get_metadata("AAPL")

    assert meta["asset_type"] == "equity"
    assert meta["quote_currency"] == "USD"
