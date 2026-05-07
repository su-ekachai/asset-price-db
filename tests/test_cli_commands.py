"""CLI integration tests for sync, query, check, and status commands."""

from datetime import UTC
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.exceptions import DatabaseError, DownloadError


def _runner():
    return CliRunner()


# --- Sync command tests ---


@patch("src.cli.commands.sync.QuestDBWriter")
@patch("src.cli.commands.sync.QuestDBReader")
@patch("src.cli.commands.sync.OHLCVRepository")
@patch("src.cli.commands.sync.SyncService")
@patch("src.cli.commands.sync.load_watchlist")
def test_sync_command(mock_load, mock_service_cls, mock_repo, mock_reader, mock_writer):
    from src.services.sync import SyncResult
    from src.watchlist import Watchlist, WatchlistEntry

    mock_load.return_value = Watchlist(
        symbols=[WatchlistEntry(symbol="BTC/USDT", exchange="binance", timeframe="1m")]
    )

    mock_service = MagicMock()
    mock_service.sync_symbol.return_value = SyncResult(
        symbol="BTC/USDT",
        exchange="binance",
        timeframe="1m",
        rows_inserted=100,
        status="synced",
        duration=1.5,
    )
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["sync", "--watchlist", "symbols.yaml"])
    assert result.exit_code == 0
    assert "synced" in result.output


@patch("src.cli.commands.sync.QuestDBWriter")
@patch("src.cli.commands.sync.QuestDBReader")
@patch("src.cli.commands.sync.OHLCVRepository")
@patch("src.cli.commands.sync.SyncService")
@patch("src.cli.commands.sync.load_watchlist")
def test_sync_dry_run(mock_load, mock_service_cls, mock_repo, mock_reader, mock_writer):
    from src.services.sync import SyncResult
    from src.watchlist import Watchlist, WatchlistEntry

    mock_load.return_value = Watchlist(
        symbols=[WatchlistEntry(symbol="BTC/USDT", exchange="binance", timeframe="1m")]
    )

    mock_service = MagicMock()
    mock_service.sync_symbol.return_value = SyncResult(
        symbol="BTC/USDT",
        exchange="binance",
        timeframe="1m",
        rows_inserted=0,
        status="dry_run",
        duration=0.1,
        message="Would download from 2024-01-01 to now",
    )
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["sync", "--watchlist", "symbols.yaml", "--dry-run"])
    assert result.exit_code == 0
    assert "dry_run" in result.output


@patch("src.cli.commands.sync.QuestDBWriter")
@patch("src.cli.commands.sync.QuestDBReader")
@patch("src.cli.commands.sync.OHLCVRepository")
@patch("src.cli.commands.sync.SyncService")
@patch("src.cli.commands.sync.load_watchlist")
def test_sync_with_failures_exits_1(
    mock_load, mock_service_cls, mock_repo, mock_reader, mock_writer
):
    from src.services.sync import SyncResult
    from src.watchlist import Watchlist, WatchlistEntry

    mock_load.return_value = Watchlist(
        symbols=[WatchlistEntry(symbol="BTC/USDT", exchange="binance", timeframe="1m")]
    )

    mock_service = MagicMock()
    mock_service.sync_symbol.return_value = SyncResult(
        symbol="BTC/USDT",
        exchange="binance",
        timeframe="1m",
        rows_inserted=0,
        status="failed",
        duration=0.5,
        message="connection error",
    )
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["sync", "--watchlist", "symbols.yaml"])
    assert result.exit_code == 1


@patch("src.cli.commands.sync.load_watchlist")
def test_sync_missing_watchlist(mock_load):
    from src.exceptions import ConfigurationError

    mock_load.side_effect = ConfigurationError("Watchlist file not found: symbols.yaml")
    result = _runner().invoke(app, ["sync"])
    assert result.exit_code == 1
    assert "Watchlist file not found" in result.output
    assert "Hint" in result.output


@patch("src.cli.commands.sync.load_watchlist")
def test_sync_symbol_not_in_watchlist(mock_load):
    from src.watchlist import Watchlist, WatchlistEntry

    mock_load.return_value = Watchlist(
        symbols=[WatchlistEntry(symbol="BTC/USDT", exchange="binance", timeframe="1m")]
    )

    result = _runner().invoke(app, ["sync", "NONEXISTENT", "--watchlist", "symbols.yaml"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "None" in result.output


# --- Query command tests ---


@patch("src.cli.commands.query.QuestDBWriter")
@patch("src.cli.commands.query.QuestDBReader")
@patch("src.cli.commands.query.OHLCVRepository")
def test_query_list_mode(mock_repo_cls, mock_reader, mock_writer):
    mock_repo = MagicMock()
    mock_repo.get_symbols.return_value = pd.DataFrame(
        {
            "symbol": ["BTC/USDT"],
            "exchange": ["binance"],
            "timeframe": ["1m"],
            "rows": [1000],
            "last_update": ["2024-01-01 00:00:00"],
        }
    )
    mock_repo_cls.return_value = mock_repo

    result = _runner().invoke(app, ["query", "--list"])
    assert result.exit_code == 0
    assert "BTC/USDT" in result.output


@patch("src.cli.commands.query.QuestDBWriter")
@patch("src.cli.commands.query.QuestDBReader")
@patch("src.cli.commands.query.OHLCVRepository")
def test_query_list_empty(mock_repo_cls, mock_reader, mock_writer):
    mock_repo = MagicMock()
    mock_repo.get_symbols.return_value = pd.DataFrame()
    mock_repo_cls.return_value = mock_repo

    result = _runner().invoke(app, ["query", "--list"])
    assert result.exit_code != 0
    assert "No data" in result.output


@patch("src.cli.commands.query.export_dataframe")
@patch("src.cli.commands.query.QuestDBWriter")
@patch("src.cli.commands.query.QuestDBReader")
@patch("src.cli.commands.query.OHLCVRepository")
def test_query_symbol(mock_repo_cls, mock_reader, mock_writer, mock_export):
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame(
        {
            "timestamp": ["2024-01-01 00:00"],
            "open": [100],
            "high": [101],
            "low": [99],
            "close": [100],
            "volume": [10],
        }
    )
    mock_repo_cls.return_value = mock_repo

    result = _runner().invoke(
        app, ["query", "BTC/USDT", "--start", "2024-01-01", "--format", "csv"]
    )
    assert result.exit_code == 0
    mock_export.assert_called_once()


@patch("src.cli.commands.query.QuestDBWriter")
@patch("src.cli.commands.query.QuestDBReader")
@patch("src.cli.commands.query.OHLCVRepository")
def test_query_no_data(mock_repo_cls, mock_reader, mock_writer):
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame()
    mock_repo_cls.return_value = mock_repo

    result = _runner().invoke(app, ["query", "BTC/USDT"])
    assert result.exit_code != 0
    assert "No data found" in result.output


def test_query_no_symbol():
    result = _runner().invoke(app, ["query"])
    assert result.exit_code != 0


# --- Check command tests ---


@patch("src.cli.commands.check.QuestDBWriter")
@patch("src.cli.commands.check.QuestDBReader")
@patch("src.cli.commands.check.OHLCVRepository")
@patch("src.cli.commands.check.IntegrityService")
def test_check_gaps_none(mock_service_cls, mock_repo, mock_reader, mock_writer):
    mock_service = MagicMock()
    mock_service.find_gaps.return_value = []
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["check", "gaps", "BTC/USDT"])
    assert result.exit_code == 0
    assert "No gaps" in result.output


@patch("src.cli.commands.check.QuestDBWriter")
@patch("src.cli.commands.check.QuestDBReader")
@patch("src.cli.commands.check.OHLCVRepository")
@patch("src.cli.commands.check.IntegrityService")
def test_check_gaps_found(mock_service_cls, mock_repo, mock_reader, mock_writer):
    from datetime import datetime

    from src.services.integrity import Gap

    mock_service = MagicMock()
    mock_service.find_gaps.return_value = [
        Gap(
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 1, 0, 5, tzinfo=UTC),
            missing_candles=4,
        )
    ]
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["check", "gaps", "BTC/USDT"])
    assert result.exit_code == 0
    assert "4" in result.output


@patch("src.cli.commands.check.QuestDBWriter")
@patch("src.cli.commands.check.QuestDBReader")
@patch("src.cli.commands.check.OHLCVRepository")
@patch("src.cli.commands.check.IntegrityService")
def test_check_anomalies_none(mock_service_cls, mock_repo, mock_reader, mock_writer):
    mock_service = MagicMock()
    mock_service.find_anomalies.return_value = []
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["check", "anomalies", "BTC/USDT"])
    assert result.exit_code == 0
    assert "No anomalies" in result.output


@patch("src.cli.commands.check.QuestDBWriter")
@patch("src.cli.commands.check.QuestDBReader")
@patch("src.cli.commands.check.OHLCVRepository")
@patch("src.cli.commands.check.IntegrityService")
def test_check_health_ok(mock_service_cls, mock_repo, mock_reader, mock_writer):
    from src.services.integrity import HealthReport

    mock_service = MagicMock()
    mock_service.check_health.return_value = HealthReport(
        connected=True, tables_exist=True, total_rows=5000, symbol_count=3
    )
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["check", "health"])
    assert result.exit_code == 0
    assert "Connected" in result.output


@patch("src.cli.commands.check.QuestDBWriter")
@patch("src.cli.commands.check.QuestDBReader")
@patch("src.cli.commands.check.OHLCVRepository")
@patch("src.cli.commands.check.IntegrityService")
def test_check_health_failed(mock_service_cls, mock_repo, mock_reader, mock_writer):
    from src.services.integrity import HealthReport

    mock_service = MagicMock()
    mock_service.check_health.return_value = HealthReport(
        connected=False, tables_exist=False, errors=["connection refused"]
    )
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["check", "health"])
    assert result.exit_code == 1


# --- Status command tests ---


@patch("src.cli.commands.status.QuestDBWriter")
@patch("src.cli.commands.status.QuestDBReader")
@patch("src.cli.commands.status.OHLCVRepository")
def test_status_with_data(mock_repo_cls, mock_reader, mock_writer):
    from datetime import datetime

    mock_repo = MagicMock()
    mock_repo.get_symbols.return_value = pd.DataFrame(
        {
            "symbol": ["BTC/USDT", "AAPL"],
            "exchange": ["binance", "yahoo"],
            "timeframe": ["1m", "1d"],
            "rows": [100000, 500],
            "last_update": [
                datetime(2026, 5, 5, 12, 0, tzinfo=UTC),
                datetime(2024, 1, 1, tzinfo=UTC),
            ],
        }
    )
    mock_repo_cls.return_value = mock_repo

    result = _runner().invoke(app, ["status"])
    assert result.exit_code == 0
    assert "BTC/USDT" in result.output
    assert "AAPL" in result.output


@patch("src.cli.commands.status.QuestDBWriter")
@patch("src.cli.commands.status.QuestDBReader")
@patch("src.cli.commands.status.OHLCVRepository")
def test_status_empty(mock_repo_cls, mock_reader, mock_writer):
    mock_repo = MagicMock()
    mock_repo.get_symbols.return_value = pd.DataFrame()
    mock_repo_cls.return_value = mock_repo

    result = _runner().invoke(app, ["status"])
    assert result.exit_code == 0
    assert "No data" in result.output


@patch("src.cli.commands.status.load_watchlist")
@patch("src.cli.commands.status.QuestDBWriter")
@patch("src.cli.commands.status.QuestDBReader")
@patch("src.cli.commands.status.OHLCVRepository")
def test_status_orphan_warning(mock_repo_cls, mock_reader, mock_writer, mock_load):
    from datetime import datetime

    from src.watchlist import Watchlist, WatchlistEntry

    mock_repo = MagicMock()
    mock_repo.get_symbols.return_value = pd.DataFrame(
        {
            "symbol": ["BTC/USDT", "ETH/USDT"],
            "exchange": ["binance", "binance"],
            "timeframe": ["1m", "5m"],
            "rows": [100000, 10000],
            "last_update": [
                datetime(2026, 5, 7, tzinfo=UTC),
                datetime(2026, 5, 1, tzinfo=UTC),
            ],
        }
    )
    mock_repo_cls.return_value = mock_repo

    mock_load.return_value = Watchlist(
        symbols=[WatchlistEntry(symbol="BTC/USDT", exchange="binance", timeframe="1m")]
    )

    result = _runner().invoke(app, ["status"])
    assert result.exit_code == 0
    assert "not in watchlist" in result.output
    assert "ETH/USDT" in result.output
    assert "5m" in result.output


@patch("src.cli.commands.status.load_watchlist")
@patch("src.cli.commands.status.QuestDBWriter")
@patch("src.cli.commands.status.QuestDBReader")
@patch("src.cli.commands.status.OHLCVRepository")
def test_status_no_orphans(mock_repo_cls, mock_reader, mock_writer, mock_load):
    from datetime import datetime

    from src.watchlist import Watchlist, WatchlistEntry

    mock_repo = MagicMock()
    mock_repo.get_symbols.return_value = pd.DataFrame(
        {
            "symbol": ["BTC/USDT"],
            "exchange": ["binance"],
            "timeframe": ["1m"],
            "rows": [100000],
            "last_update": [datetime(2026, 5, 7, tzinfo=UTC)],
        }
    )
    mock_repo_cls.return_value = mock_repo

    mock_load.return_value = Watchlist(
        symbols=[WatchlistEntry(symbol="BTC/USDT", exchange="binance", timeframe="1m")]
    )

    result = _runner().invoke(app, ["status"])
    assert result.exit_code == 0
    assert "not in watchlist" not in result.output


@patch("src.cli.commands.status.load_watchlist")
@patch("src.cli.commands.status.QuestDBWriter")
@patch("src.cli.commands.status.QuestDBReader")
@patch("src.cli.commands.status.OHLCVRepository")
def test_status_no_watchlist_file(mock_repo_cls, mock_reader, mock_writer, mock_load):
    from datetime import datetime

    from src.exceptions import ConfigurationError

    mock_repo = MagicMock()
    mock_repo.get_symbols.return_value = pd.DataFrame(
        {
            "symbol": ["BTC/USDT"],
            "exchange": ["binance"],
            "timeframe": ["1m"],
            "rows": [100000],
            "last_update": [datetime(2026, 5, 7, tzinfo=UTC)],
        }
    )
    mock_repo_cls.return_value = mock_repo
    mock_load.side_effect = ConfigurationError("Watchlist file not found")

    result = _runner().invoke(app, ["status"])
    assert result.exit_code == 0
    assert "not in watchlist" not in result.output


# --- Error handling tests ---


@patch("src.cli.commands.download.create_source")
def test_download_invalid_exchange(mock_create):
    mock_create.side_effect = DownloadError("Unsupported exchange: fake_exchange")

    result = _runner().invoke(
        app, ["download", "BTC/USDT", "-e", "fake_exchange", "-s", "2024-01-01"]
    )
    assert result.exit_code == 1
    assert "Unsupported exchange" in result.output
    assert "Hint" in result.output


@patch("src.cli.commands.check.QuestDBWriter")
@patch("src.cli.commands.check.QuestDBReader")
@patch("src.cli.commands.check.OHLCVRepository")
@patch("src.cli.commands.check.IntegrityService")
def test_check_gaps_db_error(mock_service_cls, mock_repo, mock_reader, mock_writer):
    mock_service = MagicMock()
    mock_service.find_gaps.side_effect = DatabaseError(
        "Cannot connect to QuestDB at localhost:8812"
    )
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["check", "gaps", "BTC/USDT"])
    assert result.exit_code == 1
    assert "Cannot connect" in result.output
    assert "Hint" in result.output


@patch("src.cli.commands.check.QuestDBWriter")
@patch("src.cli.commands.check.QuestDBReader")
@patch("src.cli.commands.check.OHLCVRepository")
@patch("src.cli.commands.check.IntegrityService")
def test_check_anomalies_db_error(mock_service_cls, mock_repo, mock_reader, mock_writer):
    mock_service = MagicMock()
    mock_service.find_anomalies.side_effect = DatabaseError("Query failed")
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["check", "anomalies", "BTC/USDT"])
    assert result.exit_code == 1
    assert "Query failed" in result.output


@patch("src.cli.commands.check.QuestDBWriter")
@patch("src.cli.commands.check.QuestDBReader")
@patch("src.cli.commands.check.OHLCVRepository")
@patch("src.cli.commands.check.IntegrityService")
def test_check_health_db_error(mock_service_cls, mock_repo, mock_reader, mock_writer):
    mock_service = MagicMock()
    mock_service.check_health.side_effect = DatabaseError(
        "Cannot connect to QuestDB at localhost:8812"
    )
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["check", "health"])
    assert result.exit_code == 1
    assert "Not connected" in result.output


@patch("src.cli.commands.status.QuestDBWriter")
@patch("src.cli.commands.status.QuestDBReader")
@patch("src.cli.commands.status.OHLCVRepository")
def test_status_db_connection_error(mock_repo_cls, mock_reader, mock_writer):
    mock_repo_cls.side_effect = DatabaseError("Cannot connect to QuestDB at localhost:8812")

    result = _runner().invoke(app, ["status"])
    assert result.exit_code == 1
    assert "Cannot connect" in result.output
    assert "Hint" in result.output


@patch("src.cli.commands.query.export_dataframe")
@patch("src.cli.commands.query.QuestDBWriter")
@patch("src.cli.commands.query.QuestDBReader")
@patch("src.cli.commands.query.OHLCVRepository")
def test_query_export_permission_error(mock_repo_cls, mock_reader, mock_writer, mock_export):
    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame(
        {
            "timestamp": ["2024-01-01"],
            "open": [100],
            "high": [101],
            "low": [99],
            "close": [100],
            "volume": [10],
        }
    )
    mock_repo_cls.return_value = mock_repo
    mock_export.side_effect = OSError("Permission denied: /root/output.csv")

    result = _runner().invoke(
        app, ["query", "BTC/USDT", "--start", "2024-01-01", "-o", "/root/output.csv"]
    )
    assert result.exit_code == 1
    assert "Cannot write output file" in result.output


@patch("src.cli.commands.query.export_dataframe")
@patch("src.cli.commands.query.QuestDBWriter")
@patch("src.cli.commands.query.QuestDBReader")
@patch("src.cli.commands.query.OHLCVRepository")
def test_query_export_config_error(mock_repo_cls, mock_reader, mock_writer, mock_export):
    from src.exceptions import ConfigurationError

    mock_repo = MagicMock()
    mock_repo.get_candles.return_value = pd.DataFrame(
        {
            "timestamp": ["2024-01-01"],
            "open": [100],
            "high": [101],
            "low": [99],
            "close": [100],
            "volume": [10],
        }
    )
    mock_repo_cls.return_value = mock_repo
    mock_export.side_effect = ConfigurationError("Parquet format requires --output file path.")

    result = _runner().invoke(app, ["query", "BTC/USDT", "--start", "2024-01-01", "-f", "parquet"])
    assert result.exit_code == 1
    assert "Parquet format requires" in result.output


# --- Version and global handler tests ---


def test_version_flag():
    result = _runner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "ohlcv v" in result.output


@patch("src.cli.commands.sync.load_watchlist")
def test_sync_quiet_mode(mock_load):
    from src.services.sync import SyncResult
    from src.watchlist import Watchlist, WatchlistEntry

    mock_load.return_value = Watchlist(
        symbols=[WatchlistEntry(symbol="BTC/USDT", exchange="binance", timeframe="1m")]
    )

    with (
        patch("src.cli.commands.sync.QuestDBWriter"),
        patch("src.cli.commands.sync.QuestDBReader"),
        patch("src.cli.commands.sync.OHLCVRepository"),
        patch("src.cli.commands.sync.SyncService") as mock_svc_cls,
    ):
        mock_svc = MagicMock()
        mock_svc.sync_symbol.return_value = SyncResult(
            symbol="BTC/USDT",
            exchange="binance",
            timeframe="1m",
            rows_inserted=50,
            status="synced",
            duration=1.0,
        )
        mock_svc_cls.return_value = mock_svc

        result = _runner().invoke(app, ["sync", "--watchlist", "symbols.yaml", "--quiet"])
        assert result.exit_code == 0


@patch("src.cli.commands.download.create_source")
def test_download_unsupported_timeframe(mock_create):
    mock_source = MagicMock()
    mock_source.supported_timeframes.return_value = ["1d", "1wk"]
    mock_create.return_value = mock_source

    result = _runner().invoke(
        app, ["download", "AAPL", "-e", "yahoo", "-t", "1m", "-s", "2024-01-01"]
    )
    assert result.exit_code == 1
    assert "not supported" in result.output


@patch("src.cli.commands.download.create_source")
def test_download_invalid_symbol(mock_create):
    mock_source = MagicMock()
    mock_source.supported_timeframes.return_value = ["1m", "1h"]
    mock_source.validate_symbol.return_value = False
    mock_create.return_value = mock_source

    result = _runner().invoke(app, ["download", "INVALID", "-e", "binance", "-s", "2024-01-01"])
    assert result.exit_code != 0
    assert "not valid" in result.output


@patch("src.cli.commands.download.create_source")
def test_download_invalid_date_format(mock_create):
    mock_source = MagicMock()
    mock_source.supported_timeframes.return_value = ["1m"]
    mock_source.validate_symbol.return_value = True
    mock_create.return_value = mock_source

    result = _runner().invoke(app, ["download", "BTC/USDT", "-e", "binance", "-s", "not-a-date"])
    assert result.exit_code == 1
    assert "YYYY-MM-DD" in result.output


@patch("src.cli.commands.download.create_source")
def test_download_start_after_end(mock_create):
    mock_source = MagicMock()
    mock_source.supported_timeframes.return_value = ["1m"]
    mock_source.validate_symbol.return_value = True
    mock_create.return_value = mock_source

    result = _runner().invoke(
        app,
        ["download", "BTC/USDT", "-e", "binance", "-s", "2025-01-01", "--end", "2024-01-01"],
    )
    assert result.exit_code == 1
    assert "before end" in result.output


@patch("src.cli.commands.query.QuestDBWriter")
@patch("src.cli.commands.query.QuestDBReader")
@patch("src.cli.commands.query.OHLCVRepository")
def test_query_invalid_date_format(mock_repo_cls, mock_reader, mock_writer):
    result = _runner().invoke(app, ["query", "BTC/USDT", "--start", "not-a-date"])
    assert result.exit_code == 1
    assert "YYYY-MM-DD" in result.output


@patch("src.cli.commands.check.QuestDBWriter")
@patch("src.cli.commands.check.QuestDBReader")
@patch("src.cli.commands.check.OHLCVRepository")
@patch("src.cli.commands.check.IntegrityService")
def test_check_anomalies_found(mock_service_cls, mock_repo, mock_reader, mock_writer):
    from datetime import datetime

    from src.services.integrity import Anomaly

    mock_service = MagicMock()
    mock_service.find_anomalies.return_value = [
        Anomaly(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            anomaly_type="ohlc_violation",
            details="High < Low",
        )
    ]
    mock_service_cls.return_value = mock_service

    result = _runner().invoke(app, ["check", "anomalies", "BTC/USDT"])
    assert result.exit_code == 0
    assert "ohlc_violation" in result.output


@patch("src.cli.commands.db.QuestDBReader")
@patch("src.cli.commands.db.db_schema_init")
def test_db_init_success(mock_init, mock_reader):
    result = _runner().invoke(app, ["db", "init"])
    assert result.exit_code == 0
    mock_init.assert_called_once()


@patch("src.cli.commands.db.QuestDBReader")
@patch("src.cli.commands.db.db_schema_init")
def test_db_init_error(mock_init, mock_reader):
    mock_init.side_effect = DatabaseError("Cannot connect to QuestDB at localhost:8812")

    result = _runner().invoke(app, ["db", "init"])
    assert result.exit_code == 1
    assert "Cannot connect" in result.output


# --- Global exception handler (main()) tests ---


class TestMainEntrypoint:
    def test_main_catches_domain_error(self):
        from src.cli.main import main

        with patch("src.cli.main.app", side_effect=DatabaseError("db down")):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_catches_unexpected_error(self):
        from src.cli.main import main

        with patch("src.cli.main.app", side_effect=RuntimeError("oops")):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_main_passes_system_exit_through(self):
        from src.cli.main import main

        with patch("src.cli.main.app", side_effect=SystemExit(0)):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
