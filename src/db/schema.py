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
            timestamp TIMESTAMP,
            symbol SYMBOL,
            exchange SYMBOL,
            asset_type SYMBOL,
            base_currency SYMBOL,
            quote_currency SYMBOL,
            description STRING
        ) timestamp(timestamp) PARTITION BY YEAR WAL;
    """)
