# OHLCV Data Store Architecture

This document provides a technical overview of the OHLCV Data Store project to guide future development and agentic workers.

## 1. System Overview
The OHLCV Data Store is a high-performance market data ingestion pipeline and storage system. It retrieves historical market data (Candles/OHLCV) from crypto exchanges and traditional markets, stores it in **QuestDB**, and provides CLI tools for querying, exporting, syncing, and validating data integrity.

**Tech Stack:**
- **Language:** Python 3.12 (Strict typing enforced)
- **Database:** QuestDB (ILP for writes, PostgreSQL wire for reads)
- **Data Processing:** `pandas`, `pyarrow`
- **Exchange APIs:** `ccxt` (crypto), `yfinance` (stocks/forex/commodities)
- **Package Management:** `uv`
- **CLI:** Typer (type-hint driven), Rich (formatted output)

## 2. Core Components

### 2.1 CLI (`src/cli/`)
The entry point for the application. Built with Typer, a modern CLI framework using Python type hints. Six commands:
- **`db init`** — Initialize QuestDB schema
- **`download`** — Fetch OHLCV data for one or more symbols
- **`sync`** — Cron-friendly watchlist sync to present
- **`query`** — Query stored data and export (CSV/JSON/Parquet)
- **`status`** — Rich table overview of all stored data
- **`check`** — Data integrity (gaps, anomalies, health)

### 2.2 Data Sources (`src/sources/`)
- **`DataSource` (Abstract Base Class in `base.py`):** Defines the contract for any data provider. Four abstract methods: `download()`, `get_metadata()`, `supported_timeframes()`, `validate_symbol()`.
- **`CcxtSource` (`ccxt_source.py`):** Generic source for any ccxt-supported crypto exchange. Constructor takes `exchange_name` and instantiates via `getattr(ccxt, exchange_name)`. Includes retry logic for rate limits, network errors, and exchange errors.
- **`YahooSource` (`yahoo.py`):** Traditional markets source using `yfinance`. Supports `1d`, `1wk`, `1mo` timeframes. Validates symbols as alphanumeric without `/`.
- **`registry.py`:** Factory function `create_source(exchange, rate_limit_pause)` routes "yahoo" to YahooSource, everything else to CcxtSource.

### 2.3 Database Layer (`src/db/`)
- **`QuestDBWriter`:** ILP ingestion via port 9000. Supports batch mode (context manager for connection reuse) and SSL/TLS.
- **`QuestDBReader`:** PostgreSQL wire protocol via port 8812 with persistent connection and auto-reconnect.
- **`OHLCVRepository`:** Data access layer with methods:
  - `insert_candles()` — Batch insert OHLCV data
  - `get_last_timestamp()` — Most recent timestamp for a symbol (used by sync)
  - `get_candles()` — Query with optional date/limit filters
  - `get_symbols()` — List all unique symbol/exchange/timeframe combinations with stats
  - `register_asset()` — Register asset metadata
  - `log_download()` — Record download activity

### 2.4 Services (`src/services/`)
- **`DownloadService` (`downloader.py`):** Orchestrates a single download operation — validates data, registers metadata, inserts candles, logs download.
- **`SyncService` (`sync.py`):** Watchlist-driven sync. For each symbol: queries `get_last_timestamp()`, calculates start from lookback or last known position, downloads delta, inserts. Returns `SyncResult` per symbol with status (synced/skipped/failed/dry_run).
- **`IntegrityService` (`integrity.py`):** Data quality validation:
  - `find_gaps()` — Detects missing candle periods based on expected interval
  - `find_anomalies()` — Detects OHLC violations, zero volume, price spikes (>50%), duplicates
  - `check_health()` — Verifies QuestDB connectivity and table stats

### 2.5 Watchlist (`src/watchlist.py`)
Loads `symbols.yaml` into `Watchlist` dataclass containing `WatchlistEntry` items. Each entry: symbol, exchange, timeframe, lookback. Validates lookback format (Nd/Nw/Nmo/Ny) and parses to days.

### 2.6 Export (`src/export.py`)
`export_dataframe(df, fmt, output)` — Exports pandas DataFrame to CSV (stdout or file), JSON (stdout or file), or Parquet (file only).

### 2.7 Configuration (`src/config.py`)
Supports three layers of configuration with precedence: environment variables > YAML config file > dataclass defaults. Production deployments must set secrets via environment variables.

### 2.8 Error Handling (`src/exceptions.py`)
Custom exception hierarchy: `AssetPriceDBError` → `DownloadError` (with `RateLimitError`, `NetworkError`), `DatabaseError`, `ConfigurationError`. External API calls use retry with exponential backoff.

## 3. Data Flow & Ingestion Process

### 3.1 Download Process
1. CLI validates symbols via `source.validate_symbol()` and timeframe via `source.supported_timeframes()`.
2. `create_source(exchange)` instantiates the appropriate DataSource.
3. DataSource fetches candles in batches (1,000 for ccxt) with retry logic for transient failures.
4. Returns a single `pd.DataFrame` with standard columns (timestamp, open, high, low, close, volume).
5. `DownloadService` validates the data (no future timestamps), then inserts via batch ILP connection.

### 3.2 Sync Process
1. `SyncService` loads watchlist entries.
2. For each symbol: queries `repository.get_last_timestamp()`.
3. If no data: calculates start from `now - lookback_days`.
4. If data exists: starts from `last_timestamp + 1ms`.
5. If `start >= now`: skips (already up to date).
6. Downloads delta and inserts, returns `SyncResult`.

### 3.3 Database Deduplication (Upsert)
QuestDB is configured with `DEDUP UPSERT KEYS(timestamp, symbol, exchange, timeframe)` on the `ohlcv` table. If the downloader happens to fetch overlapping data, QuestDB silently overwrites the existing row, preventing duplicate entries without throwing primary key errors.

## 4. Agentic Guidelines (For Future Workers)

When enhancing or adding new features to this codebase, adhere strictly to the following mandates:

1. **Error Handling:** Never use bare `except Exception`. Use specific exception types from `src/exceptions.py`. External API calls must have retry logic.
2. **Timezone Awareness:** All datetimes must be UTC-aware. Use `pd.Timestamp.now('UTC')` instead of `utcnow()`. Before inserting into QuestDB, timestamps in pandas DataFrames should be converted to `datetime64[us]` and made timezone-naive (`tz_localize(None)`), as the ILP client implicitly treats them as UTC.
3. **Symbol Categorization:** The QuestDB Python client expects symbol columns (like `symbol`, `exchange`, `timeframe`) to be explicitly declared as `symbols` in the `.dataframe()` ingestion method. These columns remain plain strings in the pandas DataFrame.
4. **Testing:** Maintain >80% test coverage. Every new component must have a corresponding test file in `tests/`. Mock database connections and external APIs heavily.
5. **Simplicity:** Favor straightforward, procedural logic over complex inheritance trees. Touch only the files necessary for the task at hand.
6. **Security:** Never hardcode credentials. Use environment variables for secrets. See the Environment Variables table in `CLAUDE.md` for the full reference.
7. **Adding Sources:** New data sources implement `DataSource` ABC and register in `src/sources/registry.py`. Must implement all four abstract methods.
8. **CLI Commands:** New commands go in `src/cli/commands/` and register in `src/cli/main.py` via `app.command()` or `app.add_typer()`.
