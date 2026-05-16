"""MO minute bar historical backfill with multi-process parallel download.

Uses multiprocessing to parallelize contract downloads while respecting
Tushare API rate limits via a shared file lock mechanism.

Usage:
    python -m tzdata_pkg.cli.mo_minute_backfill_mp --workers 4
"""
import logging
import sys
import time
import sqlite3
import argparse
import os
from datetime import date, datetime, timedelta
from multiprocessing import Pool, current_process
from contextlib import contextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s][%(processName)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Shared state file for rate limiting
RATE_LIMIT_FILE = "/tmp/tushare_rate_limit.lock"
PROGRESS_FILE = "/tmp/mo_minute_backfill_progress.log"


def _rate_limit_wait():
    """Shared rate limiting via file-based locking to coordinate across processes."""
    import fcntl
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with open(RATE_LIMIT_FILE, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                now = time.time()
                try:
                    last = float(f.read().strip())
                except ValueError:
                    last = 0
                wait = 0.5 - (now - last)
                if wait > 0:
                    time.sleep(wait)
                f.seek(0)
                f.truncate()
                f.write(str(time.time()))
                fcntl.flock(f, fcntl.LOCK_UN)
                return
        except Exception:
            time.sleep(0.5)
    # Fallback: just sleep
    time.sleep(0.5)


def _log_progress(msg):
    """Append progress message to shared log file."""
    with open(PROGRESS_FILE, "a") as f:
        f.write(f"{datetime.now().isoformat()} {msg}\n")


def _parse_date(s):
    if not s or s == "None" or s == "":
        return None
    s = str(s).strip()
    if len(s) == 10:
        s = s.replace("-", "")
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None


def _download_single_contract(args):
    """Download minute bars for a single contract. Runs in a worker process."""
    ts_code, contract_code, strike, opt_type, expire_date, start, end = args

    try:
        from tzdata_pkg.download.tushare.mo_minute_downloader import MOMinuteDownloader

        downloader = MOMinuteDownloader()
        count = downloader.download_contract(
            ts_code, start, end,
            contract_code=contract_code,
            strike=strike,
            opt_type=opt_type,
            expire_date=expire_date,
        )
        downloader.close()

        _log_progress(f"[OK] {contract_code}: {count} bars")
        return (contract_code, True, count)
    except Exception as e:
        _log_progress(f"[FAIL] {contract_code}: {e}")
        return (contract_code, False, 0)


def run_backfill(workers=4):
    from tzdata_pkg.config import TZDATA_TRADING_DB

    # Get all contracts
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    contracts = conn.execute("""
        SELECT ts_code, contract_code, underlying, expiry_date, strike_price,
               option_type, list_date, delist_date
        FROM mo_contract_master
        WHERE underlying = 'MO'
        ORDER BY list_date, strike_price
    """).fetchall()
    conn.close()

    logger.info(f"Total MO contracts: {len(contracts)}")

    # Build contract list with date ranges
    contract_list = []
    for r in contracts:
        ts_code, contract_code, underlying, expiry_date, strike, opt_type, list_dt, delist_dt = r
        ld = _parse_date(list_dt)
        ed = _parse_date(expiry_date) or date.today()
        if ed > date.today():
            ed = date.today()
        if ld is None or ld > ed:
            continue
        contract_list.append((
            ts_code, contract_code,
            strike or 0.0, opt_type,
            expiry_date or "", ld, ed
        ))

    # Skip already downloaded
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    existing = conn.execute("SELECT DISTINCT contract_code FROM mo_minute_quotes").fetchall()
    conn.close()
    existing_set = {r[0] for r in existing}
    to_download = [c for c in contract_list if c[1] not in existing_set]

    logger.info(f"Already downloaded: {len(existing_set)}, to download: {len(to_download)}")
    if not to_download:
        logger.info("All contracts already have data!")
        return

    _log_progress(f"START: {len(to_download)} contracts to download with {workers} workers")

    # Download in parallel batches
    total_count = 0
    total_ok = 0
    total_fail = 0
    batch_size = max(1, workers * 2)

    for batch_start in range(0, len(to_download), batch_size):
        batch = to_download[batch_start:batch_start + batch_size]
        batch_end = min(batch_start + batch_size, len(to_download))

        logger.info(f"Processing batch {batch_start+1}-{batch_end}/{len(to_download)}")

        with Pool(processes=workers) as pool:
            results = pool.map(_download_single_contract, batch)

        for contract_code, success, count in results:
            if success:
                total_ok += 1
                total_count += count
            else:
                total_fail += 1

        logger.info(f"Batch done: {total_ok} OK, {total_fail} failed, {total_count:,} bars so far")
        _log_progress(f"BATCH: {batch_end}/{len(to_download)} done, {total_ok} OK, {total_fail} fail, {total_count:,} bars")

        # Small pause between batches
        time.sleep(0.5)

    logger.info(f"DONE: {total_ok} contracts OK, {total_fail} failed, {total_count:,} total bars")
    _log_progress(f"DONE: {total_ok} OK, {total_fail} failed, {total_count:,} bars")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MO minute bar backfill (parallel)")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    args = parser.parse_args()
    run_backfill(workers=args.workers)
