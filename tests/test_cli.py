from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "db" in result.output
    assert "download" in result.output


@patch("src.cli.commands.db.QuestDBReader")
@patch("src.cli.commands.db.db_schema_init")
def test_db_init(mock_init, mock_reader, runner):
    result = runner.invoke(app, ["db", "init"])
    assert result.exit_code == 0
    mock_reader.assert_called_once()
    mock_init.assert_called_once()


@patch("src.cli.commands.download.QuestDBWriter")
@patch("src.cli.commands.download.QuestDBReader")
@patch("src.cli.commands.download.OHLCVRepository")
@patch("src.cli.commands.download.DownloadService")
@patch("src.cli.commands.download.create_source")
def test_download_command(
    mock_create_source, mock_service_cls, mock_repo, mock_reader, mock_writer, runner
):
    mock_source = MagicMock()
    mock_source.supported_timeframes.return_value = ["1m", "5m", "1h", "1d"]
    mock_source.validate_symbol.return_value = True
    mock_create_source.return_value = mock_source

    mock_service = MagicMock()
    mock_service.download.return_value = 100
    mock_service_cls.return_value = mock_service

    result = runner.invoke(app, ["download", "BTC/USDT", "--start", "2023-01-01"])

    assert result.exit_code == 0
    mock_service.download.assert_called_once()
    args = mock_service.download.call_args[0]
    assert args[0] == "BTC/USDT"
    assert args[1] == "binance"


@patch("src.cli.commands.download.create_source")
def test_download_invalid_symbol(mock_create_source, runner):
    mock_source = MagicMock()
    mock_source.supported_timeframes.return_value = ["1m", "5m", "1h", "1d"]
    mock_source.validate_symbol.return_value = False
    mock_create_source.return_value = mock_source

    result = runner.invoke(app, ["download", "BTCUSDT", "--start", "2023-01-01"])
    assert result.exit_code != 0


@patch("src.cli.commands.download.create_source")
def test_download_invalid_timeframe(mock_create_source, runner):
    mock_source = MagicMock()
    mock_source.supported_timeframes.return_value = ["1m", "5m", "1h", "1d"]
    mock_create_source.return_value = mock_source

    result = runner.invoke(
        app, ["download", "BTC/USDT", "--timeframe", "2m", "--start", "2023-01-01"]
    )
    assert result.exit_code != 0


@patch("src.cli.commands.download.QuestDBWriter")
@patch("src.cli.commands.download.QuestDBReader")
@patch("src.cli.commands.download.OHLCVRepository")
@patch("src.cli.commands.download.DownloadService")
@patch("src.cli.commands.download.create_source")
def test_download_start_after_end(
    mock_create_source, mock_service_cls, mock_repo, mock_reader, mock_writer, runner
):
    mock_source = MagicMock()
    mock_source.supported_timeframes.return_value = ["1m", "5m", "1h", "1d"]
    mock_source.validate_symbol.return_value = True
    mock_create_source.return_value = mock_source

    result = runner.invoke(
        app, ["download", "BTC/USDT", "--start", "2024-06-01", "--end", "2024-01-01"]
    )
    assert result.exit_code != 0
    assert "before end" in result.output


@patch("src.cli.commands.download.QuestDBWriter")
@patch("src.cli.commands.download.QuestDBReader")
@patch("src.cli.commands.download.OHLCVRepository")
@patch("src.cli.commands.download.DownloadService")
@patch("src.cli.commands.download.create_source")
def test_download_multiple_symbols(
    mock_create_source, mock_service_cls, mock_repo, mock_reader, mock_writer, runner
):
    mock_source = MagicMock()
    mock_source.supported_timeframes.return_value = ["1m", "5m", "1h", "1d"]
    mock_source.validate_symbol.return_value = True
    mock_create_source.return_value = mock_source

    mock_service = MagicMock()
    mock_service.download.return_value = 50
    mock_service_cls.return_value = mock_service

    result = runner.invoke(app, ["download", "BTC/USDT", "ETH/USDT", "--start", "2023-01-01"])

    assert result.exit_code == 0
    assert mock_service.download.call_count == 2
