# tz-data

Unified market data download and management for Chinese futures/options markets.

## Overview

tz-data is a Python package that downloads, parses, stores, and serves market data from Chinese futures and options exchanges (CFFEX, SHFE, DCE, CZCE, INE) into SQLite databases. It serves as the unified data source for:

- **tz2.0** - Trading analysis platform (FastAPI + Vue.js)
- **tz-ai** - AI-powered trading analysis platform

## Version: 0.3.0

### Features

| Feature | Status |
|---------|--------|
| CFFEX daily/weekly/monthly quotes | Implemented |
| CFFEX position ranking | Implemented |
| SHFE daily quotes (AkShare) | Implemented |
| SHFE option quotes | Implemented |
| Tushare daily/minute/option | Implemented |
| CFMMC bill auto-download (Selenium) | Implemented |
| Bill HTML parser | Implemented |
| 12→ DB migration | Implemented |
| Python SDK (`TzDataClient`) | Implemented |
| CLI (`tzdata` command) | Implemented |
| Download scheduler (APScheduler) | Implemented |
| FastAPI service (`tzdata serve`) | Implemented |
| DCE/CZCE/INE downloaders | Planned |

## Installation

```bash
pip install -e .
```

## Architecture

tz-data consolidates data from 12 legacy SQLite databases into 3 unified databases:

| Database | Content | Tables | Total Rows |
|----------|---------|--------|------------|
| `tzdata_market.db` | Quotes, positions, contracts | 10 | ~1.6M |
| `tzdata_trading.db` | Bills, trades, accounts | 28 | ~923K |
| `tzdata_analysis.db` | Institution features, signals | 18 | ~5.6K |

### Core Tables

| Database | Table | Rows | Description |
|----------|-------|------|-------------|
| Market | `daily_quotes` | 967K | Unified daily quotes (CFFEX + SHFE) |
| Market | `position_detail` | 639K | CFFEX position rankings |
| Market | `contracts` | 106 | Contract definitions |
| Trading | `cffex_daily_settlement` | 889K | CFFEX daily settlement data |
| Trading | `trades` | 13.5K | Trade records |
| Trading | `matched_trades` | 9.9K | Open-close paired trades |
| Trading | `trade_performance` | 9.9K | Trade performance analysis |
| Trading | `strategy_performance_summary` | 286 | Strategy performance by dimension |
| Analysis | `feature_daily` | 5.5K | Daily comprehensive features |
| Analysis | `model_validation_records` | 141 | Model validation records |

### Data Flow

```
Exchanges (CFFEX/SHFE) ??▸Downloaders ??▸Dual-write ??▸tzdata_market.db (unified)
                                              ??                                              └??▸cffex.db / shfe.db (legacy, transition)

CFMMC (bills) ??▸Selenium download ??▸HTML parser ??▸tzdata_trading.db

Tushare API ??▸TushareDownloader ??▸tzdata_market.db / tzdata_analysis.db

Legacy 12 DBs ??▸Migration script ??▸3 unified DBs
```

## CLI Commands

```bash
# Download market data
tzdata download cffex --product MO --from 2025-01-01 --to 2025-05-01
tzdata download cffex --product MO --data-type position --from 2025-01-01 --to 2025-05-01
tzdata download shfe --product AU --incremental
tzdata download tushare --type minute --underlying MO --from 2025-01-01 --to 2025-05-01
tzdata download cfmmc --auto

# Query data
tzdata query quotes --exchange CFFEX --contract MO2505
tzdata query positions --contract MO2505 --date 2025-05-01
tzdata query bills --account-id ACC001
tzdata query pnl --account-id ACC001 --from 2025-01-01 --to 2025-05-01

# Migration (12 legacy DBs →3 unified DBs)
tzdata migrate --dry-run    # Preview what would be migrated
tzdata migrate              # Execute migration
tzdata migrate --verify     # Verify row counts match

# Status & validation
tzdata status               # Data freshness and table statistics
tzdata validate             # Data quality checks

# Scheduler
tzdata schedule start               # Start download scheduler
tzdata schedule start --background  # Background mode
tzdata schedule run cffex_daily     # Run a specific job immediately
tzdata schedule list                # List scheduled jobs

# API service
tzdata serve --port 8100    # Start FastAPI API service
tzdata serve --reload       # Development mode with auto-reload
```

## Python SDK

```python
from tzdata_pkg.query import TzDataClient

with TzDataClient() as client:
    # Query market quotes
    quotes = client.quotes(exchange="CFFEX", contract="MO2505")

    # Query positions
    positions = client.positions(contract="MO2505", trade_date="2025-05-01")

    # Query bills
    bills = client.bills(account_id="ACC001")

    # Query P&L summary
    pnl = client.pnl_summary(account_id="ACC001")

    # Query trading signals
    signals = client.signals(signal_type="trend")

    # Query market regime
    regime = client.market_regime(trade_date="2025-05-01")

    # Get system status
    status = client.status()
```

## API Service

Start the FastAPI service:

```bash
tzdata serve --port 8100
```

API endpoints (all under `/api/v1`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/market/quotes` | GET | Query quote data |
| `/api/v1/market/contracts` | GET | Contract list |
| `/api/v1/positions/{product}` | GET | Position rankings |
| `/api/v1/positions/{product}/top-holders` | GET | Top holder concentration |
| `/api/v1/bills` | GET | Bill list |
| `/api/v1/trades` | GET | Trade records |
| `/api/v1/pnl` | GET | P&L summary |
| `/api/v1/account-summary` | GET | Account overview |
| `/api/v1/signals` | GET | Trading signals |
| `/api/v1/regime` | GET | Market regime |
| `/api/v1/institution-features` | GET | Institution features |
| `/api/v1/option-features` | GET | Option Greeks |
| `/api/v1/iv-snapshot` | GET | IV snapshot |
| `/api/v1/admin/status` | GET | System status |
| `/api/v1/admin/health` | GET | Health check |

## Data Sources

| Source | Status | Data Types |
|--------|--------|------------|
| CFFEX | Implemented | Daily/Weekly/Monthly quotes, Position ranking |
| SHFE | Implemented | Daily quotes (via AkShare), Option quotes |
| Tushare | Implemented | Minute bars, Greeks, IV, Daily quotes |
| CFMMC | Implemented | Bill auto-download via Selenium |
| DCE | Planned | Daily quotes |
| CZCE | Planned | Daily quotes |
| INE | Planned | Daily quotes |

## Migration Guide

### 12 →3 Database Migration

The migration script consolidates data from 12 legacy SQLite databases into 3 unified databases:

**Source databases:**
- `cffex.db`, `cffex_minute_data.db`, `shfe.db` →`tzdata_market.db`
- `bills.db`, `option_sim.db` →`tzdata_trading.db`
- `institution.db`, `tushare.db`, `trading.db` →`tzdata_analysis.db`

**Column mapping:** The migration automatically maps column names between old and new schemas:

| Source Column | Target Column |
|--------------|---------------|
| `instrument_id` | `contract_code` |
| `open_price` | `open` |
| `close_price` | `close` |
| `settlement_price` | `settle` |
| `pre_settle` | `prev_settle` |
| `change` | `daily_change` |
| `change_pct` | `daily_change_pct` |

**Run migration:**

```bash
# 1. Preview (dry run)
tzdata migrate --dry-run

# 2. Execute
tzdata migrate

# 3. Verify
tzdata migrate --verify
tzdata status
```

**Dual-write strategy:** During the transition period, new data is written to both the legacy databases and the new unified databases. Once all consumers switch to the SDK, the legacy databases can be archived.

### Known Limitations

- Some institution analysis tables (`institution_daily_features`, `institution_master`, `market_regime`, `trading_signals`, `option_features`) have fundamentally different schemas between source and target and require manual migration scripts.
- The `model_validation_records` table has a completely different schema but is mapped via column aliases.
- Tables with no common columns between source and target are skipped during auto-migration.

## Configuration

All paths derive from `TZ_DATA_DIR` environment variable (default: `C:\myspace\tz-data\data`).

Key environment variables:
- `TZ_DATA_DIR` ??Data directory for databases and logs
- `TUSHARE_TOKEN` ??Tushare API token
- `CFMMC_COOKIES_DIR` ??CFMMC cookie directory for bill downloads

See `src/tzdata_pkg/config.py` for exchange-specific settings.

## Project Structure

```
tz-data/
├── pyproject.toml                  # Package definition + dependencies
├── README.md                       # This file
├── docs/
??  └── DATABASE_SCHEMA.md          # Database schema documentation
├── src/tzdata_pkg/
??  ├── __main__.py                 # CLI entry point (Click)
??  ├── config.py                   # Configuration
??  ├── core/                       # Core infrastructure
??  ??  ├── db.py                   # DB connection pool
??  ??  ├── exceptions.py           # Custom exceptions
??  ??  ├── constants.py            # Exchange codes, product definitions
??  ??  └── validators.py           # Data validators
??  ├── storage/                    # Unified storage layer
??  ??  ├── schemas/                # SQL schema files
??  ??  ├── db_registry.py          # DB path + connection management
??  ??  ├── market_store.py         # Market data CRUD
??  ??  ├── trading_store.py        # Trading data CRUD
??  ??  └── analysis_store.py       # Analysis data CRUD
??  ├── download/                   # Exchange downloaders
??  ??  ├── cffex/                  # CFFEX (unified downloader)
??  ??  ├── shfe/                   # SHFE (AkShare)
??  ??  ├── tushare/                # Tushare API
??  ??  └── cfmmc/                  # CFMMC bill download
??  ├── parser/                     # Bill parser (migrated from tz2.0)
??  ??  ├── bill_parser.py          # HTML bill parser
??  ??  └── models.py               # Bill data models
??  ├── query/                      # Python SDK
??  ??  ├── client.py               # TzDataClient main interface
??  ??  ├── market.py               # Market data queries
??  ??  ├── trading.py              # Trading data queries
??  ??  └── analysis.py             # Analysis data queries
??  ├── scheduler/                  # Download scheduler
??  ??  └── scheduler.py            # APScheduler-based job scheduler
??  ├── api/                        # FastAPI service
??  ??  ├── server.py               # FastAPI app
??  ??  └── routes/                 # API route handlers
??  └── migration/                  # Migration tools
??      └── migrate_12_to_3.py      # 12→ DB migration script
└── tests/                          # Test suite
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

Internal use only.
