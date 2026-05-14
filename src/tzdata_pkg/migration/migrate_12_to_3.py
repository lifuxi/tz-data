"""Migration script: 12-DB layout to 3-DB consolidation.

Reads data from legacy databases and writes to unified tzdata_* databases.
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("tzdata.migration")

# Schema files for initializing target DBs
SCHEMA_FILES = {
    "tzdata_market.db": "market.sql",
    "tzdata_trading.db": "trading.sql",
    "tzdata_analysis.db": "analysis.sql",
}

# Market DB migration: source DB -> table mapping
MARKET_MIGRATIONS = {
    "cffex.db": {
        "daily_quotes": "daily_quotes",
        "position_detail": "position_detail",
        "contracts": "contracts",
    },
    "cffex_minute_data.db": {
        "minute_data": "minute_quotes",
    },
    "shfe.db": {
        "daily_quotes": "daily_quotes",
        "shfe_option_quotes": "daily_quotes",
    },
}

# Trading DB migration: source DB -> table mapping
TRADING_MIGRATIONS = {
    "bills.db": {
        "trades": "trades",
        "matched_trades": "matched_trades",
        "trade_performance": "trade_performance",
        "positions_summary": "positions_summary",
        "account_summary": "account_summary",
        "strategy_summary": "strategy_summary",
        "trade_comparison_analysis": "trade_comparison_analysis",
        "cffex_daily_settlement": "cffex_daily_settlement",
        "strategy_performance_summary": "strategy_performance_summary",
        "daily_equity_series": "daily_equity_series",
        "account_cashflow": "account_cashflow",
        "sim_orders": "sim_orders",
        "sim_positions": "sim_positions",
        "sim_account": "sim_account",
        "jq_futures_data": "jq_futures_data",
        "jq_options_data": "jq_options_data",
        "option_sim_iv_series": "option_sim_iv_series",
        "risk_config": "risk_config",
        "reports": "reports",
        "report_templates": "report_templates",
    },
}

# Analysis DB migration: source DB -> table mapping
ANALYSIS_MIGRATIONS = {
    "institution.db": {
        "institution_daily_features": "institution_daily_features",
        "institution_master": "institution_master",
        "institution_name_mapping": "institution_name_mapping",
        "institution_profiles": "institution_profiles",
        "market_regime": "market_regime",
        "trading_signals": "trading_signals",
        "option_features": "option_features",
        "cffex_holdings_continuous": "cffex_holdings_continuous",
        "institution_lead_lag": "institution_lead_lag",
        "model_validation_records": "model_validation_records",
        "feature_daily": "feature_daily",
    },
}


@dataclass
class MigrationReport:
    """Tracks migration results."""
    started_at: str = ""
    completed_at: str = ""
    tables_migrated: int = 0
    rows_migrated: int = 0
    errors: list = field(default_factory=list)
    details: list = field(default_factory=list)

    def to_dict(self):
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "tables_migrated": self.tables_migrated,
            "rows_migrated": self.rows_migrated,
            "errors": self.errors,
        }


# Column name mapping: source column -> target column
COLUMN_MAPPINGS = {
    # daily_quotes: cffex/shfe -> tzdata_market
    "instrument_id": "contract_code",
    "open_price": "open",
    "high_price": "high",
    "low_price": "low",
    "close_price": "close",
    "settlement_price": "settle",
    "pre_settle": "prev_settle",
    "change": "daily_change",
    "change_pct": "daily_change_pct",
    "pre_settlement": "prev_settle",
    # minute_data -> minute_quotes
    "date": "trade_date",
    "instrument": "contract_code",
    # institution_daily_features
    "institution_id": "member_id",
    "net_position": "net_change",
    # model_validation_records: legacy -> new schema
    "product": "model_name",
    "trade_date": "validation_date",
    "model_type": "metric_name",
    "auc": "metric_value",
}


def map_columns(src_cols: list, tgt_cols: list) -> tuple:
    """Map source columns to target columns using COLUMN_MAPPINGS."""
    mapping = {}
    for col in src_cols:
        if col in tgt_cols:
            mapping[col] = col
        elif col in COLUMN_MAPPINGS and COLUMN_MAPPINGS[col] in tgt_cols:
            mapping[col] = COLUMN_MAPPINGS[col]

    if not mapping:
        return [], []
    return list(mapping.keys()), [mapping[k] for k in mapping.keys()]


class MigrationRunner:
    """Handles 12->3 DB migration."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def run(self, dry_run: bool = False) -> MigrationReport:
        """Execute the full migration."""
        report = MigrationReport()
        report.started_at = datetime.now().isoformat()

        logger.info("Starting 12->3 DB migration" + (" (DRY RUN)" if dry_run else ""))

        for db_name, label, migrations in [
            ("tzdata_market.db", "Market", MARKET_MIGRATIONS),
            ("tzdata_trading.db", "Trading", TRADING_MIGRATIONS),
            ("tzdata_analysis.db", "Analysis", ANALYSIS_MIGRATIONS),
        ]:
            target = self.data_dir / db_name
            if not target.exists():
                report.errors.append(f"Target {db_name} does not exist (run status first)")
                continue

            logger.info(f"Migrating {label} data -> {db_name}")
            try:
                migrated = self._migrate_group(target, migrations, dry_run)
                report.tables_migrated += migrated["tables"]
                report.rows_migrated += migrated["rows"]
                report.details.extend(migrated["details"])
            except Exception as e:
                logger.error(f"Migration of {label} failed: {e}")
                report.errors.append(f"{label}: {e}")

        report.completed_at = datetime.now().isoformat()
        logger.info(f"Migration complete: {report.tables_migrated} tables, {report.rows_migrated:,} rows")
        return report

    def _migrate_group(self, target_path: Path, migrations: dict, dry_run: bool) -> dict:
        """Migrate a group of source DBs into one target DB."""
        result = {"tables": 0, "rows": 0, "details": []}

        # Initialize target DB with schema
        schema_name = SCHEMA_FILES.get(target_path.name)
        if schema_name:
            schema_path = Path(__file__).parent.parent / "storage" / "schemas" / schema_name
            if schema_path.exists():
                conn = sqlite3.connect(str(target_path))
                conn.execute("PRAGMA journal_mode=WAL")
                sql_text = schema_path.read_text(encoding="utf-8")
                conn.executescript(sql_text)
                conn.commit()
                conn.close()
                logger.info(f"  Initialized {target_path.name} with {schema_name}")

        target_conn = sqlite3.connect(str(target_path))
        target_conn.execute("PRAGMA journal_mode=WAL")

        for src_name, table_map in migrations.items():
            src_path = self.data_dir / src_name
            if not src_path.exists():
                logger.warning(f"Source {src_name} not found, skipping")
                continue

            src_conn = sqlite3.connect(str(src_path))
            exchange = self._db_to_exchange(src_name)

            for src_table, target_table in table_map.items():
                try:
                    count = self._copy_table(
                        src_conn, src_table, target_conn, target_table, dry_run, exchange,
                    )
                    result["tables"] += 1
                    result["rows"] += count
                    result["details"].append({
                        "source": f"{src_name}/{src_table}",
                        "target": f"{target_path.name}/{target_table}",
                        "rows": count,
                    })
                    logger.info(f"  {src_name}/{src_table} -> {target_table}: {count:,} rows")
                except Exception as e:
                    logger.error(f"  Failed to migrate {src_name}/{src_table}: {e}")
                    result["details"].append({
                        "source": f"{src_name}/{src_table}",
                        "target": f"{target_path.name}/{target_table}",
                        "error": str(e),
                    })

            src_conn.close()

        target_conn.commit()
        target_conn.close()
        return result

    def _db_to_exchange(self, db_name: str) -> str:
        """Infer exchange code from source DB name."""
        name = db_name.lower()
        if "cffex" in name:
            return "CFFEX"
        if "shfe" in name:
            return "SHFE"
        if "institution" in name:
            return "ANALYSIS"
        if "bills" in name:
            return "TRADING"
        return "UNKNOWN"

    def _copy_table(self, src_conn, src_table: str, target_conn, target_table: str,
                    dry_run: bool, exchange: str = None) -> int:
        """Copy data from source table to target table with column mapping."""
        src_exists = src_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (src_table,),
        ).fetchone()
        if not src_exists:
            return 0

        src_cols = [row[1] for row in src_conn.execute(
            f"PRAGMA table_info({src_table})"
        ).fetchall()]
        if not src_cols:
            return 0

        count = src_conn.execute(f"SELECT COUNT(*) FROM {src_table}").fetchone()[0]
        if count == 0:
            return 0

        target_exists = target_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (target_table,),
        ).fetchone()

        if not target_exists:
            if not dry_run:
                col_defs = ", ".join(f"{c} TEXT" for c in src_cols)
                target_conn.execute(
                    f"CREATE TABLE IF NOT EXISTS {target_table} ({col_defs})"
                )
            return count

        target_info = target_conn.execute(
            f"PRAGMA table_info({target_table})"
        ).fetchall()
        target_cols = [row[1] for row in target_info]

        src_use, tgt_use = map_columns(src_cols, target_cols)
        if not src_use:
            return 0

        # Find target NOT NULL columns not covered by mapping
        mapped_target_set = set(tgt_use)
        defaults_needed = {}
        for col_info in target_info:
            col_name, notnull, dflt = col_info[1], col_info[3], col_info[4]
            if col_name not in mapped_target_set and notnull and dflt is None:
                if col_name == "exchange" and exchange:
                    defaults_needed[col_name] = exchange
                elif col_name == "source":
                    defaults_needed[col_name] = "legacy"

        full_tgt_cols = list(tgt_use) + list(defaults_needed.keys())
        full_tgt_list = ", ".join(full_tgt_cols)

        select_parts = list(src_use)
        for col_name, val in defaults_needed.items():
            select_parts.append(f"'{val}' AS {col_name}")
        src_select = ", ".join(select_parts)

        if dry_run:
            return count

        chunk_size = 5000
        offset = 0
        placeholders = ", ".join("?" for _ in full_tgt_cols)
        while offset < count:
            rows = src_conn.execute(
                f"SELECT {src_select} FROM {src_table} LIMIT {chunk_size} OFFSET {offset}"
            ).fetchall()
            if not rows:
                break
            target_conn.executemany(
                f"INSERT OR IGNORE INTO {target_table} ({full_tgt_list}) VALUES ({placeholders})",
                rows,
            )
            offset += chunk_size

        return count

    def verify(self) -> dict:
        """Verify migration by comparing row counts."""
        results = {}

        for db_name, label, migrations in [
            ("tzdata_market.db", "Market", MARKET_MIGRATIONS),
            ("tzdata_trading.db", "Trading", TRADING_MIGRATIONS),
            ("tzdata_analysis.db", "Analysis", ANALYSIS_MIGRATIONS),
        ]:
            target_path = self.data_dir / db_name
            if not target_path.exists():
                continue

            target_conn = sqlite3.connect(str(target_path))

            for src_name, table_map in migrations.items():
                src_path = self.data_dir / src_name
                if not src_path.exists():
                    continue

                src_conn = sqlite3.connect(str(src_path))

                for src_table, target_table in table_map.items():
                    src_count = self._table_count(src_conn, src_table)
                    tgt_count = self._table_count(target_conn, target_table)

                    key = f"{src_name}/{src_table}"
                    results[key] = {
                        "source": src_count,
                        "target": tgt_count,
                        "matched": src_count == tgt_count,
                    }

                src_conn.close()
            target_conn.close()

        return results

    def _table_count(self, conn, table: str) -> int:
        """Get row count for a table, returning 0 if it doesn't exist."""
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not exists:
            return 0
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except Exception:
            return 0
