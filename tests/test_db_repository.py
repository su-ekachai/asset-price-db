from datetime import UTC, datetime

import pandas as pd


class TestInsertCandles:
    def test_inserts_with_metadata_columns(self, mock_repo, sample_ohlcv_df):
        rows = mock_repo.insert_candles(sample_ohlcv_df, "BTC/USDT", "binance", "1m")

        assert rows == 3
        mock_repo._writer.insert_dataframe.assert_called_once()
        _, kwargs = mock_repo._writer.insert_dataframe.call_args
        df_sent = kwargs["df"]
        assert "symbol" in df_sent.columns
        assert "exchange" in df_sent.columns
        assert "timeframe" in df_sent.columns
        assert kwargs["table_name"] == "ohlcv"
        assert kwargs["symbols"] == ["symbol", "exchange", "timeframe"]
        assert kwargs["at"] == "timestamp"

    def test_empty_dataframe_returns_zero(self, mock_repo):
        rows = mock_repo.insert_candles(pd.DataFrame(), "BTC/USDT", "binance", "1m")

        assert rows == 0
        mock_repo._writer.insert_dataframe.assert_not_called()

    def test_strips_timezone_and_converts_units(self, mock_repo):
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2024-01-01T12:00:00+00:00"]),
                "open": [100.0],
                "high": [105.0],
                "low": [95.0],
                "close": [102.0],
                "volume": [10.0],
            }
        )

        mock_repo.insert_candles(df, "BTC/USDT", "binance", "1m")

        _, kwargs = mock_repo._writer.insert_dataframe.call_args
        ts = kwargs["df"]["timestamp"].iloc[0]
        assert ts.tzinfo is None

    def test_drops_future_timestamps_keeps_valid_rows(self, mock_repo):
        future = pd.Timestamp.now("UTC") + pd.Timedelta(days=10)
        df = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01", tz="UTC"), future],
                "open": [100.0, 200.0],
                "high": [105.0, 205.0],
                "low": [95.0, 195.0],
                "close": [102.0, 202.0],
                "volume": [10.0, 20.0],
            }
        )

        rows = mock_repo.insert_candles(df, "BTC/USDT", "binance", "1m")

        assert rows == 1
        _, kwargs = mock_repo._writer.insert_dataframe.call_args
        assert len(kwargs["df"]) == 1

    def test_all_future_timestamps_returns_zero(self, mock_repo):
        future = pd.Timestamp.now("UTC") + pd.Timedelta(days=10)
        df = pd.DataFrame(
            {
                "timestamp": [future],
                "open": [100.0],
                "high": [105.0],
                "low": [95.0],
                "close": [102.0],
                "volume": [10.0],
            }
        )

        rows = mock_repo.insert_candles(df, "BTC/USDT", "binance", "1m")

        assert rows == 0
        mock_repo._writer.insert_dataframe.assert_not_called()


class TestLogDownload:
    def test_logs_download_metadata(self, mock_repo):
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 2, tzinfo=UTC)

        mock_repo.log_download("BTC/USDT", "binance", "1m", start, end, 1000)

        mock_repo._writer.insert_row.assert_called_once()
        _, kwargs = mock_repo._writer.insert_row.call_args
        assert kwargs["table_name"] == "download_log"
        assert kwargs["symbols"]["symbol"] == "BTC/USDT"
        assert kwargs["symbols"]["exchange"] == "binance"
        assert kwargs["symbols"]["timeframe"] == "1m"
        assert kwargs["columns"]["start_time"] == start
        assert kwargs["columns"]["end_time"] == end
        assert kwargs["columns"]["rows_inserted"] == 1000


class TestGetLastTimestamp:
    def test_returns_timestamp_when_exists(self, mock_repo):
        ts = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)
        mock_repo._reader.query.return_value = [(ts,)]

        result = mock_repo.get_last_timestamp("BTC/USDT", "binance", "1m")

        assert result == ts
        mock_repo._reader.query.assert_called_once()

    def test_returns_none_when_no_data(self, mock_repo):
        mock_repo._reader.query.return_value = [(None,)]

        result = mock_repo.get_last_timestamp("BTC/USDT", "binance", "1m")

        assert result is None

    def test_returns_none_when_empty_result(self, mock_repo):
        mock_repo._reader.query.return_value = []

        result = mock_repo.get_last_timestamp("BTC/USDT", "binance", "1m")

        assert result is None

    def test_adds_utc_if_naive_timestamp(self, mock_repo):
        naive_ts = datetime(2024, 6, 15, 12, 0)
        mock_repo._reader.query.return_value = [(naive_ts,)]

        result = mock_repo.get_last_timestamp("BTC/USDT", "binance", "1m")

        assert result is not None
        assert result.tzinfo == UTC


class TestGetCandles:
    def test_basic_query(self, mock_repo):
        expected = pd.DataFrame({"timestamp": ["2024-01-01"], "close": [100.0]})
        mock_repo._reader.query_df.return_value = expected

        result = mock_repo.get_candles("BTC/USDT", "binance", "1m")

        assert result.equals(expected)
        sql_arg = mock_repo._reader.query_df.call_args[0][0]
        assert "WHERE symbol = %s AND exchange = %s AND timeframe = %s" in sql_arg

    def test_with_start_date(self, mock_repo):
        mock_repo._reader.query_df.return_value = pd.DataFrame()
        start = datetime(2024, 1, 1, tzinfo=UTC)

        mock_repo.get_candles("BTC/USDT", "binance", "1m", start=start)

        sql_arg = mock_repo._reader.query_df.call_args[0][0]
        params = mock_repo._reader.query_df.call_args[0][1]
        assert "AND timestamp >= %s" in sql_arg
        assert start in params

    def test_with_end_date(self, mock_repo):
        mock_repo._reader.query_df.return_value = pd.DataFrame()
        end = datetime(2024, 6, 1, tzinfo=UTC)

        mock_repo.get_candles("BTC/USDT", "binance", "1m", end=end)

        sql_arg = mock_repo._reader.query_df.call_args[0][0]
        params = mock_repo._reader.query_df.call_args[0][1]
        assert "AND timestamp <= %s" in sql_arg
        assert end in params

    def test_with_limit(self, mock_repo):
        mock_repo._reader.query_df.return_value = pd.DataFrame()

        mock_repo.get_candles("BTC/USDT", "binance", "1m", limit=500)

        sql_arg = mock_repo._reader.query_df.call_args[0][0]
        params = mock_repo._reader.query_df.call_args[0][1]
        assert "LIMIT %s" in sql_arg
        assert 500 in params

    def test_with_all_filters(self, mock_repo):
        mock_repo._reader.query_df.return_value = pd.DataFrame()
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 6, 1, tzinfo=UTC)

        mock_repo.get_candles("BTC/USDT", "binance", "1m", start=start, end=end, limit=100)

        sql_arg = mock_repo._reader.query_df.call_args[0][0]
        assert "AND timestamp >= %s" in sql_arg
        assert "AND timestamp <= %s" in sql_arg
        assert "LIMIT %s" in sql_arg
        assert "ORDER BY timestamp" in sql_arg


class TestGetSymbols:
    def test_returns_symbol_summary(self, mock_repo):
        expected = pd.DataFrame(
            {
                "symbol": ["BTC/USDT"],
                "exchange": ["binance"],
                "timeframe": ["1m"],
                "rows": [5000],
                "last_update": [datetime(2024, 6, 1, tzinfo=UTC)],
            }
        )
        mock_repo._reader.query_df.return_value = expected

        result = mock_repo.get_symbols()

        assert len(result) == 1
        assert result.iloc[0]["symbol"] == "BTC/USDT"


class TestRegisterAsset:
    def test_inserts_asset_metadata(self, mock_repo):
        mock_repo.register_asset("BTC/USDT", "binance", "crypto", "BTC", "USDT", "Bitcoin")

        mock_repo._writer.insert_row.assert_called_once()
        _, kwargs = mock_repo._writer.insert_row.call_args
        assert kwargs["table_name"] == "assets"
        assert kwargs["symbols"]["symbol"] == "BTC/USDT"
        assert kwargs["symbols"]["asset_type"] == "crypto"
        assert kwargs["columns"]["description"] == "Bitcoin"

    def test_defaults_unknown_for_none_values(self, mock_repo):
        mock_repo.register_asset("BTC/USDT", "binance", "crypto", None, None, None)

        _, kwargs = mock_repo._writer.insert_row.call_args
        assert kwargs["symbols"]["base_currency"] == "UNKNOWN"
        assert kwargs["symbols"]["quote_currency"] == "UNKNOWN"
        assert kwargs["columns"]["description"] == ""


class TestBatch:
    def test_delegates_to_writer(self, mock_repo):
        with mock_repo.batch():
            pass

        mock_repo._writer.batch.assert_called_once()
