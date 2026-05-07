from unittest.mock import MagicMock

from src.db.schema import init_db


def test_init_db_creates_tables():
    mock_reader = MagicMock()
    init_db(mock_reader)
    assert mock_reader.execute_ddl.call_count == 3


def test_init_db_ddl_contains_table_names():
    mock_reader = MagicMock()
    init_db(mock_reader)
    calls = [str(call) for call in mock_reader.execute_ddl.call_args_list]
    assert any("ohlcv" in c for c in calls)
    assert any("download_log" in c for c in calls)
    assert any("assets" in c for c in calls)


def test_init_db_uses_wal_partitioning():
    mock_reader = MagicMock()
    init_db(mock_reader)
    calls = [str(call) for call in mock_reader.execute_ddl.call_args_list]
    assert all("WAL" in c for c in calls)
    assert all("PARTITION BY" in c for c in calls)
