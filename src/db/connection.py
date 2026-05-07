import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import Any, cast

import pandas as pd
import psycopg
from loguru import logger
from questdb.ingress import IngressError, Sender

from src.config import DatabaseConfig
from src.exceptions import DatabaseError

type JSONDict = dict[str, Any]


class QuestDBWriter:
    """Ingests data into QuestDB via the Influx Line Protocol (ILP) over HTTP."""

    def __init__(self, config: DatabaseConfig) -> None:
        protocol = "https" if os.environ.get("QUESTDB_ILP_TLS") else "http"
        self._conf = f"{protocol}::addr={config.host}:{config.ilp_port};"
        self._sender: Sender | None = None

    @contextmanager
    def batch(self) -> Generator[None, None, None]:
        """Context manager that holds a single ILP connection for multiple inserts."""
        try:
            with Sender.from_conf(self._conf) as sender:
                self._sender = sender
                try:
                    yield
                finally:
                    self._sender = None
        except IngressError as e:
            raise DatabaseError(f"ILP ingestion failed: {e}") from e

    def insert_dataframe(
        self, df: pd.DataFrame, table_name: str, symbols: list[str], at: str
    ) -> None:
        """Write a pandas DataFrame as a batch of ILP rows."""
        try:
            if self._sender:
                self._sender.dataframe(df, table_name=table_name, symbols=symbols, at=at)
            else:
                with Sender.from_conf(self._conf) as sender:
                    sender.dataframe(df, table_name=table_name, symbols=symbols, at=at)
        except IngressError as e:
            raise DatabaseError(f"DataFrame insert failed: {e}") from e

    def insert_row(
        self, table_name: str, symbols: dict[str, str], columns: JSONDict, at: datetime
    ) -> None:
        """Write a single row via ILP."""
        try:
            if self._sender:
                self._sender.row(table_name, symbols=symbols, columns=columns, at=at)
            else:
                with Sender.from_conf(self._conf) as sender:
                    sender.row(table_name, symbols=symbols, columns=columns, at=at)
        except IngressError as e:
            raise DatabaseError(f"Row insert failed: {e}") from e


class QuestDBReader:
    """Reads data from QuestDB via the PostgreSQL wire protocol (port 8812)."""

    def __init__(self, config: DatabaseConfig) -> None:
        sslmode = os.environ.get("QUESTDB_SSLMODE", "disable")
        self._host = config.host
        self._port = config.pg_port
        self._conn_str = (
            f"user={config.user} password={config.password} "
            f"host={config.host} port={config.pg_port} dbname=qdb "
            f"sslmode={sslmode} connect_timeout=10"
        )
        self._conn: psycopg.Connection[Any] | None = None

    def _get_conn(self) -> psycopg.Connection[Any]:
        """Return the persistent connection, establishing it on first call or reconnect."""
        if self._conn is None or self._conn.closed:
            logger.debug("Establishing PostgreSQL connection to {}:{}", self._host, self._port)
            try:
                self._conn = psycopg.connect(self._conn_str, autocommit=True)
                # Set statement timeout to 30 seconds
                with self._conn.cursor() as cur:
                    cur.execute(cast(bytes, "SET statement_timeout TO '30000'"))
            except psycopg.Error as e:
                raise DatabaseError(
                    f"Cannot connect to QuestDB at {self._host}:{self._port}: {e}"
                ) from e
        return self._conn

    def close(self) -> None:
        """Release the persistent PostgreSQL connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        """Execute SQL and return all rows as tuples."""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(cast(bytes, sql), params)
                return cur.fetchall()
        except DatabaseError:
            raise
        except psycopg.Error as e:
            raise DatabaseError(f"Query failed: {e}") from e

    def query_df(self, sql: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
        """Execute SQL and return results as a pandas DataFrame."""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(cast(bytes, sql), params)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                return pd.DataFrame(cur.fetchall(), columns=columns)
        except DatabaseError:
            raise
        except psycopg.Error as e:
            raise DatabaseError(f"Query failed: {e}") from e

    def execute_ddl(self, sql: str) -> None:
        """Execute a DDL statement (CREATE TABLE, ALTER TABLE, etc.)."""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(cast(bytes, sql))
        except DatabaseError:
            raise
        except psycopg.Error as e:
            raise DatabaseError(f"DDL execution failed: {e}") from e
