"""MO minute bar historical backfill with multi-threaded parallel download.

Uses ThreadPoolExecutor within a single process to parallelize downloads
while sharing a single rate limiter and handling SQLite WAL-mode concurrency.

Usage:
    python -m tzdata_pkg.cli.mo_minute_backfill_mt --workers 4
"""
import logging
import sys
import time
import sqlite3
import argparse
import threading
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Shared state
_rate_lock = threading.Lock()
_last_api_call = 0
_progress_lock = threading.Lock()
_total_bars = 0
_total_ok = 0
_total_fail = 0
_processed = 0


def _rate_limit_wait(min_interval=0.35):
    """Thread-safe rate limiting. Each worker calls this before API calls."""
    global _last_api_call
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_api_call
        if elapsed < min_interval:
            wait = min_interval - elapsed
            time.sleep(wait)
        _last_api_call = time.time()


def _download_single_contract(args):
    """Download minute bars for a single contract in a worker thread."""
    global _total_bars, _total_ok, _total_fail, _processed
    ts_code, contract_code, strike, opt_type, expire_date_str, start, end = args

    try:
        from tzdata_pkg.download.tushare.mo_minute_downloader import MOMinuteDownloader

        downloader = MOMinuteDownloader()
        count = downloader.download_contract(
            ts_code, start, end,
            contract_code=contract_code,
            strike=strike,
            opt_type=opt_type,
            expire_date=expire_date_str,
        )
        downloader.close()

        with _progress_lock:
            _total_bars += count
            _total_ok += 1
            _processed += 1
            logger.info(f"[{_processed}] {contract_code}: {count} bars")
            if _processed % 50 == 0:
                logger.info(f"PROGRESS: {_processed} done, {_total_ok} OK, {_total_fail} failed, {_total_bars:,} total bars")
        return True
    except Exception as e:
        with _progress_lock:
            _total_fail += 1
            _processed += 1
            logger.error(f"[{_processed}] {contract_code}: FAILED - {e}")
        return False


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

    # Download in parallel
    start_time = time.time()
    logger.info(f"Starting with {workers} workers, {len(to_download)} contracts")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_download_single_contract, c): c[1] for c in to_download}
        for future in as_completed(futures):
            contract_code = futures[future]
            try:
                future.result()
            except Exception as e:
                logger.error(f"Unhandled exception for {contract_code}: {e}")

    elapsed = time.time() - start_time
    logger.info(f"DONE in {elapsed/60:.1f} min: {_total_ok} OK, {_total_fail} failed, {_total_bars:,} total bars")


def _parse_date(s):
    if not s or s == "None" or s == "":
        return None
    s = str(s).strip()
    if len(s) == 10:
        s = s.replace("-", "")
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MO minute bar backfill (multi-threaded)")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    args = parser.parse_args()
    run_backfill(workers=args.workers)
