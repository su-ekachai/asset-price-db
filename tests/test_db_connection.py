from unittest.mock import MagicMock, patch

import pandas as pd
import psycopg
import pytest

from src.config import DatabaseConfig
from src.db.connection import QuestDBReader, QuestDBWriter
from src.exceptions import DatabaseError


@patch("src.db.connection.Sender")
def test_questdb_writer_http(mock_sender, monkeypatch):
    monkeypatch.delenv("QUESTDB_ILP_TLS", raising=False)
    config = DatabaseConfig(host="localhost", ilp_port=9000)
    writer = QuestDBWriter(config)
    assert "http::addr=localhost:9000;" in writer._conf


@patch("src.db.connection.Sender")
def test_questdb_writer_https(mock_sender, monkeypatch):
    monkeypatch.setenv("QUESTDB_ILP_TLS", "true")
    config = DatabaseConfig(host="localhost", ilp_port=9000)
    writer = QuestDBWriter(config)
    assert "https::addr=localhost:9000;" in writer._conf


def test_writer_insert_dataframe(mocker):
    mock_sender = mocker.patch("src.db.connection.Sender")
    mock_sender_instance = mock_sender.from_conf.return_value.__enter__.return_value

    config = DatabaseConfig()
    writer = QuestDBWriter(config)

    df = pd.DataFrame({"A": [1]})
    writer.insert_dataframe(df, "test", ["symbol"], "timestamp")

    mock_sender_instance.dataframe.assert_called_once_with(
        df, table_name="test", symbols=["symbol"], at="timestamp"
    )


def test_writer_batch_mode(mocker):
    mock_sender = mocker.patch("src.db.connection.Sender")
    mock_sender_instance = mock_sender.from_conf.return_value.__enter__.return_value

    config = DatabaseConfig()
    writer = QuestDBWriter(config)

    df = pd.DataFrame({"A": [1]})
    with writer.batch():
        writer.insert_dataframe(df, "t1", ["s"], "ts")
        writer.insert_dataframe(df, "t2", ["s"], "ts")

    assert mock_sender_instance.dataframe.call_count == 2
    mock_sender.from_conf.assert_called_once()


def test_reader_persistent_connection(mocker):
    mock_psycopg = mocker.patch("src.db.connection.psycopg")
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(1,)]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    config = DatabaseConfig()
    reader = QuestDBReader(config)

    reader.query("SELECT 1")
    reader.query("SELECT 2")

    mock_psycopg.connect.assert_called_once()


def test_reader_reconnects_on_closed(mocker):
    mock_psycopg = mocker.patch("src.db.connection.psycopg")
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(1,)]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    config = DatabaseConfig()
    reader = QuestDBReader(config)

    reader.query("SELECT 1")
    mock_conn.closed = True
    reader.query("SELECT 2")

    assert mock_psycopg.connect.call_count == 2


def test_reader_execute_ddl(mocker):
    mock_psycopg = mocker.patch("src.db.connection.psycopg")
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    config = DatabaseConfig(host="localhost", pg_port=8812, user="admin", password="pw")
    reader = QuestDBReader(config)

    reader.execute_ddl("CREATE TABLE test;")
    mock_cursor.execute.assert_called_with("CREATE TABLE test;")


def test_reader_close(mocker):
    mock_psycopg = mocker.patch("src.db.connection.psycopg")
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_psycopg.connect.return_value = mock_conn

    config = DatabaseConfig()
    reader = QuestDBReader(config)
    reader._get_conn()
    reader.close()

    mock_conn.close.assert_called_once()


def test_connection_failure_raises_database_error(mocker):
    mock_psycopg = mocker.patch("src.db.connection.psycopg")
    mock_psycopg.connect.side_effect = psycopg.OperationalError("connection refused")
    mock_psycopg.Error = psycopg.Error

    config = DatabaseConfig(host="badhost", pg_port=9999)
    reader = QuestDBReader(config)

    with pytest.raises(DatabaseError, match="Cannot connect to QuestDB"):
        reader.query("SELECT 1")


def test_query_failure_raises_database_error(mocker):
    mock_psycopg = mocker.patch("src.db.connection.psycopg")
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = psycopg.ProgrammingError("syntax error")
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn
    mock_psycopg.Error = psycopg.Error

    config = DatabaseConfig()
    reader = QuestDBReader(config)

    with pytest.raises(DatabaseError, match="Query failed"):
        reader.query("INVALID SQL")


def test_ddl_failure_raises_database_error(mocker):
    mock_psycopg = mocker.patch("src.db.connection.psycopg")
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = psycopg.ProgrammingError("table already exists")
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn
    mock_psycopg.Error = psycopg.Error

    config = DatabaseConfig()
    reader = QuestDBReader(config)

    with pytest.raises(DatabaseError, match="DDL execution failed"):
        reader.execute_ddl("CREATE TABLE oops")


def test_writer_batch_ingress_error(mocker):
    mock_sender = mocker.patch("src.db.connection.Sender")
    from questdb.ingress import IngressError

    mock_sender.from_conf.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_sender.from_conf.return_value.__exit__ = MagicMock(
        side_effect=IngressError(0, "flush failed")
    )

    config = DatabaseConfig()
    writer = QuestDBWriter(config)

    with pytest.raises(DatabaseError, match="ILP ingestion failed"), writer.batch():
        pass


def test_writer_insert_dataframe_standalone(mocker):
    mock_sender = mocker.patch("src.db.connection.Sender")
    mock_sender_instance = MagicMock()
    mock_sender.from_conf.return_value.__enter__ = MagicMock(return_value=mock_sender_instance)
    mock_sender.from_conf.return_value.__exit__ = MagicMock(return_value=False)

    config = DatabaseConfig()
    writer = QuestDBWriter(config)

    import pandas as pd

    df = pd.DataFrame({"A": [1]})
    writer.insert_dataframe(df, "test", ["symbol"], "timestamp")

    mock_sender_instance.dataframe.assert_called_once()


def test_writer_insert_row_standalone(mocker):
    mock_sender = mocker.patch("src.db.connection.Sender")
    mock_sender_instance = MagicMock()
    mock_sender.from_conf.return_value.__enter__ = MagicMock(return_value=mock_sender_instance)
    mock_sender.from_conf.return_value.__exit__ = MagicMock(return_value=False)

    config = DatabaseConfig()
    writer = QuestDBWriter(config)

    from datetime import UTC, datetime

    writer.insert_row("test", {"symbol": "BTC"}, {"price": 100}, datetime.now(UTC))

    mock_sender_instance.row.assert_called_once()


def test_writer_insert_dataframe_ingress_error(mocker):
    mock_sender = mocker.patch("src.db.connection.Sender")
    from questdb.ingress import IngressError

    mock_sender_instance = MagicMock()
    mock_sender_instance.dataframe.side_effect = IngressError(0, "insert failed")
    mock_sender.from_conf.return_value.__enter__ = MagicMock(return_value=mock_sender_instance)
    mock_sender.from_conf.return_value.__exit__ = MagicMock(return_value=False)

    config = DatabaseConfig()
    writer = QuestDBWriter(config)

    import pandas as pd

    with pytest.raises(DatabaseError, match="DataFrame insert failed"):
        writer.insert_dataframe(pd.DataFrame({"A": [1]}), "test", ["s"], "ts")


def test_writer_insert_row_ingress_error(mocker):
    mock_sender = mocker.patch("src.db.connection.Sender")
    from questdb.ingress import IngressError

    mock_sender_instance = MagicMock()
    mock_sender_instance.row.side_effect = IngressError(0, "row failed")
    mock_sender.from_conf.return_value.__enter__ = MagicMock(return_value=mock_sender_instance)
    mock_sender.from_conf.return_value.__exit__ = MagicMock(return_value=False)

    config = DatabaseConfig()
    writer = QuestDBWriter(config)

    from datetime import UTC, datetime

    with pytest.raises(DatabaseError, match="Row insert failed"):
        writer.insert_row("test", {"sym": "X"}, {"v": 1}, datetime.now(UTC))


def test_reader_query_df(mocker):
    mock_psycopg = mocker.patch("src.db.connection.psycopg")
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_cursor = MagicMock()
    mock_cursor.description = [("col1",), ("col2",)]
    mock_cursor.fetchall.return_value = [(1, "a"), (2, "b")]
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    config = DatabaseConfig()
    reader = QuestDBReader(config)
    df = reader.query_df("SELECT col1, col2 FROM test")

    assert len(df) == 2
    assert list(df.columns) == ["col1", "col2"]


def test_reader_query_df_no_description(mocker):
    mock_psycopg = mocker.patch("src.db.connection.psycopg")
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_cursor = MagicMock()
    mock_cursor.description = None
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    config = DatabaseConfig()
    reader = QuestDBReader(config)
    df = reader.query_df("SELECT 1")

    assert df.empty


def test_reader_query_df_error(mocker):
    mock_psycopg = mocker.patch("src.db.connection.psycopg")
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = psycopg.ProgrammingError("bad sql")
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn
    mock_psycopg.Error = psycopg.Error

    config = DatabaseConfig()
    reader = QuestDBReader(config)

    with pytest.raises(DatabaseError, match="Query failed"):
        reader.query_df("INVALID")
