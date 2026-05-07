from unittest.mock import MagicMock

import pandas as pd
import pytest
from typer.testing import CliRunner

from src.config import AppConfig, DatabaseConfig, DownloadConfig
from src.db.repository import OHLCVRepository


@pytest.fixture
def db_config():
    return DatabaseConfig(
        host="localhost", ilp_port=9000, pg_port=8812, user="test", password="test"
    )


@pytest.fixture
def app_config(db_config):
    return AppConfig(database=db_config, download=DownloadConfig())


@pytest.fixture
def mock_writer():
    writer = MagicMock()
    writer.batch.return_value.__enter__ = MagicMock(return_value=None)
    writer.batch.return_value.__exit__ = MagicMock(return_value=False)
    return writer


@pytest.fixture
def mock_reader():
    return MagicMock()


@pytest.fixture
def mock_repo(mock_writer, mock_reader):
    return OHLCVRepository(mock_writer, mock_reader)


@pytest.fixture
def sample_ohlcv_df():
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-01-01T00:00:00Z", "2024-01-01T00:01:00Z", "2024-01-01T00:02:00Z"]
            ),
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [95.0, 96.0, 97.0],
            "close": [102.0, 103.0, 104.0],
            "volume": [10.0, 11.0, 12.0],
        }
    )


@pytest.fixture
def runner():
    return CliRunner()
