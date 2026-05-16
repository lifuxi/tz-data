"""MO minute bar backfill - single threaded, optimized.

Skips already-downloaded contracts. Uses minimal sleep times.
Run with: python -u src/tzdata_pkg/cli/mo_minute_backfill_v2.py
"""
import sys
import time
import sqlite3
import logging
from datetime import date

# Unbuffered output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _parse_date(s):
    if not s or s == "None" or s == "":
        return None
    s = str(s).strip()
    if len(s) == 10:
        s = s.replace("-", "")
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None


def run():
    from tzdata_pkg.config import TZDATA_TRADING_DB
    from tzdata_pkg.download.tushare.mo_minute_downloader import MOMinuteDownloader
    from tzdata_pkg.download.tushare.client import TushareClient

    DB_PATH = str(TZDATA_TRADING_DB)

    # Get contracts
    conn = sqlite3.connect(DB_PATH)
    contracts = conn.execute("""
        SELECT ts_code, contract_code, strike_price, option_type, list_date, expiry_date
        FROM mo_contract_master WHERE underlying = 'MO'
    """).fetchall()
    conn.close()

    existing_conn = sqlite3.connect(DB_PATH)
    existing_set = {r[0] for r in existing_conn.execute("SELECT DISTINCT contract_code FROM mo_minute_quotes").fetchall()}
    existing_conn.close()

    # Filter to download
    to_download = []
    for r in contracts:
        ts_code, contract_code, strike, opt_type, list_dt, expiry_dt = r
        ld = _parse_date(list_dt)
        ed = _parse_date(expiry_dt) or date.today()
        if ed > date.today():
            ed = date.today()
        if ld and ld <= ed and contract_code not in existing_set:
            to_download.append((ts_code, contract_code, strike or 0.0, opt_type, expiry_dt or "", ld, ed))

    logger.info(f"Total contracts: {len(contracts)}, existing: {len(existing_set)}, to download: {len(to_download)}")

    if not to_download:
        logger.info("All done!")
        return

    # Create downloader once
    downloader = MOMinuteDownloader()
    # Reduce client rate limit
    downloader._client._rate_limit = 0.3

    total_bars = 0
    total_ok = 0
    total_fail = 0
    start_time = time.time()

    for i, (ts_code, contract_code, strike, opt_type, expire_date, start, end) in enumerate(to_download):
        try:
            count = downloader.download_contract(
                ts_code, start, end,
                contract_code=contract_code,
                strike=strike,
                opt_type=opt_type,
                expire_date=expire_date,
            )
            total_bars += count
            total_ok += 1
            logger.info(f"[{total_ok}/{len(to_download)}] {contract_code}: {count:,} bars ({i+1}/{len(to_download)})")
        except Exception as e:
            total_fail += 1
            logger.error(f"[FAIL {total_fail}] {contract_code}: {e}")

        # Minimal sleep between contracts
        time.sleep(0.05)

        # Progress every 10
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / (elapsed / 60) if elapsed > 0 else 0
            remaining = len(to_download) - (i + 1)
            eta_min = remaining / rate if rate > 0 else 999
            logger.info(f"PROGRESS: {i+1}/{len(to_download)} done, {total_bars:,} bars, rate={rate:.1f}/min, ETA={eta_min:.0f}min")

    elapsed = time.time() - start_time
    downloader.close()
    logger.info(f"DONE in {elapsed/60:.1f}min: {total_ok} OK, {total_fail} failed, {total_bars:,} bars")


if __name__ == "__main__":
    run()
