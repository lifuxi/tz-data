"""
Daily data sync for MO system.

Synchronizes IV data (Tushare) and underlying daily bars (akshare)
to tzdata_trading.db. Includes Tushare → akshare fallback.
"""
import logging
import time
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from tzdata_pkg.config import TZDATA_TRADING_DB

logger = logging.getLogger(__name__)

# Target DB: tzdata_trading.db (not bills.db)
TARGET_DB = str(TZDATA_TRADING_DB)

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS option_sim_underlying_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    underlying VARCHAR(20) NOT NULL,
    trade_date VARCHAR(20) NOT NULL,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(underlying, trade_date)
);
"""


def _ensure_underlying_table(conn):
    conn.executescript(TABLE_SQL)


def _safe_float(val):
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return float(val)
    except Exception:
        return None


# ==================== Underlying Daily Sync ====================

def sync_underlying_daily(
    underlyings: list[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Sync underlying daily bar data via akshare.
    Writes to tzdata_trading.db option_sim_underlying_daily.

    Args:
        underlyings: List of underlying codes (default: ['000852', 'IM', '512100', 'A00'])
        start_date: Start date YYYY-MM-DD (default: 1 year ago)
        end_date: End date YYYY-MM-DD (default: today)

    Returns:
        dict with per-underlying sync results.
    """
    if underlyings is None:
        underlyings = ['000852', 'IM', '512100', 'A00']

    now = date.today()
    if not end_date:
        end_date = now.isoformat()
    if not start_date:
        start_date = (now - timedelta(days=365)).isoformat()

    conn = None
    results = {}

    try:
        import akshare as ak

        conn = __import__('sqlite3').connect(TARGET_DB)
        _ensure_underlying_table(conn)

        for code in underlyings:
            try:
                df = _fetch_underlying(ak, code)
                if df is None or df.empty:
                    logger.warning(f"No data fetched for {code}")
                    results[code] = {"status": "no_data", "count": 0}
                    continue

                # Normalize date column
                if 'date' in df.columns:
                    df = df.copy()
                    df['date'] = df['date'].astype(str).str[:10]
                    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

                if df.empty:
                    logger.info(f"No new data for {code} in range {start_date} to {end_date}")
                    results[code] = {"status": "up_to_date", "count": 0}
                    continue

                count = 0
                for _, row in df.iterrows():
                    trade_date = str(row.get('date', ''))[:10]
                    if not trade_date:
                        continue
                    conn.execute("""
                        INSERT OR REPLACE INTO option_sim_underlying_daily
                        (underlying, trade_date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        code,
                        trade_date,
                        _safe_float(row.get('open')),
                        _safe_float(row.get('high')),
                        _safe_float(row.get('low')),
                        _safe_float(row.get('close')),
                        _safe_float(row.get('volume')),
                    ))
                    count += 1

                conn.commit()
                logger.info(f"Synced {count} bars for {code}")
                results[code] = {"status": "ok", "count": count}
                time.sleep(1)  # Rate limit for akshare

            except Exception as e:
                logger.error(f"Failed to sync {code}: {e}")
                results[code] = {"status": "error", "error": str(e)}

    finally:
        if conn:
            conn.close()

    return results


def _fetch_underlying(ak, code: str) -> pd.DataFrame:
    """
    Fetch daily bar data for an underlying code.
    Supports index, futures, ETF, and A50.
    """
    if code == '000852':
        # CSI 1000 index via akshare
        df = ak.stock_zh_index_daily(symbol='sh000852')
        if df is not None and not df.empty and 'volume' in df.columns:
            df = df.copy()
            df['volume'] = df['volume'] / 100  # sina uses 100x scale
        return df

    elif code == 'IM':
        # IM futures main contract
        return ak.futures_zh_daily_sina(symbol='IM0')

    elif code == '512100':
        # CSI 1000 ETF — use direct sina HTTP (akshare em blocked)
        sd = (date.today() - timedelta(days=365)).strftime("%Y%m%d")
        ed = date.today().strftime("%Y%m%d")
        from tzdata_pkg.download.akshare.client import AkshareClient
        return AkshareClient().fetch_etf_daily('512100', start_date=sd, end_date=ed)

    elif code == 'A00':
        # SGX FTSE China A50
        return ak.futures_foreign_hist(symbol='FEF')

    else:
        logger.warning(f"Unknown underlying code: {code}")
        return pd.DataFrame()


# ==================== IV Sync ====================

def sync_iv_daily(
    underlyings: list[str] = None,
    trade_date: Optional[str] = None,
) -> dict:
    """
    Sync option IV data from Tushare for a specific date.

    Args:
        underlyings: List of underlying codes (default: ['MO'])
        trade_date: Date to sync YYYY-MM-DD (default: today)

    Returns:
        dict with per-underlying sync results.
    """
    if underlyings is None:
        underlyings = ['MO']
    if not trade_date:
        trade_date = date.today().isoformat()

    try:
        from tzdata_pkg.config import get_tushare_config
        from tzdata_pkg.download.tushare.client import TushareClient

        tushare_cfg = get_tushare_config()
        client = TushareClient(token=tushare_cfg["token"])
    except Exception as e:
        logger.error(f"Tushare client init failed: {e}")
        return {"error": str(e)}

    conn = None
    results = {}

    try:
        conn = __import__('sqlite3').connect(TARGET_DB)

        # Ensure tables exist
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS option_sim_iv_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                underlying VARCHAR(20) NOT NULL,
                trade_date VARCHAR(20) NOT NULL,
                expiry VARCHAR(20),
                strike FLOAT,
                option_type VARCHAR(10),
                iv FLOAT,
                underlying_price FLOAT,
                source VARCHAR(20) DEFAULT 'market',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(underlying, trade_date, expiry, strike, option_type)
            );
        """)

        date_num = trade_date.replace('-', '')

        for underlying in underlyings:
            try:
                logger.info(f"Fetching IV data for {underlying} on {trade_date}...")

                # Fetch all options for underlying
                all_contracts = client.opt_basic(exchange="CFFEX")
                if all_contracts is None or all_contracts.empty:
                    results[underlying] = {"status": "no_contracts", "count": 0}
                    continue

                # Filter by underlying
                ts_codes = all_contracts.get("ts_code", "")
                if isinstance(ts_codes, pd.Series):
                    mask = ts_codes.str.startswith(underlying, na=False)
                    contracts = all_contracts[mask]
                else:
                    contracts = all_contracts

                logger.info(f"Found {len(contracts)} contracts for {underlying}")

                count = 0
                for _, opt in contracts.iterrows():
                    ts_code = opt.get("ts_code", "")
                    if not ts_code:
                        continue

                    # Fetch daily data for this contract on target date
                    df = client.opt_daily(ts_code, start_date=date_num, end_date=date_num)
                    if df is None or df.empty:
                        continue

                    for _, row in df.iterrows():
                        try:
                            iv = _safe_float(row.get('iv'))
                            # Skip if no IV data
                            if iv is None or iv <= 0:
                                continue

                            # Parse contract details
                            contract_code = _parse_contract_code(ts_code)
                            strike = _parse_strike(ts_code)
                            opt_type = _parse_opt_type(ts_code)
                            expiry = str(opt.get('delist_date', ''))
                            if len(expiry) == 8 and expiry.isdigit():
                                expiry = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}"

                            conn.execute("""
                                INSERT OR REPLACE INTO option_sim_iv_series
                                (underlying, trade_date, expiry, strike, option_type,
                                 iv, underlying_price, source)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 'tushare')
                            """, (
                                underlying,
                                trade_date,
                                expiry if expiry else None,
                                strike,
                                opt_type,
                                iv,
                                _safe_float(row.get('close')),
                            ))
                            count += 1
                        except Exception as e:
                            logger.debug(f"Failed to store IV for {ts_code}: {e}")

                    time.sleep(0.5)  # Rate limit

                conn.commit()
                logger.info(f"Synced {count} IV records for {underlying}")
                results[underlying] = {"status": "ok", "count": count}

            except Exception as e:
                logger.error(f"Failed to sync IV for {underlying}: {e}")
                results[underlying] = {"status": "error", "error": str(e)}

    finally:
        if conn:
            conn.close()

    return results


def _parse_contract_code(ts_code: str) -> str:
    """MO2505C8500.CFFEX -> MO2505-C-8500"""
    import re
    base = ts_code.split(".")[0] if "." in ts_code else ts_code
    match = re.match(r"^([A-Z]+)(\d{4,6})([CP])(\d+)$", base)
    if match:
        return f"{match.group(1)}{match.group(2)}-{match.group(3)}-{match.group(4)}"
    return base


def _parse_strike(ts_code: str) -> float:
    """MO2505C8500.CFFEX -> 8500.0"""
    import re
    base = ts_code.split(".")[0] if "." in ts_code else ts_code
    match = re.match(r"^[A-Z]+\d{4,6}[CP](\d+)$", base)
    if match:
        return float(match.group(1))
    return 0.0


def _parse_opt_type(ts_code: str) -> str:
    """MO2505C8500.CFFEX -> call"""
    base = ts_code.split(".")[0] if "." in ts_code else ts_code
    if 'C' in base.split('-')[0] if '-' in base else base:
        # Find C or P after the date digits
        import re
        match = re.match(r"^[A-Z]+\d{4,6}([CP])", base)
        if match:
            return 'call' if match.group(1) == 'C' else 'put'
    return None


# ==================== Backfill ====================

def backfill_underlying_daily(
    underlyings: list[str] = None,
    start_date: str = '2022-07-01',
) -> dict:
    """Backfill underlying daily data from start_date to today."""
    return sync_underlying_daily(underlyings=underlyings, start_date=start_date)


# ==================== CLI entry point ====================

def run_daily_sync(
    sync_iv: bool = True,
    sync_underlying: bool = True,
    underlyings: list[str] = None,
) -> dict:
    """Run all daily sync tasks."""
    result = {"timestamp": datetime.now().isoformat(), "iv": {}, "underlying": {}}

    if sync_underlying:
        logger.info("=== Syncing underlying daily data ===")
        result["underlying"] = sync_underlying_daily(underlyings=underlyings)

    if sync_iv:
        logger.info("=== Syncing IV data ===")
        result["iv"] = sync_iv_daily()

    result["completed_at"] = datetime.now().isoformat()
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "sync"

    if action == "sync":
        result = run_daily_sync()
        print(f"Sync complete: {result}")
    elif action == "iv":
        result = sync_iv_daily()
        print(f"IV sync complete: {result}")
    elif action == "underlying":
        codes = sys.argv[2:] if len(sys.argv) > 2 else None
        result = sync_underlying_daily(underlyings=codes)
        print(f"Underlying sync complete: {result}")
    elif action == "backfill":
        result = backfill_underlying_daily()
        print(f"Backfill complete: {result}")
    else:
        print(f"Usage: python -m tzdata_pkg.cli.daily_sync [sync|iv|underlying|backfill]")
