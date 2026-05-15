"""
MO data quality checks.

Freshness, completeness, and cross-table consistency checks
for MO system data tables in tzdata_trading.db.
Calendar-driven: lag measured in trading days.
"""
import logging
import sqlite3
from datetime import datetime, timedelta, date
from typing import Dict, List

from tzdata_pkg.config import TZDATA_TRADING_DB

logger = logging.getLogger(__name__)

# Expected underlyings and their data sources
UNDERLYINGS = {
    "000852": {"name": "中证1000指数", "table": "option_sim_underlying_daily"},
    "IM": {"name": "IM期货主力", "table": "option_sim_underlying_daily"},
    "512100": {"name": "中证1000ETF", "table": "option_sim_underlying_daily"},
    "A00": {"name": "A50指数", "table": "option_sim_underlying_daily"},
}

IV_UNDERLYINGS = {
    "MO": {"name": "中证1000期权", "table": "option_sim_iv_series"},
    "HO": {"name": "上证50ETF期权", "table": "option_sim_iv_series"},
    "IO": {"name": "沪深300ETF期权", "table": "option_sim_iv_series"},
}

# Staleness thresholds (trading days)
FRESH_THRESHOLD = 1       # OK: lag <= 1 trading day
STALE_THRESHOLD = 3       # Stale: lag > 3 trading days


def _get_latest_date(conn, table: str, where_clause: str = "", params: tuple = ()) -> str:
    """Get latest trade_date from a table."""
    query = f"SELECT MAX(trade_date) FROM {table}"
    if where_clause:
        query += f" WHERE {where_clause}"
    row = conn.execute(query, params).fetchone()
    return row[0] if row and row[0] else ""


def _get_count(conn, table: str, where_clause: str = "", params: tuple = ()) -> int:
    """Count rows in a table."""
    query = f"SELECT COUNT(*) FROM {table}"
    if where_clause:
        query += f" WHERE {where_clause}"
    row = conn.execute(query, params).fetchone()
    return row[0] if row else 0


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _latest_trading_day_str() -> str:
    """Get the latest CFFEX trading day (previous trading day from today)."""
    try:
        from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator
        dc = DateCalculator()
        return dc.get_prev_trading_day(date.today(), n=1, exchange_code='CFFEX').isoformat()
    except (ValueError, Exception) as e:
        logger.warning(f"Trading calendar unavailable: {e}, falling back to today")
        return _today_str()


def _lag_trading_days(date_str: str) -> int:
    """Calculate lag in trading days from a YYYY-MM-DD string."""
    if not date_str:
        return 999
    try:
        data_date = date.fromisoformat(date_str)
        latest = _parse_latest_trading_day()
        if data_date >= latest:
            return 0

        # Count trading days between data_date and latest
        from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator
        dc = DateCalculator()
        trading_days = dc.get_trading_days_list(data_date, latest, exchange_code='CFFEX')
        return len(trading_days) - 1  # -1 because both ends are included
    except Exception:
        return 999


def _parse_latest_trading_day() -> date:
    """Cached latest trading day for this check run."""
    return date.fromisoformat(_latest_trading_day_str())


def check_data_freshness() -> Dict:
    """
    Check MO data freshness using trading calendar.

    Lag is measured in trading days relative to the latest CFFEX trading day.

    Returns:
        Dict with freshness status for each data source.
    """
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        latest_trading_day = _latest_trading_day_str()
        result = {
            "check_date": _today_str(),
            "latest_trading_day": latest_trading_day,
            "iv": {},
            "underlying": {},
            "overall": "ok",
        }

        # Check IV data freshness
        for code, info in IV_UNDERLYINGS.items():
            latest = _get_latest_date(conn, info["table"], "underlying = ?", (code,))
            lag = _lag_trading_days(latest)
            status = "ok" if lag <= FRESH_THRESHOLD else ("stale" if lag <= STALE_THRESHOLD else "expired")
            result["iv"][code] = {
                "latest_date": latest,
                "lag_trading_days": lag,
                "status": status,
            }
            if status != "ok":
                result["overall"] = "degraded"

        # Check underlying daily data freshness
        for code, info in UNDERLYINGS.items():
            latest = _get_latest_date(conn, info["table"], "underlying = ?", (code,))
            lag = _lag_trading_days(latest)
            status = "ok" if lag <= FRESH_THRESHOLD else ("stale" if lag <= STALE_THRESHOLD else "expired")
            result["underlying"][code] = {
                "latest_date": latest,
                "lag_trading_days": lag,
                "status": status,
            }
            if status != "ok":
                result["overall"] = "degraded"

        # Check if any IV data is expired (> STALE_THRESHOLD trading days)
        expired = [
            code for code, v in result["iv"].items() if v["status"] == "expired"
        ]
        if expired:
            result["overall"] = "error"
            result["expired_iv"] = expired

        # Summary
        total_ok = sum(1 for v in result["iv"].values() if v["status"] == "ok") + \
                   sum(1 for v in result["underlying"].values() if v["status"] == "ok")
        total = len(result["iv"]) + len(result["underlying"])
        result["healthy_ratio"] = round(total_ok / total, 2) if total > 0 else 0

        logger.info(f"Data freshness check: {result['overall']} ({total_ok}/{total} healthy)")
        return result
    finally:
        conn.close()


def check_iv_completeness() -> Dict:
    """
    Check IV data completeness:
    - Contract count per date >= 8 (4 months × 2 directions)
    - IV non-null rate >= 80%

    Returns:
        Dict with completeness stats.
    """
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        result = {"underlying": {}, "issues": []}

        for code, info in IV_UNDERLYINGS.items():
            # Count contracts per date
            date_rows = conn.execute("""
                SELECT trade_date, COUNT(*) as cnt,
                       SUM(CASE WHEN iv IS NOT NULL AND iv > 0 THEN 1 ELSE 0 END) as iv_cnt
                FROM option_sim_iv_series
                WHERE underlying = ?
                GROUP BY trade_date
                ORDER BY trade_date DESC
                LIMIT 30
            """, (code,)).fetchall()

            incomplete_dates = []
            low_iv_dates = []
            for dr in date_rows:
                if dr[1] < 8:
                    incomplete_dates.append(dr[0])
                total = dr[1] if dr[1] > 0 else 1
                iv_rate = dr[2] / total
                if iv_rate < 0.8:
                    low_iv_dates.append({"date": dr[0], "rate": round(iv_rate, 2)})

            result["underlying"][code] = {
                "total_dates": len(date_rows),
                "incomplete_dates": incomplete_dates[:5],  # Last 5
                "low_iv_dates": low_iv_dates[:5],
                "incomplete_count": len(incomplete_dates),
                "low_iv_count": len(low_iv_dates),
            }

            if incomplete_dates:
                result["issues"].append(
                    f"{code}: {len(incomplete_dates)} dates with < 8 contracts"
                )
            if low_iv_dates:
                result["issues"].append(
                    f"{code}: {len(low_iv_dates)} dates with IV non-null rate < 80%"
                )

        return result
    finally:
        conn.close()


def check_cross_table_consistency() -> Dict:
    """
    Check cross-table data consistency:
    - option_sim_underlying_daily dates should match option_sim_iv_series dates
    - Check for date mismatches between different data sources

    Returns:
        Dict with consistency results.
    """
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        result = {"checks": [], "inconsistencies": []}

        # Check 1: IV dates vs underlying dates (should be within 1 trading day)
        iv_latest = _get_latest_date(conn, "option_sim_iv_series", "underlying = ?", ("MO",))
        idx_latest = _get_latest_date(conn, "option_sim_underlying_daily", "underlying = ?", ("000852",))

        iv_lag = _lag_trading_days(iv_latest)
        idx_lag = _lag_trading_days(idx_latest)
        date_diff = abs(iv_lag - idx_lag)

        result["checks"].append({
            "check": "IV vs Index date alignment",
            "iv_latest": iv_latest,
            "idx_latest": idx_latest,
            "iv_lag_trading_days": iv_lag,
            "idx_lag_trading_days": idx_lag,
            "diff_trading_days": date_diff,
            "status": "consistent" if date_diff <= 1 else "inconsistent",
        })

        if date_diff > 1:
            result["inconsistencies"].append(
                f"IV and Index data lag differs by {date_diff} trading days "
                f"(IV: {iv_latest}, Index: {idx_latest})"
            )

        # Check 2: IV underlyings date alignment
        iv_dates = {}
        for code in IV_UNDERLYINGS:
            latest = _get_latest_date(conn, "option_sim_iv_series", "underlying = ?", (code,))
            iv_dates[code] = latest

        for code_a in iv_dates:
            for code_b in iv_dates:
                if code_a >= code_b:
                    continue
                lag_a = _lag_trading_days(iv_dates[code_a])
                lag_b = _lag_trading_days(iv_dates[code_b])
                diff = abs(lag_a - lag_b)
                if diff > 1:
                    result["inconsistencies"].append(
                        f"IV data {code_a} ({iv_dates[code_a]}) and {code_b} ({iv_dates[code_b]}) "
                        f"differ by {diff} trading days"
                    )

        # Check 3: Underlying daily date alignment
        for code_a in UNDERLYINGS:
            for code_b in UNDERLYINGS:
                if code_a >= code_b:
                    continue
                latest_a = _get_latest_date(conn, "option_sim_underlying_daily", "underlying = ?", (code_a,))
                latest_b = _get_latest_date(conn, "option_sim_underlying_daily", "underlying = ?", (code_b,))
                lag_a = _lag_trading_days(latest_a)
                lag_b = _lag_trading_days(latest_b)
                diff = abs(lag_a - lag_b)
                if diff > 1:
                    result["inconsistencies"].append(
                        f"Underlying {code_a} ({latest_a}) and {code_b} ({latest_b}) "
                        f"differ by {diff} trading days"
                    )

        result["overall_status"] = "consistent" if not result["inconsistencies"] else "inconsistent"
        logger.info(f"Cross-table consistency: {result['overall_status']} "
                    f"({len(result['inconsistencies'])} issues)")
        return result
    finally:
        conn.close()


def check_data_quality_summary() -> Dict:
    """Run all checks and return a comprehensive quality summary."""
    freshness = check_data_freshness()
    consistency = check_cross_table_consistency()
    iv_completeness = check_iv_completeness()

    # Determine overall status
    issues = []
    if freshness["overall"] != "ok":
        issues.append(f"Freshness: {freshness['overall']}")
    if consistency["overall_status"] != "consistent":
        issues.extend(consistency["inconsistencies"])
    if iv_completeness["issues"]:
        issues.extend(iv_completeness["issues"])

    return {
        "timestamp": _today_str(),
        "freshness": freshness,
        "consistency": consistency,
        "iv_completeness": iv_completeness,
        "overall_status": "ok" if not issues else "issues_found",
        "issues": issues,
        "issue_count": len(issues),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = check_data_quality_summary()
    import json
    print(json.dumps(summary, indent=2, ensure_ascii=False))
