"""
Option Contract Master Sync.

Creates and populates option contract master tables for MO/HO/IO
from Tushare opt_basic.
"""
import logging
import sqlite3
from datetime import datetime

import pandas as pd

from tzdata_pkg.config import TZDATA_TRADING_DB

logger = logging.getLogger(__name__)

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mo_contract_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    contract_code TEXT NOT NULL,
    underlying TEXT NOT NULL DEFAULT 'MO',
    expiry_date TEXT,
    strike_price REAL,
    option_type TEXT,
    list_date TEXT,
    delist_date TEXT,
    last_trade_date TEXT,
    exercise_date TEXT,
    multiplier REAL DEFAULT 100.0,
    tick_size REAL DEFAULT 0.2,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ts_code)
);
CREATE INDEX IF NOT EXISTS idx_mo_contract_underlying ON mo_contract_master(underlying);
CREATE INDEX IF NOT EXISTS idx_mo_contract_expiry ON mo_contract_master(expiry_date);
CREATE INDEX IF NOT EXISTS idx_mo_contract_status ON mo_contract_master(status);
CREATE INDEX IF NOT EXISTS idx_mo_contract_type ON mo_contract_master(option_type);
"""


PRODUCTS = {
    "MO": {"name": "中证1000期权", "multiplier": 100.0, "tick_size": 0.2},
    "HO": {"name": "上证50ETF期权", "multiplier": 10000.0, "tick_size": 0.0001},
    "IO": {"name": "沪深300ETF期权", "multiplier": 10000.0, "tick_size": 0.0001},
}


def _ensure_table(conn):
    """Create mo_contract_master table if not exists."""
    conn.executescript(TABLE_SQL)


def _parse_contract_code(ts_code: str) -> str:
    """
    Parse Tushare format to short contract code.
    e.g. 'MO2505C8500.CFFEX' -> 'MO2505-C-8500'
    """
    import re
    base = ts_code.split(".")[0] if "." in ts_code else ts_code
    match = re.match(r"^([A-Z]+)(\d{4,6})([CP])(\d+)$", base)
    if match:
        return f"{match.group(1)}{match.group(2)}-{match.group(3)}-{match.group(4)}"
    return base


def _parse_option_type(call_put: str) -> str:
    """Map call_put to option_type."""
    if call_put and str(call_put).upper() == 'C':
        return 'call'
    return 'put'


def _normalize_date(date_str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD."""
    if date_str is None or pd.isna(date_str):
        return None
    s = str(date_str).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) == 10:
        return s
    return None


def sync_option_contracts(product: str = 'MO', force: bool = False) -> dict:
    """
    Sync option contract metadata from Tushare opt_basic.

    Args:
        product: 'MO', 'HO', or 'IO'
        force: If True, re-sync all contracts (including existing ones).

    Returns:
        dict with inserted/updated/total counts.
    """
    if product not in PRODUCTS:
        raise ValueError(f"Unknown product: {product}. Must be one of {list(PRODUCTS.keys())}")

    from tzdata_pkg.config import get_tushare_config
    from tzdata_pkg.download.tushare.client import TushareClient

    tushare_cfg = get_tushare_config()
    client = TushareClient(token=tushare_cfg["token"])

    logger.info(f"Fetching {product} contracts from Tushare opt_basic...")
    df = client.opt_basic(exchange="CFFEX")
    if df is None or df.empty:
        logger.warning("Tushare opt_basic returned no data")
        return {"inserted": 0, "updated": 0, "total": 0}

    # Filter by product
    ts_codes = df.get("ts_code", "")
    if isinstance(ts_codes, pd.Series):
        mask = ts_codes.str.startswith(product, na=False)
        df = df[mask]

    logger.info(f"Found {len(df)} {product} contracts from Tushare")

    cfg = PRODUCTS[product]
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        _ensure_table(conn)

        inserted = 0
        updated = 0

        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code", "")).strip()
            if not ts_code:
                continue

            contract_code = _parse_contract_code(ts_code)
            call_put = row.get("call_put", "")
            option_type = _parse_option_type(call_put)
            strike = row.get("exercise_price")
            if strike is not None and pd.isna(strike):
                strike = None
            else:
                strike = float(strike) if strike is not None else None

            expiry_date = _normalize_date(row.get("delist_date") or row.get("exercise_date"))
            list_date = _normalize_date(row.get("list_date"))
            delist_date = _normalize_date(row.get("delist_date"))
            last_trade_date = _normalize_date(row.get("last_trade_date"))
            exercise_date = _normalize_date(row.get("exercise_date"))

            existing = conn.execute(
                "SELECT id, status FROM mo_contract_master WHERE ts_code = ?",
                (ts_code,)
            ).fetchone()

            if existing and not force:
                # Update delist_date and status if contract was delisted
                if delist_date and existing[1] == "active":
                    conn.execute("""
                        UPDATE mo_contract_master
                        SET delist_date = ?, exercise_date = ?,
                            status = 'delisted', updated_at = CURRENT_TIMESTAMP
                        WHERE ts_code = ?
                    """, (delist_date, exercise_date, ts_code))
                    updated += 1
                continue

            if existing and force:
                conn.execute("""
                    UPDATE mo_contract_master
                    SET contract_code = ?, underlying = ?, expiry_date = ?, strike_price = ?,
                        option_type = ?, list_date = ?, delist_date = ?,
                        last_trade_date = ?, exercise_date = ?,
                        multiplier = ?, tick_size = ?,
                        status = 'active', updated_at = CURRENT_TIMESTAMP
                    WHERE ts_code = ?
                """, (contract_code, product, expiry_date, strike, option_type,
                      list_date, delist_date, last_trade_date, exercise_date,
                      cfg["multiplier"], cfg["tick_size"], ts_code))
                updated += 1
            else:
                conn.execute("""
                    INSERT OR IGNORE INTO mo_contract_master
                        (ts_code, contract_code, underlying, expiry_date, strike_price,
                         option_type, list_date, delist_date, last_trade_date,
                         exercise_date, multiplier, tick_size, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """, (ts_code, contract_code, product, expiry_date, strike, option_type,
                      list_date, delist_date, last_trade_date, exercise_date,
                      cfg["multiplier"], cfg["tick_size"]))
                if conn.total_changes > 0:
                    inserted += 1

        conn.commit()
        logger.info(f"Synced {product} contracts: {inserted} inserted, {updated} updated, {len(df)} total")
        return {"inserted": inserted, "updated": updated, "total": len(df)}
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to sync {product} contracts: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def sync_mo_contracts(force: bool = False) -> dict:
    """Backward-compatible wrapper. Syncs MO/HO/IO contracts with single API call."""
    from tzdata_pkg.config import get_tushare_config
    from tzdata_pkg.download.tushare.client import TushareClient

    tushare_cfg = get_tushare_config()
    client = TushareClient(token=tushare_cfg["token"])

    # Single API call — fetch all CFFEX options at once
    logger.info("Fetching all CFFEX contracts from Tushare opt_basic (single call)...")
    df = client.opt_basic(exchange="CFFEX")
    if df is None or df.empty:
        logger.warning("Tushare opt_basic returned no data")
        return {"inserted": 0, "updated": 0, "total": 0}

    results = {}
    for product in PRODUCTS:
        ts_codes = df.get("ts_code", "")
        if isinstance(ts_codes, pd.Series):
            mask = ts_codes.str.startswith(product, na=False)
            product_df = df[mask]
        else:
            product_df = df[:0]  # empty

        results[product] = _sync_product(product, product_df, force)

    total_inserted = sum(r.get('inserted', 0) for r in results.values())
    total_updated = sum(r.get('updated', 0) for r in results.values())
    total_all = sum(r.get('total', 0) for r in results.values())
    return {"inserted": total_inserted, "updated": total_updated, "total": total_all, "details": results}


def _sync_product(product: str, df, force: bool) -> dict:
    """Sync contracts for a single product from a pre-fetched DataFrame."""
    if df is None or df.empty:
        logger.warning(f"Tushare opt_basic returned no data for {product}")
        return {"inserted": 0, "updated": 0, "total": 0}

    logger.info(f"Found {len(df)} {product} contracts from Tushare")
    cfg = PRODUCTS[product]
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        _ensure_table(conn)

        inserted = 0
        updated = 0

        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code", "")).strip()
            if not ts_code:
                continue

            contract_code = _parse_contract_code(ts_code)
            call_put = row.get("call_put", "")
            option_type = _parse_option_type(call_put)
            strike = row.get("exercise_price")
            if strike is not None and pd.isna(strike):
                strike = None
            else:
                strike = float(strike) if strike is not None else None

            expiry_date = _normalize_date(row.get("delist_date") or row.get("exercise_date"))
            list_date = _normalize_date(row.get("list_date"))
            delist_date = _normalize_date(row.get("delist_date"))
            last_trade_date = _normalize_date(row.get("last_trade_date"))
            exercise_date = _normalize_date(row.get("exercise_date"))

            existing = conn.execute(
                "SELECT id, status FROM mo_contract_master WHERE ts_code = ?",
                (ts_code,)
            ).fetchone()

            if existing and not force:
                if delist_date and existing[1] == "active":
                    conn.execute("""
                        UPDATE mo_contract_master
                        SET delist_date = ?, exercise_date = ?,
                            status = 'delisted', updated_at = CURRENT_TIMESTAMP
                        WHERE ts_code = ?
                    """, (delist_date, exercise_date, ts_code))
                    updated += 1
                continue

            if existing and force:
                conn.execute("""
                    UPDATE mo_contract_master
                    SET contract_code = ?, underlying = ?, expiry_date = ?, strike_price = ?,
                        option_type = ?, list_date = ?, delist_date = ?,
                        last_trade_date = ?, exercise_date = ?,
                        multiplier = ?, tick_size = ?,
                        status = 'active', updated_at = CURRENT_TIMESTAMP
                    WHERE ts_code = ?
                """, (contract_code, product, expiry_date, strike, option_type,
                      list_date, delist_date, last_trade_date, exercise_date,
                      cfg["multiplier"], cfg["tick_size"], ts_code))
                updated += 1
            else:
                conn.execute("""
                    INSERT OR IGNORE INTO mo_contract_master
                        (ts_code, contract_code, underlying, expiry_date, strike_price,
                         option_type, list_date, delist_date, last_trade_date,
                         exercise_date, multiplier, tick_size, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """, (ts_code, contract_code, product, expiry_date, strike, option_type,
                      list_date, delist_date, last_trade_date, exercise_date,
                      cfg["multiplier"], cfg["tick_size"]))
                if conn.total_changes > 0:
                    inserted += 1

        conn.commit()
        logger.info(f"Synced {product} contracts: {inserted} inserted, {updated} updated, {len(df)} total")
        return {"inserted": inserted, "updated": updated, "total": len(df)}
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to sync {product} contracts: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def get_mo_contracts(active_only: bool = True, product: str = None) -> list[dict]:
    """Get option contracts from master table.

    Args:
        active_only: Filter active contracts only
        product: 'MO', 'HO', 'IO', or None for all
    """
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        _ensure_table(conn)
        conditions = ["status = 'active'"] if active_only else []
        params = []
        if product:
            conditions.append("underlying = ?")
            params.append(product)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = conn.execute(f"""
            SELECT ts_code, contract_code, underlying, expiry_date, strike_price,
                   option_type, list_date, delist_date, status
            FROM mo_contract_master {where}
            ORDER BY underlying, expiry_date, strike_price, option_type
        """, params).fetchall()
        return [
            {
                "ts_code": r[0],
                "contract_code": r[1],
                "underlying": r[2],
                "expiry_date": r[3],
                "strike_price": r[4],
                "option_type": r[5],
                "list_date": r[6],
                "delist_date": r[7],
                "status": r[8],
            }
            for r in rows
        ]
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = sync_mo_contracts()
    print(f"Result: {result}")
