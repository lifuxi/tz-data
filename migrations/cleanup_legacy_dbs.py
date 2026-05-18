"""Legacy database cleanup script.

Migrates remaining data from 5 legacy databases into tzdata_* unified databases,
then optionally deletes the legacy files.

Legacy DBs:
  - bills.db          → tzdata_trading.db (bills/trades/positions already migrated)
  - cffex.db          → tzdata_market.db  (daily_quotes/position_detail/contracts already migrated)
  - cffex_minute_data → tzdata_market.db  (720 rows NOT yet migrated)
  - institution.db    → tzdata_analysis.db (191K+ rows NOT yet migrated)
  - shfe.db           → tzdata_market.db  (102K options + 9K daily NOT yet migrated)

Usage:
    # Dry run — show what would be migrated
    python migrations/cleanup_legacy_dbs.py --dry-run

    # Execute migration
    python migrations/cleanup_legacy_dbs.py

    # Execute + delete legacy files
    python migrations/cleanup_legacy_dbs.py --delete
"""

import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("tzdata.cleanup")

DATA_DIR = Path(__file__).parent.parent / "data"

# Migration definitions: (legacy_db, legacy_table) -> (target_db, target_table, column_mapping)
MIGRATIONS = [
    # cffex_minute_data.minute_data → tzdata_market.minute_quotes
    {
        "source_db": "cffex_minute_data.db",
        "source_table": "minute_data",
        "target_db": "tzdata_market.db",
        "target_table": "minute_quotes",
        "column_map": {
            "datetime": None,       # skip — split into trade_date + trade_time
            "date": "trade_date",
            "time": "trade_time",
            "product": None,        # skip — use derived value
            "instrument": "contract_code",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "created_at": "created_at",
        },
        "extra_defaults": {
            "exchange": "CFFEX",
            "frequency": "1min",
        },
    },

    # institution.db → tzdata_analysis.db (tables with DIFFERENT schemas)
    # These go to new tables to avoid conflicts with existing target schemas
    {
        "source_db": "institution.db",
        "source_table": "institution_daily_features",
        "target_db": "tzdata_analysis.db",
        "target_table": "legacy_institution_features",
        "column_map": {
            "id": "id",
            "institution_id": "institution_id",
            "product": "product",
            "trade_date": "trade_date",
            "net_position": "net_position",
            "long_volume": "long_volume",
            "short_volume": "short_volume",
            "ewma_net_5": "ewma_net_5",
            "ewma_net_20": "ewma_net_20",
            "ewma_change_10": "ewma_change_10",
            "trend_score": "trend_score",
            "stability_score": "stability_score",
            "n_day_win_rate": "n_day_win_rate",
            "concentration": "concentration",
            "synergy": "synergy",
        },
    },
    {
        "source_db": "institution.db",
        "source_table": "cffex_holdings_continuous",
        "target_db": "tzdata_analysis.db",
        "target_table": "legacy_cffex_holdings",
        "column_map": {
            "id": "id",
            "product": "product",
            "trade_date": "trade_date",
            "contract": "contract",
            "open_price": "open_price",
            "high_price": "high_price",
            "low_price": "low_price",
            "close_price": "close_price",
            "settlement_price": "settlement_price",
            "volume": "volume",
            "open_interest": "open_interest",
            "total_long": "total_long",
            "total_short": "total_short",
            "net_position": "net_position",
            "inst_count": "inst_count",
        },
    },
    {
        "source_db": "institution.db",
        "source_table": "market_regime",
        "target_db": "tzdata_analysis.db",
        "target_table": "legacy_market_regime",
        "column_map": {
            "id": "id",
            "product": "product",
            "trade_date": "trade_date",
            "regime": "regime",
            "confidence": "confidence",
            "price": "price",
            "ma5": "ma5",
            "ma20": "ma20",
            "ma60": "ma60",
            "volatility": "volatility",
            "atr": "atr",
            "adx": "adx",
        },
    },

    # shfe.db → tzdata_market.db
    {
        "source_db": "shfe.db",
        "source_table": "daily_quotes",
        "target_db": "tzdata_market.db",
        "target_table": "daily_quotes",
        "column_map": {
            "instrument_id": "contract_code",
            "trade_date": "trade_date",
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
            "settlement_price": "settle",
            "pre_settle": "prev_settle",
            "volume": "volume",
            "turnover": "turnover",
            "open_interest": "open_interest",
            "change": "daily_change",
            "change_pct": "daily_change_pct",
        },
        "extra_defaults": {
            "exchange": "SHFE",
            "source": "shfe",
        },
    },
    {
        "source_db": "shfe.db",
        "source_table": "shfe_option_quotes",
        "target_db": "tzdata_market.db",
        "target_table": "daily_quotes",
        "column_map": {
            "instrument_id": "contract_code",
            "trade_date": "trade_date",
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
            "settlement_price": "settle",
            "pre_settle": "prev_settle",
            "volume": "volume",
            "turnover": "turnover",
            "open_interest": "open_interest",
        },
        "extra_defaults": {
            "exchange": "SHFE",
            "source": "shfe_option",
        },
    },
    {
        "source_db": "shfe.db",
        "source_table": "contracts",
        "target_db": "tzdata_market.db",
        "target_table": "contracts",
        "column_map": {
            "id": "id",
            "contract_code": "contract_code",
            "variety": "variety",
            "exchange": "exchange",
            "contract_type": "contract_type",
            "multiplier": "multiplier",
            "tick_size": "tick_size",
            "list_date": "listing_date",
            "expire_date": "expiry_date",
            "status": "status",
            # skip: updated_at (not in target)
        },
    },
]

# Tables in legacy DBs that should be DELETED (empty or superseded)
DEPRECATED_TABLES = {
    "bills.db": ["positions", "transactions"],
    "cffex.db": [
        "instruments", "market_data_daily", "market_data_1min", "market_data_5min",
        "market_data_15min", "market_data_30min", "market_data_60min",
        "market_data_weekly", "market_data_monthly",
        "users", "user_sessions", "audit_logs", "audit_log",
        "data_configs", "strategies", "backtests", "orders", "trading_positions",
        "trades", "account_log", "signals", "task_execution_log",
        "data_quality_checks",
    ],
    "institution.db": ["alert_log"],
}

# Legacy DBs that can be fully deleted after migration
LEGACY_DBS_TO_DELETE = [
    "cffex_minute_data.db",
    "shfe.db",
]

# Unique set of target DBs that will be migrated
TARGET_DBS = sorted(set(m["target_db"] for m in MIGRATIONS))


def backup_db(db_path: Path, backup_path: Path):
    """Create a backup of a SQLite database using the online backup API."""
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    src.backup(dst)
    src.close()
    dst.close()


def swap_db(db_path: Path, backup_path: Path):
    """Atomically replace a database with its backup copy.

    Caller must ensure no other process holds the original DB open.
    """
    for ext in ["", "-wal", "-shm", "-journal"]:
        src = Path(str(db_path) + ext)
        bak = Path(str(backup_path) + ext)
        if bak.exists():
            if src.exists():
                src.unlink()
            bak.rename(src)
            logger.info(f"  Swapped {bak.name} → {src.name}")


def migrate_table(src_path: Path, tgt_path: Path, migration: dict, dry_run: bool = False) -> int:
    """Migrate a single table from legacy to target DB."""
    src_table = migration["source_table"]
    tgt_table = migration["target_table"]
    col_map = migration["column_map"]
    defaults = migration.get("extra_defaults", {})

    src_conn = sqlite3.connect(str(src_path))
    tgt_conn = sqlite3.connect(str(tgt_path))

    # Get source columns
    src_cols = [c[1] for c in src_conn.execute(f"PRAGMA table_info({src_table})").fetchall()]
    if not src_cols:
        logger.warning(f"  Source table {src_table} not found in {src_path.name}")
        src_conn.close()
        tgt_conn.close()
        return 0

    # Build column mapping
    if col_map == "auto":
        col_map = {c: c for c in src_cols}

    src_col_list = [c for c in src_cols if c in col_map and col_map[c]]
    tgt_col_list = [col_map[c] for c in src_col_list]
    default_cols = list(defaults.keys())
    all_tgt_cols = tgt_col_list + default_cols

    # Check if target table exists; create it if not
    tgt_exists = tgt_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tgt_table,)
    ).fetchone()
    if not tgt_exists:
        # Build CREATE TABLE from source schema + extra defaults
        src_col_defs = src_conn.execute(f"PRAGMA table_info({src_table})").fetchall()
        col_defs = []
        for cid, cname, ctype, notnull, dflt, pk in src_col_defs:
            if cname not in src_col_list:
                continue
            mapped = col_map[cname]
            def_parts = [f'"{mapped}"', ctype]
            if pk:
                def_parts.append("PRIMARY KEY AUTOINCREMENT")
            elif notnull:
                def_parts.append("NOT NULL")
            col_defs.append(" ".join(def_parts))
        for dc in default_cols:
            col_defs.append(f'"{dc}" TEXT')
        create_sql = f'CREATE TABLE "{tgt_table}" ({", ".join(col_defs)})'
        logger.info(f"  Creating target table: {tgt_table}")
        tgt_conn.execute(create_sql)
        tgt_conn.commit()

    count = src_conn.execute(f"SELECT COUNT(*) FROM {src_table}").fetchone()[0]
    logger.info(f"  Migrating {src_path.name}.{src_table} ({count:,} rows) → {tgt_path.name}.{tgt_table}")

    if dry_run:
        src_conn.close()
        tgt_conn.close()
        return count

    # Read and insert in batches
    placeholders = ", ".join(["?"] * len(all_tgt_cols))
    col_names = ", ".join(all_tgt_cols)
    insert_sql = f"INSERT OR IGNORE INTO {tgt_table} ({col_names}) VALUES ({placeholders})"

    batch = []
    inserted = 0
    for row in src_conn.execute(f"SELECT {', '.join(src_col_list)} FROM {src_table}"):
        values = list(row) + [defaults.get(c) for c in default_cols]
        batch.append(values)
        if len(batch) >= 5000:
            tgt_conn.executemany(insert_sql, batch)
            inserted += len(batch)
            batch = []

    if batch:
        tgt_conn.executemany(insert_sql, batch)
        inserted += len(batch)

    tgt_conn.commit()
    src_conn.close()
    tgt_conn.close()

    logger.info(f"  Inserted {inserted:,} rows into {tgt_table}")
    return inserted


def cleanup_deprecated_tables(db_path: Path, tables: list[str], dry_run: bool = False):
    """Drop deprecated tables from a legacy DB."""
    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    existing = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

    for table in tables:
        if table not in existing:
            continue
        cnt = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
        if dry_run:
            logger.info(f"  Would DROP {db_path.name}.{table} ({cnt} rows)")
        else:
            if cnt > 0:
                logger.warning(f"  DROPPING {db_path.name}.{table} with {cnt} rows — is this intended?")
            conn.execute(f"DROP TABLE IF EXISTS [{table}]")
            logger.info(f"  Dropped {db_path.name}.{table}")

    conn.commit()
    conn.close()


def main():
    dry_run = "--dry-run" in sys.argv
    delete_legacy = "--delete" in sys.argv

    logger.info(f"Legacy Database Cleanup {'(DRY RUN) ' if dry_run else ''}")
    logger.info(f"Data directory: {DATA_DIR}")

    total_rows = 0

    # Phase 0: Create backup copies of target DBs (avoids file locks from running server)
    if not dry_run:
        logger.info("\n=== Phase 0: Create backup copies of target databases ===")
        for db_name in TARGET_DBS:
            db_path = DATA_DIR / db_name
            backup_path = DATA_DIR / f"{db_name}.migration_copy"
            if not db_path.exists():
                logger.warning(f"Target not found: {db_path}")
                continue
            logger.info(f"  Backing up {db_name} → {db_name}.migration_copy")
            backup_db(db_path, backup_path)

    # Phase 1: Migrate remaining data (to backup copies when not dry-run)
    logger.info("\n=== Phase 1: Migrate remaining data ===")
    for mig in MIGRATIONS:
        src = DATA_DIR / mig["source_db"]
        tgt_name = mig["target_db"]
        tgt = DATA_DIR / (tgt_name if dry_run else f"{tgt_name}.migration_copy")

        if not src.exists():
            logger.warning(f"Source not found: {src}")
            continue
        if not tgt.exists():
            logger.warning(f"Target not found: {tgt}")
            continue

        rows = migrate_table(src, tgt, mig, dry_run=dry_run)
        total_rows += rows

    # Phase 2: Clean up deprecated tables (on originals)
    logger.info("\n=== Phase 2: Clean up deprecated tables ===")
    for db_name, tables in DEPRECATED_TABLES.items():
        cleanup_deprecated_tables(DATA_DIR / db_name, tables, dry_run=dry_run)

    # Phase 2b: Swap backup copies back to originals
    if not dry_run and total_rows > 0:
        logger.info("\n=== Phase 2b: Replace original databases with migrated copies ===")
        logger.info("NOTE: This will fail if other processes hold the DBs open.")
        logger.info("Stop the FastAPI server and Celery workers first if swap fails.")
        for db_name in TARGET_DBS:
            db_path = DATA_DIR / db_name
            backup_path = DATA_DIR / f"{db_name}.migration_copy"
            if not backup_path.exists():
                logger.warning(f"Backup not found: {backup_path} — skipping swap")
                continue
            try:
                swap_db(db_path, backup_path)
                # Clean up any remaining backup files
                for ext in ["", "-wal", "-shm", "-journal"]:
                    bak = Path(str(backup_path) + ext)
                    if bak.exists():
                        bak.unlink()
            except Exception as e:
                logger.error(f"  Failed to swap {db_name}: {e}")
                logger.error(f"  Manual fix: stop all processes, then run:")
                logger.error(f"    cp data/{db_name}.migration_copy data/{db_name}")

    # Phase 3: Delete legacy DBs
    if delete_legacy:
        logger.info("\n=== Phase 3: Delete legacy databases ===")
        for db_name in LEGACY_DBS_TO_DELETE:
            db_path = DATA_DIR / db_name
            if db_path.exists():
                size = db_path.stat().st_size
                if dry_run:
                    logger.info(f"  Would delete {db_name} ({size / 1024 / 1024:.1f} MB)")
                else:
                    db_path.unlink()
                    logger.info(f"  Deleted {db_name} ({size / 1024 / 1024:.1f} MB)")

    logger.info(f"\nTotal rows migrated: {total_rows:,}")
    if dry_run:
        logger.info("This was a dry run. Remove --dry-run to execute.")


if __name__ == "__main__":
    main()
