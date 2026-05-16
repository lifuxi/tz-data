"""Full historical backfill of MO minute bars from Tushare.

Uses each contract's actual list_date and expire_date to minimize API calls.
Runs in background with rate limit handling.
"""
import logging
import time
import sys
from datetime import date, datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_backfill():
    from tzdata_pkg.download.tushare.mo_minute_downloader import MOMinuteDownloader
    from tzdata_pkg.config import TZDATA_TRADING_DB
    import sqlite3

    downloader = MOMinuteDownloader()

    # Get all contracts with their actual date ranges
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    contracts = conn.execute("""
        SELECT ts_code, contract_code, underlying, expiry_date, strike_price,
               option_type, list_date, delist_date, status
        FROM mo_contract_master
        WHERE underlying = 'MO'
        ORDER BY list_date, strike_price
    """).fetchall()
    conn.close()

    logger.info(f"Total MO contracts: {len(contracts)}")

    # Convert to dict format the downloader expects
    contract_list = []
    for r in contracts:
        ts_code, contract_code, underlying, expiry_date, strike, opt_type, list_dt, delist_dt, status = r

        # Parse dates
        ld = _parse_date(list_dt)
        ed = _parse_date(expiry_date)

        if ld is None:
            continue

        contract_list.append({
            "ts_code": ts_code,
            "contract_code": contract_code,
            "strike": strike or 0.0,
            "option_type": opt_type,
            "expire_date": expiry_date or "",
            "list_date": ld,
            "delist_date": ed,
        })

    logger.info(f"Contracts with valid list_date: {len(contract_list)}")

    # Build set of contracts that already have minute data (skip them)
    conn2 = sqlite3.connect(str(TZDATA_TRADING_DB))
    existing = conn2.execute("""
        SELECT DISTINCT contract_code FROM mo_minute_quotes
    """).fetchall()
    conn2.close()
    existing_contracts = {r[0] for r in existing}
    skip_count = sum(1 for c in contract_list if c["contract_code"] in existing_contracts)
    logger.info(f"Contracts already downloaded: {skip_count}, new to download: {len(contract_list) - skip_count}")

    # Group by list_date to show date range
    if contract_list:
        dates = [c["list_date"] for c in contract_list]
        logger.info(f"Earliest list_date: {min(dates)}, latest: {max(dates)}")

    # Download each contract within its actual trading period
    total_count = 0
    total_contracts = len(contract_list)
    contracts_with_data = 0
    failed_contracts = 0
    api_calls = 0

    for i, c in enumerate(contract_list):
        # Contract's active period: list_date to min(expire_date, today)
        end = c["delist_date"] or date.today()
        if end > date.today():
            end = date.today()

        start = c["list_date"]
        if start > end:
            logger.debug(f"  [{i+1}/{total_contracts}] {c['contract_code']}: no active period ({start} > {end})")
            continue

        # Skip if already has data
        if c["contract_code"] in existing_contracts:
            continue

        logger.info(f"[{i+1}/{total_contracts}] {c['ts_code']} ({c['contract_code']}): {start} to {end}")

        try:
            count = downloader.download_contract(
                c["ts_code"], start, end,
                contract_code=c["contract_code"],
                strike=c["strike"],
                opt_type=c["option_type"],
                expire_date=c["expire_date"],
            )
            total_count += count
            api_calls += _count_monthly_periods(start, end)
            if count > 0:
                contracts_with_data += 1
                logger.info(f"  -> {count} bars")
            else:
                logger.info(f"  -> 0 bars (no data available)")
        except Exception as e:
            failed_contracts += 1
            logger.error(f"  -> Failed: {e}")

        # Rate limit between contracts (reduced from 0.3s for faster backfill)
        time.sleep(0.1)

        # Progress report every 100 contracts (counting only downloaded, not skipped)
        if (i + 1) % 100 == 0 or (i + 1) == total_contracts:
            logger.info(f"PROGRESS: {i+1}/{total_contracts} contracts processed, {total_count:,} bars, {contracts_with_data} new data, {failed_contracts} failed, {skip_count} skipped")

    logger.info(f"DONE: {total_contracts} contracts processed")
    logger.info(f"Total bars: {total_count:,}")
    logger.info(f"Contracts with data: {contracts_with_data}")
    logger.info(f"Failed contracts: {failed_contracts}")
    logger.info(f"API calls made: {api_calls}")

    downloader.close()


def _parse_date(s):
    if not s or s == "None" or s == "":
        return None
    s = str(s).strip()
    if len(s) == 10:
        s = s.replace("-", "")
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None


def _count_monthly_periods(start, end):
    """Count the number of month-boundary splits for a date range."""
    months = 0
    current = start
    while current <= end:
        months += 1
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)
    return months


if __name__ == "__main__":
    run_backfill()
