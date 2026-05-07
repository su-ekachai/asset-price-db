# CLAUDE.md — OHLCV Data Store

## Project Overview
A Python 3.12 OHLCV (Open/High/Low/Close/Volume) market data ingestion pipeline supporting crypto exchanges (via ccxt) and traditional markets (via Yahoo Finance). Fetches historical candle data and stores it in QuestDB, a high-performance time-series database.

## Quick Commands
```bash
uv sync                                 # Install dependencies
uv run pytest                           # Run tests (80%+ coverage enforced)
uv run ruff check src/ tests/           # Lint
uv run ruff format src/ tests/          # Format
uv run ty check src/                    # Type check
uv run pre-commit run --all-files       # Run all pre-commit hooks
uv run ohlcv --help                     # CLI help
uv run ohlcv db init                    # Initialize database schema
uv run ohlcv download BTC/USDT ETH/USDT --start 2024-01-01 -v
uv run ohlcv sync --dry-run             # Preview watchlist sync
uv run ohlcv sync                       # Sync all watchlist symbols to present
uv run ohlcv query BTC/USDT --start 2024-01-01 --format csv
uv run ohlcv query --list               # List all stored data
uv run ohlcv status                     # Overview dashboard
uv run ohlcv check health               # Verify QuestDB connectivity
uv run ohlcv check gaps BTC/USDT -e binance -t 1m
```

## Architecture

```
main.py                         → Entry point
src/
├── config.py                   → Configuration (env vars > YAML > defaults)
├── exceptions.py               → Custom exception hierarchy
├── export.py                   → DataFrame export (CSV/JSON/Parquet)
├── utils.py                    → Retry decorator, utilities
├── watchlist.py                → symbols.yaml parsing + validation
├── cli/
│   ├── main.py                 → Typer app, callback, command assembly
│   ├── state.py                → Module-level State dataclass (config + logging)
│   └── commands/
│       ├── check.py            → `check gaps|anomalies|health` commands
│       ├── db.py               → `db init` command
│       ├── download.py         → `download` command (multi-symbol)
│       ├── query.py            → `query` command (export to CSV/JSON/Parquet)
│       ├── status.py           → `status` command (rich table dashboard)
│       └── sync.py             → `sync` command (cron-friendly watchlist sync)
├── db/
│   ├── connection.py           → QuestDBWriter (ILP) + QuestDBReader (PostgreSQL wire)
│   ├── repository.py           → OHLCVRepository (data access layer)
│   └── schema.py               → DDL table definitions
├── services/
│   ├── downloader.py           → DownloadService (single download orchestration)
│   ├── integrity.py            → IntegrityService (gap/anomaly detection, health)
│   └── sync.py                 → SyncService (watchlist sync orchestration)
└── sources/
    ├── base.py                 → DataSource ABC (download, get_metadata, supported_timeframes, validate_symbol)
    ├── ccxt_source.py          → CcxtSource (any ccxt-supported crypto exchange)
    ├── registry.py             → Source factory (create_source)
    └── yahoo.py                → YahooSource (stocks/forex/commodities via yfinance)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `db init` | Create QuestDB tables (ohlcv, download_log, assets) |
| `download SYMBOLS --exchange --timeframe --start --end` | Download OHLCV data for one or more symbols |
| `sync [SYMBOLS] --watchlist --dry-run --quiet` | Sync watchlist symbols to present (cron-friendly) |
| `query SYMBOL --exchange --timeframe --start --end --format --output --list` | Query stored data, export to CSV/JSON/Parquet |
| `status` | Show overview dashboard of all stored data |
| `check gaps SYMBOL` | Find missing candle periods |
| `check anomalies SYMBOL` | Detect data quality issues (OHLC violations, spikes, zero volume) |
| `check health` | Verify QuestDB connectivity and basic stats |

## Watchlist Configuration

Create `symbols.yaml` (see `symbols.yaml.example` for template):
```yaml
symbols:
  - symbol: BTC/USDT
    exchange: binance
    timeframe: 1m
    lookback: 30d
  - symbol: AAPL
    exchange: yahoo
    timeframe: 1d
    lookback: 2y
```

Fields: `symbol` (required), `exchange` (required), `timeframe` (required), `lookback` (optional, default `30d` — supports `Nd`, `Nw`, `Nmo`, `Ny`).

## Code Conventions
- Python 3.12+: `type` aliases, `@override`, `match` statements
- All dataclasses use `kw_only=True`
- Favor straightforward procedural logic over complex inheritance
- UTC timestamps everywhere; strip tz before QuestDB ILP insert via `dt.tz_localize(None).dt.as_unit('us')`
- No bare `except Exception` — use specific exception types from `src/exceptions.py`
- Retry with exponential backoff for external API calls (see `src/utils.py`)
- Keep dependency footprint minimal — prefer stdlib over new packages

## Environment Variables (override config.yaml)
| Variable | Default | Description |
|----------|---------|-------------|
| `QUESTDB_HOST` | localhost | QuestDB hostname |
| `QUESTDB_ILP_PORT` | 9000 | ILP ingestion port |
| `QUESTDB_PG_PORT` | 8812 | PostgreSQL wire port |
| `QUESTDB_USER` | admin | Database user |
| `QUESTDB_PASSWORD` | quest | Database password |
| `QUESTDB_ILP_TLS` | (unset) | Set to enable HTTPS for ILP |
| `QUESTDB_SSLMODE` | disable | psycopg sslmode (disable/require/verify-full) |

## Database
- **QuestDB** with ILP (port 9000) for writes, PostgreSQL wire (port 8812) for reads
- Tables: `ohlcv` (DAY partitioned), `download_log` (MONTH), `assets` (YEAR)
- All tables use WAL and `DEDUP UPSERT KEYS(timestamp, symbol, exchange, timeframe)`
- Schema initialized via `db init` command

## Data Flow
1. Typer callback initializes State (config + logging) → command function runs
2. Source created via `create_source(exchange)` registry factory
3. DataSource (CcxtSource or YahooSource) fetches candles with retry/backoff
4. Repository converts timestamps, inserts via ILP batch mode
5. Asset metadata registered, download logged

## Testing
- Tests in `tests/`, fixtures in `tests/conftest.py`
- Mock all external services (QuestDB, ccxt exchange APIs, yfinance)
- 80% coverage minimum enforced via `pytest-cov`
- Run `uv run pytest` — includes coverage report
- 107 tests, 90%+ coverage

## Adding a New Exchange
1. Create `src/sources/<exchange>.py` implementing `DataSource` ABC
2. Implement `download()` → returns `pd.DataFrame` with columns: timestamp, open, high, low, close, volume
3. Implement `get_metadata()` → returns dict with asset_type, base_currency, quote_currency, description
4. Implement `supported_timeframes()` → returns list of valid timeframe strings
5. Implement `validate_symbol()` → returns True if symbol format is valid for this source
6. Register in `src/sources/registry.py` factory function
7. Add tests in `tests/`

## Key Decisions
- Multi-exchange via generic CcxtSource (any ccxt-supported exchange) + YahooSource for traditional markets
- Source registry factory pattern (`create_source`) decouples CLI from specific source implementations
- Single DataFrame return from sources (not Iterator) — memory acceptable for 1000-row batches
- QuestDB chosen for time-series performance and built-in deduplication
- ccxt library for unified exchange API abstraction
- No async — sequential downloads, single-threaded (acceptable for batch workload)
- Batch ILP connections for performance (single connection per download operation)
- Cron-friendly sync: proper exit codes, quiet mode, watchlist-driven
- Per-symbol timeframe support via symbols.yaml (crypto 1m, stocks 1d)
