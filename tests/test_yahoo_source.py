from datetime import UTC, datetime

import pandas as pd
import pytest
from yfinance.exceptions import YFPricesMissingError, YFTzMissingError

from src.exceptions import DownloadError
from src.sources.yahoo import YahooSource


def _history_frame() -> pd.DataFrame:
    """DataFrame shaped like yfinance Ticker.history(): tz-aware DatetimeIndex + OHLCV."""
    index = pd.DatetimeIndex(
        [
            pd.Timestamp("2024-01-02", tz="America/New_York"),
            pd.Timestamp("2024-01-03", tz="America/New_York"),
        ],
        name="Date",
    )
    return pd.DataFrame(
        {
            "Open": [185.0, 186.0],
            "High": [186.0, 187.0],
            "Low": [184.0, 185.0],
            "Close": [185.5, 186.5],
            "Volume": [1000000, 1100000],
        },
        index=index,
    )


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
    assert source.validate_symbol("BRK-B") is True
    assert source.validate_symbol("^GSPC") is True
    assert source.validate_symbol("EURUSD=X") is True
    assert source.validate_symbol("GC=F") is True
    assert source.validate_symbol("7203.T") is True
    assert source.validate_symbol("BTC/USDT") is False
    assert source.validate_symbol("") is False


def test_yahoo_download(mocker):
    mock_ticker_cls = mocker.patch("src.sources.yahoo.yf.Ticker")
    mock_ticker_cls.return_value.history.return_value = _history_frame()

    source = YahooSource()
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 4, tzinfo=UTC)

    df = source.download("AAPL", "1d", start, end)

    assert not df.empty
    assert len(df) == 2
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df.iloc[0]["open"] == 185.0
    assert df["timestamp"].dt.tz is not None  # normalized to UTC
    mock_ticker_cls.return_value.history.assert_called_once_with(
        start="2024-01-01",
        end="2024-01-04",
        interval="1d",
        auto_adjust=True,
        actions=False,
        raise_errors=True,
    )


def test_yahoo_download_flattens_multiindex_columns(mocker):
    """yf.download-style frames carry (field, ticker) MultiIndex columns."""
    frame = _history_frame().reset_index()
    frame.columns = pd.MultiIndex.from_tuples((c, "AAPL") for c in frame.columns)
    mocker.patch.object(YahooSource, "_fetch_yfinance", return_value=frame)

    source = YahooSource()
    df = source.download(
        "AAPL",
        "1d",
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 4, tzinfo=UTC),
    )

    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 2


def test_yahoo_download_no_prices_returns_empty(mocker):
    """YFPricesMissingError (e.g. weekend/holiday range) is benign no-data, not a failure."""
    mock_ticker_cls = mocker.patch("src.sources.yahoo.yf.Ticker")
    mock_ticker_cls.return_value.history.side_effect = YFPricesMissingError("AAPL", "no data")

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
    """yfinance errors surface as DownloadError so sync reports 'failed', not 'skipped'."""
    mock_ticker_cls = mocker.patch("src.sources.yahoo.yf.Ticker")
    mock_ticker_cls.return_value.history.side_effect = YFTzMissingError("BADTICKER")

    source = YahooSource()
    with pytest.raises(DownloadError, match="Yahoo Finance download failed"):
        source.download(
            "BADTICKER",
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
