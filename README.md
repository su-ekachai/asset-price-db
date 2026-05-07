# OHLCV Data Store

A high-performance OHLCV (Open/High/Low/Close/Volume) market data ingestion pipeline. Downloads historical candle data from crypto exchanges and traditional markets, stores it in QuestDB for fast time-series queries.

## Features

- **Multi-source:** Crypto via [ccxt](https://github.com/ccxt/ccxt) (Binance, Coinbase, etc.) and stocks/forex via [yfinance](https://github.com/ranaroussi/yfinance)
- **Time-series optimized:** QuestDB with ILP ingestion, deduplication, and partitioned storage
- **Watchlist sync:** Cron-friendly incremental sync with configurable lookback
- **Data integrity:** Gap detection, anomaly detection (OHLC violations, price spikes, zero volume)
- **Export:** CSV, JSON, Parquet output formats
- **Rich CLI:** Progress bars, colored output, helpful error messages

## Prerequisites

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) (package manager)
- Docker (for QuestDB)

## Quick Start

```bash
# 1. Start QuestDB
docker-compose up -d

# 2. Install dependencies
uv sync

# 3. Initialize database schema
uv run ohlcv db init

# 4. Download data
uv run ohlcv download BTC/USDT --start 2024-01-01

# 5. Check what's stored
uv run ohlcv status
```

## Usage

### Download

```bash
uv run ohlcv download BTC/USDT --start 2024-01-01
uv run ohlcv download BTC/USDT ETH/USDT -e binance -t 1h -s 2024-01-01 --end 2024-06-01
```

### Sync (watchlist-driven, incremental)

```bash
uv run ohlcv sync                          # Sync all symbols to present
uv run ohlcv sync BTC/USDT --dry-run       # Preview what would be downloaded
uv run ohlcv sync --watchlist custom.yaml   # Use custom watchlist
```

### Query and Export

```bash
uv run ohlcv query BTC/USDT --start 2024-01-01 --format csv
uv run ohlcv query --list                  # List all stored symbols
uv run ohlcv query AAPL -e yahoo -t 1d --format json -o data.json
```

### Data Integrity

```bash
uv run ohlcv check health                  # Verify QuestDB connectivity
uv run ohlcv check gaps BTC/USDT -e binance -t 1m
uv run ohlcv check anomalies BTC/USDT
```

### Status Dashboard

```bash
uv run ohlcv status
```

Run `uv run ohlcv --help` for the full command reference.

## Watchlist Configuration

Create `symbols.yaml` from the example:

```bash
cp symbols.yaml.example symbols.yaml
```

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

| Field | Required | Description |
|-------|----------|-------------|
| `symbol` | Yes | Trading pair or ticker (e.g., `BTC/USDT`, `AAPL`) |
| `exchange` | Yes | Source name (`binance`, `coinbase`, `yahoo`, etc.) |
| `timeframe` | Yes | Candle interval (`1m`, `5m`, `1h`, `1d`, etc.) |
| `lookback` | No | Initial sync depth (default `30d`). Supports `Nd`, `Nw`, `Nmo`, `Ny` |

## Configuration

Environment variables override `config.yaml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `QUESTDB_HOST` | `localhost` | QuestDB hostname |
| `QUESTDB_ILP_PORT` | `9000` | ILP ingestion port |
| `QUESTDB_PG_PORT` | `8812` | PostgreSQL wire protocol port |
| `QUESTDB_USER` | `admin` | Database user |
| `QUESTDB_PASSWORD` | `quest` | Database password |
| `QUESTDB_ILP_TLS` | (unset) | Set to enable HTTPS for ILP |
| `QUESTDB_SSLMODE` | `disable` | psycopg sslmode (`disable`/`require`/`verify-full`) |

## Development

### Setup

```bash
uv sync                              # Install all dependencies
uv run pre-commit install            # Install git hooks
```

### Code Quality

```bash
uv run ruff check src/ tests/        # Lint
uv run ruff format src/ tests/       # Format
uv run ty check src/                 # Type check
uv run pytest                        # Tests (80%+ coverage enforced)
uv run pre-commit run --all-files    # Run all hooks
```

### Pre-commit Hooks

Automatically run on every commit:

| Hook | Purpose |
|------|---------|
| `check-yaml` | Validates YAML syntax |
| `check-merge-conflict` | Catches leftover conflict markers |
| `check-added-large-files` | Blocks files > 500KB |
| `trailing-whitespace` | Removes trailing spaces |
| `end-of-file-fixer` | Ensures newline at EOF |
| `gitleaks` | Scans for secrets and API keys |
| `ruff` | Lint with auto-fix |
| `ruff-format` | Code formatting |
| `ty` | Static type checking |

### Tech Stack

- **Language:** Python 3.12 (`type` aliases, `StrEnum`, `@override`)
- **CLI:** [Typer](https://typer.tiangolo.com/) with Rich output
- **Database:** [QuestDB](https://questdb.io/) (ILP writes, PostgreSQL reads)
- **Data Sources:** [ccxt](https://github.com/ccxt/ccxt), [yfinance](https://github.com/ranaroussi/yfinance)
- **Linting:** [Ruff](https://docs.astral.sh/ruff/) (E, F, W, I, UP, B, SIM rules)
- **Type Checking:** [ty](https://docs.astral.sh/ty/)
- **Testing:** pytest with 90%+ coverage (107 tests)
- **Package Manager:** [uv](https://github.com/astral-sh/uv)

## Project Structure

```
src/
├── cli/           CLI commands (Typer)
├── db/            Database layer (QuestDB ILP + PostgreSQL wire)
├── services/      Business logic (download, sync, integrity)
└── sources/       Data source adapters (ccxt, yfinance)
tests/             107 tests, 90%+ coverage
docs/              Architecture and deployment guides
```

## License

MIT
