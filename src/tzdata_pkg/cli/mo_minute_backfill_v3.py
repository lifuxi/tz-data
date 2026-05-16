"""MO minute bar backfill - standalone script.

No tzdata_pkg imports at module level. Only imports inside the worker function
to avoid spawning unwanted processes during startup.
"""
import sys
import os
import time
import sqlite3
from datetime import date

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

def _parse_date(s):
    if not s or s == "None" or s == "":
        return None
    s = str(s).strip()
    if len(s) == 10:
        s = s.replace("-", "")
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None


def main():
    DB_PATH = r"C:\myspace\tz-data\data\tzdata_trading.db"

    print(f"[{time.strftime('%H:%M:%S')}] Connecting to DB...", flush=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)

    contracts = conn.execute("""
        SELECT ts_code, contract_code, strike_price, option_type, list_date, expiry_date
        FROM mo_contract_master WHERE underlying = 'MO'
    """).fetchall()

    existing_set = {r[0] for r in conn.execute("SELECT DISTINCT contract_code FROM mo_minute_quotes").fetchall()}
    conn.close()

    print(f"[{time.strftime('%H:%M:%S')}] Total: {len(contracts)}, Existing: {len(existing_set)}", flush=True)

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

    print(f"[{time.strftime('%H:%M:%S')}] To download: {len(to_download)}", flush=True)

    if not to_download:
        print("All done!", flush=True)
        return

    # Now import tzdata_pkg modules (after DB queries are done)
    from tzdata_pkg.download.tushare.mo_minute_downloader import MOMinuteDownloader

    downloader = MOMinuteDownloader()
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
            if count > 0:
                print(f"[{time.strftime('%H:%M:%S')}] [{total_ok}] {contract_code}: {count:,} bars", flush=True)
        except Exception as e:
            total_fail += 1
            print(f"[{time.strftime('%H:%M:%S')}] [FAIL] {contract_code}: {e}", flush=True)

        time.sleep(0.05)

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / (elapsed / 60) if elapsed > 0 else 0
            remaining = len(to_download) - (i + 1)
            eta_min = remaining / rate if rate > 0 else 999
            print(f"[{time.strftime('%H:%M:%S')}] PROGRESS: {i+1}/{len(to_download)}, {total_bars:,} bars, {rate:.1f}/min, ETA={eta_min:.0f}min", flush=True)

    elapsed = time.time() - start_time
    downloader.close()
    print(f"DONE in {elapsed/60:.1f}min: {total_ok} OK, {total_fail} failed, {total_bars:,} bars", flush=True)


if __name__ == "__main__":
    main()
