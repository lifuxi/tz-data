"""Phase 2: Migrate remaining bills/cffex/institution legacy databases.

Phase 1 (cleanup_legacy_dbs.py) already migrated:
  - cffex_minute_data.db (720 rows → minute_quotes)
  - shfe.db (111K rows → daily_quotes + contracts)
  - institution.db feature tables → legacy_* tables

Phase 2 handles:
  1. bills.db — already fully in tzdata_trading.db, just verify & drop
  2. cffex.db — migrate daily_quotes (860K) + position_detail delta (7K)
     + contracts → tzdata_market.db
  3. institution.db — migrate ALL remaining tables (schemas differ from
     existing tzdata_analysis.db placeholders) into tz2.0-compatible tables
     so tz2.0 can switch its config to read from tzdata_analysis.db

Usage:
    python migrations/phase2_cleanup_legacy_dbs.py --dry-run
    python migrations/phase2_cleanup_legacy_dbs.py
    python migrations/phase2_cleanup_legacy_dbs.py --delete
"""

import logging
import os
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("tzdata.cleanup.phase2")

DATA_DIR = Path(__file__).parent.parent / "data"


# ── Migration definitions ──────────────────────────────────────────

MIGRATIONS = [
    # ── cffex.db → tzdata_market.db ──────────────────────────────
    {
        "source_db": "cffex.db",
        "source_table": "daily_quotes",
        "target_db": "tzdata_market.db",
        "target_table": "daily_quotes",
        "column_map": {
            "id": "id",
            "trade_date": "trade_date",
            "instrument_id": "contract_code",
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
            "settlement_price": "settle",
            "volume": "volume",
            "turnover": "turnover",
            "open_interest": "open_interest",
            "change": "daily_change",
            "change_pct": "daily_change_pct",
            # skip: created_at, updated_at, adj_close (not in target)
        },
        "extra_defaults": {
            "exchange": "CFFEX",
            "source": "cffex",
            "prev_settle": None,       # NULL for CFFEX data
            "amplitude": None,
        },
    },
    {
        "source_db": "cffex.db",
        "source_table": "position_detail",
        "target_db": "tzdata_market.db",
        "target_table": "position_detail",
        "column_map": {
            "id": "id",
            "trade_date": "trade_date",
            "instrument_id": "contract_code",
            "member_name": "member_name",
            "long_volume": "long_volume",
            "short_volume": "short_volume",
            "long_change": "long_change",
            "short_change": "short_change",
            # skip: created_at, updated_at
        },
        "extra_defaults": {
            "exchange": "CFFEX",
            "product": None,
            "rank": None,
            "source": "cffex",
        },
    },
    {
        "source_db": "cffex.db",
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
            "last_trade_date": "delisting_date",
            "status": "status",
            # skip: created_at, updated_at
        },
    },

    # ── institution.db → tzdata_analysis.db ──────────────────────
    # Tables that DON'T exist in target yet — create from source schema
    {
        "source_db": "institution.db",
        "source_table": "institution_master",
        "target_db": "tzdata_analysis.db",
        "target_table": "institution_master",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "institution_name_mapping",
        "target_db": "tzdata_analysis.db",
        "target_table": "institution_name_mapping",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "institution_profiles",
        "target_db": "tzdata_analysis.db",
        "target_table": "institution_profiles",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "institution_daily_features",
        "target_db": "tzdata_analysis.db",
        "target_table": "institution_daily_features",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "cffex_holdings_continuous",
        "target_db": "tzdata_analysis.db",
        "target_table": "cffex_holdings_continuous",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "market_regime",
        "target_db": "tzdata_analysis.db",
        "target_table": "market_regime",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "trading_signals",
        "target_db": "tzdata_analysis.db",
        "target_table": "trading_signals",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "signal_triggers",
        "target_db": "tzdata_analysis.db",
        "target_table": "signal_triggers",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "option_features",
        "target_db": "tzdata_analysis.db",
        "target_table": "option_features",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "feature_daily",
        "target_db": "tzdata_analysis.db",
        "target_table": "legacy_feature_daily",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "institution_lead_lag",
        "target_db": "tzdata_analysis.db",
        "target_table": "institution_lead_lag",
        "column_map": "auto",
    },
    {
        "source_db": "institution.db",
        "source_table": "model_validation_records",
        "target_db": "tzdata_analysis.db",
        "target_table": "legacy_model_validation",
        "column_map": "auto",
    },
]

# Tables in institution.db to drop after migration
INSTITUTION_DROP_TABLES = [
    "legacy_institution_features",
    "legacy_cffex_holdings",
    "legacy_market_regime",
]

LEGACY_DBS_TO_DELETE = ["bills.db", "cffex.db", "institution.db"]

TARGET_DBS = sorted(set(m["target_db"] for m in MIGRATIONS))


def backup_db(db_path: Path, backup_path: Path):
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    src.backup(dst)
    src.close()
    dst.close()


def _create_table_from_source(src_conn, tgt_conn, src_table, tgt_table,
                              col_map, src_col_list, default_cols):
    """Create target table from source schema."""
    src_col_defs = src_conn.execute(f"PRAGMA table_info({src_table})").fetchall()
    col_defs = []
    pk_cols = []
    for cid, cname, ctype, notnull, dflt, pk in src_col_defs:
        if cname not in src_col_list:
            continue
        mapped = col_map[cname]
        if pk:
            pk_cols.append(mapped)
        def_parts = [f'"{mapped}"', ctype]
        if pk and ctype.upper().startswith("INTEGER"):
            def_parts.append("PRIMARY KEY")
        elif notnull:
            def_parts.append("NOT NULL")
        col_defs.append(" ".join(def_parts))
    if len(pk_cols) > 1:
        col_defs.append(f"PRIMARY KEY ({', '.join(pk_cols)})")
    for dc in default_cols:
        col_defs.append(f'"{dc}" TEXT')
    create_sql = f'CREATE TABLE "{tgt_table}" ({", ".join(col_defs)})'
    tgt_conn.execute(create_sql)
    tgt_conn.commit()


def swap_db(db_path: Path, backup_path: Path):
    for ext in ["", "-wal", "-shm", "-journal"]:
        src = Path(str(db_path) + ext)
        bak = Path(str(backup_path) + ext)
        if bak.exists():
            if src.exists():
                src.unlink()
            bak.rename(src)
            logger.info(f"  Swapped {bak.name} → {src.name}")


def migrate_table(src_path: Path, tgt_path: Path, migration: dict, dry_run: bool = False) -> int:
    src_table = migration["source_table"]
    tgt_table = migration["target_table"]
    col_map = migration["column_map"]
    defaults = migration.get("extra_defaults", {})

    src_conn = sqlite3.connect(str(src_path))
    tgt_conn = sqlite3.connect(str(tgt_path))

    src_cols = [c[1] for c in src_conn.execute(f"PRAGMA table_info({src_table})").fetchall()]
    if not src_cols:
        logger.warning(f"  Source table {src_table} not found in {src_path.name}")
        src_conn.close()
        tgt_conn.close()
        return 0

    if col_map == "auto":
        col_map = {c: c for c in src_cols}

    src_col_list = [c for c in src_cols if c in col_map and col_map[c]]
    tgt_col_list = [col_map[c] for c in src_col_list]
    default_cols = list(defaults.keys())
    all_tgt_cols = tgt_col_list + default_cols

    # Create target table if it doesn't exist, or drop/recreate if schema mismatches
    tgt_exists = tgt_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tgt_table,)
    ).fetchone()
    if not tgt_exists:
        _create_table_from_source(src_conn, tgt_conn, src_table, tgt_table,
                                  col_map, src_col_list, default_cols)
    else:
        # Check if target table is empty and has different schema
        existing_rows = tgt_conn.execute(f"SELECT COUNT(*) FROM {tgt_table}").fetchone()[0]
        tgt_cols = {c[1] for c in tgt_conn.execute(f"PRAGMA table_info({tgt_table})").fetchall()}
        needed_cols = set(all_tgt_cols)
        if existing_rows == 0 and not needed_cols.issubset(tgt_cols):
            # Empty table with wrong schema — drop and recreate
            tgt_conn.execute(f"DROP TABLE IF EXISTS [{tgt_table}]")
            _create_table_from_source(src_conn, tgt_conn, src_table, tgt_table,
                                      col_map, src_col_list, default_cols)
            logger.info(f"  Dropped empty {tgt_table} with wrong schema, recreated from source")

    # Check existing rows to calculate delta
    existing = tgt_conn.execute(f"SELECT COUNT(*) FROM {tgt_table}").fetchone()[0]

    count = src_conn.execute(f"SELECT COUNT(*) FROM {src_table}").fetchone()[0]
    new_rows = count - existing
    label = f"{src_path.name}.{src_table} ({count:,} rows, ~{new_rows:,} new)"
    logger.info(f"  Migrating {label} → {tgt_path.name}.{tgt_table}")

    if dry_run:
        src_conn.close()
        tgt_conn.close()
        return count

    # INSERT OR IGNORE (by primary key or unique constraint)
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

    logger.info(f"  Inserted {inserted:,} rows (total now: {existing + inserted:,})")
    return inserted


def main():
    dry_run = "--dry-run" in sys.argv
    delete_legacy = "--delete" in sys.argv

    logger.info(f"Phase 2 Legacy Cleanup {'(DRY RUN) ' if dry_run else ''}")
    logger.info(f"Data directory: {DATA_DIR}")

    total_rows = 0

    # Phase 0: Verify bills.db
    logger.info("\n=== Phase 0: Verify bills.db migration status ===")
    bills_src = DATA_DIR / "bills.db"
    trading_tgt = DATA_DIR / "tzdata_trading.db"
    if bills_src.exists() and trading_tgt.exists():
        for table in ["bills", "trades", "positions_summary"]:
            src_cnt = sqlite3.connect(str(bills_src)).execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            tgt_cnt = sqlite3.connect(str(trading_tgt)).execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            status = "OK" if src_cnt == tgt_cnt else f"MISMATCH (source={src_cnt}, target={tgt_cnt})"
            logger.info(f"  {table}: {src_cnt:,} rows — {status}")
    else:
        logger.warning("  bills.db or tzdata_trading.db not found")

    # Phase 1: Backup target DBs
    if not dry_run:
        logger.info("\n=== Phase 1: Create backup copies of target databases ===")
        for db_name in TARGET_DBS:
            db_path = DATA_DIR / db_name
            backup_path = DATA_DIR / f"{db_name}.p2_copy"
            if not db_path.exists():
                logger.warning(f"Target not found: {db_path}")
                continue
            logger.info(f"  Backing up {db_name} → {db_name}.p2_copy")
            backup_db(db_path, backup_path)

    # Phase 2: Migrate
    logger.info("\n=== Phase 2: Migrate remaining data ===")
    for mig in MIGRATIONS:
        src = DATA_DIR / mig["source_db"]
        tgt_name = mig["target_db"]
        tgt = DATA_DIR / (tgt_name if dry_run else f"{tgt_name}.p2_copy")

        if not src.exists():
            logger.warning(f"Source not found: {src}")
            continue
        if not tgt.exists():
            logger.warning(f"Target not found: {tgt}")
            continue

        rows = migrate_table(src, tgt, mig, dry_run=dry_run)
        total_rows += rows

    # Phase 3: Drop Phase 1 legacy tables
    if not dry_run and total_rows > 0:
        logger.info("\n=== Phase 3: Drop Phase 1 legacy tables from analysis.db ===")
        analysis_copy = DATA_DIR / "tzdata_analysis.db.p2_copy"
        if analysis_copy.exists():
            conn = sqlite3.connect(str(analysis_copy))
            for table in INSTITUTION_DROP_TABLES:
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if exists:
                    conn.execute(f"DROP TABLE IF EXISTS [{table}]")
                    logger.info(f"  Dropped {table}")
            conn.commit()
            conn.close()

    # Phase 4: Swap copies back
    if not dry_run and total_rows > 0:
        logger.info("\n=== Phase 4: Replace original databases with migrated copies ===")
        logger.info("NOTE: Stop FastAPI/Celery if swap fails due to file locks.")
        for db_name in TARGET_DBS:
            db_path = DATA_DIR / db_name
            backup_path = DATA_DIR / f"{db_name}.p2_copy"
            if not backup_path.exists():
                logger.warning(f"Backup not found: {backup_path} — skipping swap")
                continue
            try:
                swap_db(db_path, backup_path)
                for ext in ["", "-wal", "-shm", "-journal"]:
                    bak = Path(str(backup_path) + ext)
                    if bak.exists():
                        bak.unlink()
            except Exception as e:
                logger.error(f"  Failed to swap {db_name}: {e}")
                logger.error(f"  Manual fix: stop all processes, then:")
                logger.error(f"    cp data/{db_name}.p2_copy data/{db_name}")

    # Phase 5: Delete legacy DBs
    if delete_legacy:
        logger.info("\n=== Phase 5: Delete legacy databases ===")
        for db_name in LEGACY_DBS_TO_DELETE:
            db_path = DATA_DIR / db_name
            if db_path.exists():
                size = db_path.stat().st_size
                if dry_run:
                    logger.info(f"  Would delete {db_name} ({size / 1024 / 1024:.1f} MB)")
                else:
                    db_path.unlink()
                    logger.info(f"  Deleted {db_name} ({size / 1024 / 1024:.1f} MB)")

    logger.info(f"\nTotal rows processed: {total_rows:,}")
    if dry_run:
        logger.info("This was a dry run. Remove --dry-run to execute.")


if __name__ == "__main__":
    main()
