"""
Schema alignment verification script.

Compares actual SQLite table columns against tzdata_pkg.models canonical
definitions. Reports missing/extra columns so migration can proceed safely.

Usage:
    python -m tzdata_pkg.cli.verify_schema_alignment
    python migrations/verify_schema_alignment.py
"""
import sqlite3
import sys
import os
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.system("chcp 65001 >NUL 2>&1")

# Shared tables: tzdata_pkg.models defines the canonical schema
CANONICAL_COLUMNS = {
    "bills": [
        "id", "account_id", "bill_date_start", "bill_date_end",
        "client_id", "client_name", "currency", "file_path", "status",
        "balance_bf", "balance_cf", "deposit_withdrawal", "realized_pl",
        "mtm_pl", "exercise_pl", "commission", "premium_received",
        "premium_paid", "client_equity", "fund_available",
        "margin_occupied", "created_at",
    ],
    "trades": [
        "id", "account_id", "year", "month", "trade_date", "exchange",
        "product", "instrument", "direction", "offset_flag", "volume",
        "price", "turnover", "commission", "total_pnl", "premium",
        "trade_id", "position_type", "created_at",
    ],
    "positions_summary": [
        "id", "account_id", "year", "month", "trade_date", "instrument",
        "exchange", "product", "long_position", "short_position",
        "prev_settlement", "settlement_price", "accumulated_pnl",
        "margin_occupied", "float_pl", "created_at",
    ],
    "account_summary": [
        "id", "account_id", "year", "month", "start_date", "end_date",
        "balance_b_f", "balance_c_f", "deposit_withdrawal", "total_pnl",
        "accumulated_pnl", "exercise_pnl", "commission", "client_equity",
        "margin_occupied", "fund_available", "risk_degree", "margin_call",
        "premium_received", "premium_paid", "market_value_long",
        "market_value_short", "market_value_equity", "created_at",
    ],
    "matched_trades": [
        "id", "instrument", "exchange", "product", "is_option",
        "open_trade_id", "open_date", "open_price", "open_volume",
        "open_premium", "open_direction", "close_trade_id", "close_date",
        "close_price", "close_volume", "close_premium", "holding_days",
        "price_pnl", "premium_pnl", "money_pnl", "commission",
        "net_pnl", "status",
    ],
}

# tz2.0-specific columns (allowed to be extra on certain tables)
TZ2_ONLY_COLUMNS = {
    "bills": ["total_records", "parse_error"],
    "trades": ["order_type", "slippage", "strategy_tag", "trade_time", "vwap"],
    "matched_trades": ["multiplier"],
}

# Old columns that have been REMOVED in the new schema
DEPRECATED_COLUMNS = {
    "trades": ["bill_id"],
    "positions_summary": ["bill_id", "client_id", "avg_buy_price", "avg_sell_price",
                          "mtm_pl", "speculation_hedge", "market_value_long", "market_value_short"],
    "account_summary": ["client_id"],
}


def get_actual_columns(db_path: str) -> dict[str, list[str]]:
    """Read actual table columns from SQLite database."""
    conn = sqlite3.connect(db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()

    result = {}
    for (table_name,) in tables:
        if table_name.startswith("sqlite_"):
            continue
        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        result[table_name] = [c[1] for c in cols]

    conn.close()
    return result


def verify_alignment(db_path: str) -> dict:
    """Compare actual columns against canonical definitions."""
    actual = get_actual_columns(db_path)

    report = {
        "db": db_path,
        "tables_checked": 0,
        "tables_missing": [],
        "tables_ok": [],
        "tables_with_issues": [],
        "details": {},
    }

    for table_name, canonical_cols in CANONICAL_COLUMNS.items():
        report["tables_checked"] += 1

        if table_name not in actual:
            report["tables_missing"].append(table_name)
            report["details"][table_name] = {"status": "MISSING"}
            continue

        actual_cols = set(actual[table_name])
        canonical_set = set(canonical_cols)
        tz2_only = set(TZ2_ONLY_COLUMNS.get(table_name, []))
        deprecated = set(DEPRECATED_COLUMNS.get(table_name, []))

        # Columns in DB but not in canonical (excluding tz2.0 extras)
        extra = actual_cols - canonical_set - tz2_only
        # Columns in canonical but not in DB
        missing = canonical_set - actual_cols
        # Deprecated columns still present
        still_deprecated = deprecated & actual_cols

        issues = []
        if missing:
            issues.append(f"MISSING columns: {sorted(missing)}")
        if extra:
            issues.append(f"EXTRA columns (not in canonical or tz2-allowed): {sorted(extra)}")
        if still_deprecated:
            issues.append(f"DEPRECATED columns still present: {sorted(still_deprecated)}")

        if issues:
            report["tables_with_issues"].append(table_name)
            report["details"][table_name] = {
                "status": "ISSUES",
                "issues": issues,
                "actual_cols": sorted(actual_cols),
            }
        else:
            report["tables_ok"].append(table_name)
            report["details"][table_name] = {
                "status": "OK",
                "col_count": len(actual_cols & canonical_set | tz2_only),
            }

    return report


def print_report(report: dict):
    """Print a human-readable migration report."""
    print(f"\n{'='*60}")
    print(f"Schema Alignment Report: {report['db']}")
    print(f"{'='*60}")

    print(f"\nTables checked: {report['tables_checked']}")
    print(f"OK: {len(report['tables_ok'])}")
    print(f"With issues: {len(report['tables_with_issues'])}")
    print(f"Missing tables: {len(report['tables_missing'])}")

    if report["tables_ok"]:
        print(f"\n[OK] {', '.join(report['tables_ok'])}")

    if report["tables_with_issues"]:
        print(f"\n[ISSUES]:")
        for table in report["tables_with_issues"]:
            detail = report["details"][table]
            print(f"\n  [{table}]")
            for issue in detail["issues"]:
                print(f"    - {issue}")

    if report["tables_missing"]:
        print(f"\n[MISSING] tables: {', '.join(report['tables_missing'])}")

    # Migration readiness
    all_ok = len(report["tables_with_issues"]) == 0 and len(report["tables_missing"]) == 0
    print(f"\n{'='*60}")
    if all_ok:
        print("STATUS: ALL TABLES ALIGNED - safe to proceed with migration")
    else:
        print("STATUS: MIGRATION BLOCKED - resolve issues above first")
    print(f"{'='*60}\n")


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/tzdata_trading.db"

    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        print("Usage: python verify_schema_alignment.py <db_path>")
        sys.exit(1)

    report = verify_alignment(db_path)
    print_report(report)

    # Exit with error code if migration is blocked
    if report["tables_with_issues"] or report["tables_missing"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
