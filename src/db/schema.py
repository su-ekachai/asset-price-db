from src.db.connection import QuestDBReader


def init_db(reader: QuestDBReader) -> None:
    """Create all required tables (ohlcv, download_log, assets) if they do not exist."""
    reader.execute_ddl("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            timestamp TIMESTAMP,
            symbol SYMBOL,
            exchange SYMBOL,
            timeframe SYMBOL,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE
        ) timestamp(timestamp) PARTITION BY DAY WAL;
    """)

    reader.execute_ddl("""
        CREATE TABLE IF NOT EXISTS download_log (
            timestamp TIMESTAMP,
            symbol SYMBOL,
            exchange SYMBOL,
            timeframe SYMBOL,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            rows_inserted LONG
        ) timestamp(timestamp) PARTITION BY MONTH WAL;
    """)

    reader.execute_ddl("""
        CREATE TABLE IF NOT EXISTS assets (
            created_at TIMESTAMP,
            symbol SYMBOL,
            exchange SYMBOL,
            asset_type SYMBOL,
            base_currency SYMBOL,
            quote_currency SYMBOL,
            description STRING
        ) timestamp(created_at) PARTITION BY YEAR WAL;
    """)

    # DEDUP is the integrity guarantee the whole pipeline relies on (sync refetches
    # boundary candles expecting upsert) — a failure here must abort init, not be
    # suppressed. ENABLE is idempotent, so re-running `db init` stays safe.
    for ddl in [
        "ALTER TABLE ohlcv DEDUP ENABLE UPSERT KEYS(timestamp, symbol, exchange, timeframe);",
        "ALTER TABLE download_log "
        "DEDUP ENABLE UPSERT KEYS(timestamp, symbol, exchange, timeframe);",
        "ALTER TABLE assets DEDUP ENABLE UPSERT KEYS(created_at, symbol, exchange);",
    ]:
        reader.execute_ddl(ddl)
