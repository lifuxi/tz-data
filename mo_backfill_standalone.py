"""Standalone MO minute bar backfill.

No tzdata_pkg imports. Uses raw sqlite3 + direct Tushare API calls.
"""
import sqlite3
import time
import requests
import sys
from datetime import date, timedelta

DB_PATH = r"C:\myspace\tz-data\data\tzdata_trading.db"
# Get token from system_config DB
def get_token():
    conn = sqlite3.connect(r"C:\myspace\tz-data\data\tzdata_market.db")
    r = conn.execute("SELECT config_value FROM system_config WHERE config_key = 'tushare.token'").fetchone()
    conn.close()
    return r[0] if r else ""

# TUSHARE_TOKEN = get_token()
TUSHARE_TOKEN = "ddaece0dddfdeb0ea99e80f7f63b06a97772ebd731b14095b1f8e566"
TUSHARE_URL = "http://api.tushare.pro"

def _parse_date(s):
    if not s or s == "None" or s == "":
        return None
    s = str(s).strip()
    if len(s) == 10:
        s = s.replace("-", "")
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return None

_last_call = 0

def call_api(method, **kwargs):
    """Call Tushare API with rate limiting."""
    global _last_call
    now = time.time()
    elapsed = now - _last_call
    if elapsed < 0.35:
        time.sleep(0.35 - elapsed)
    _last_call = time.time()

    payload = {
        "api_name": method,
        "token": TUSHARE_TOKEN,
        "params": kwargs,
        "fields": "ts_code,trade_time,open,close,high,low,vol,amount,oi"
    }
    resp = requests.post(TUSHARE_URL, json=payload, timeout=30)
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Tushare error: {data.get('msg')}")
    items = data.get("data", {}).get("items", [])
    fields = data.get("data", {}).get("fields", [])
    return items, fields

def download_contract(ts_code, start, end, contract_code, strike, opt_type, expire_date):
    """Download minute bars for one contract, split by month."""
    count = 0
    current = start
    conn = sqlite3.connect(DB_PATH)

    while current <= end:
        # Month boundary
        if current.month == 12:
            month_end = current.replace(year=current.year + 1, month=1, day=1)
        else:
            month_end = current.replace(month=current.month + 1, day=1)
        actual_end = min(month_end, end + timedelta(days=1)) - timedelta(days=1)

        sd = current.strftime("%Y%m%d")
        ed = actual_end.strftime("%Y%m%d")

        try:
            items, fields = call_api("opt_mins", ts_code=ts_code, freq="1min", start_date=sd, end_date=ed)
            if items:
                # Map fields to values
                col_map = {f: i for i, f in enumerate(fields)}
                rows = []
                for item in items:
                    trade_time = str(item[col_map.get("trade_time", 0)])
                    if " " in trade_time:
                        trade_date = trade_time.split(" ", 1)[0].replace("-", "")
                    elif len(trade_time) >= 8:
                        trade_date = trade_time[:8]
                    else:
                        continue

                    def sf(name):
                        idx = col_map.get(name)
                        if idx is None or item[idx] is None:
                            return None
                        try:
                            return float(item[idx])
                        except:
                            return None

                    rows.append((
                        trade_time, trade_date, contract_code, "MO",
                        opt_type, strike if strike > 0 else None,
                        expire_date if expire_date else None,
                        sf("open"), sf("high"), sf("low"), sf("close"),
                        sf("vol"), sf("amount"), sf("oi"), "1min"
                    ))

                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=10000")
                conn.executemany("""
                    INSERT OR REPLACE INTO mo_minute_quotes
                    (trade_time, trade_date, contract_code, underlying,
                     option_type, strike, expire_date,
                     open, high, low, close, volume, turnover, open_interest, frequency)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows)
                conn.commit()
                count += len(rows)
        except Exception as e:
            pass  # Log error but continue

        # Next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1, day=1)
        else:
            current = current.replace(month=current.month + 1, day=1)

    conn.close()
    return count

def main():
    print(f"[{time.strftime('%H:%M:%S')}] Getting contracts...", flush=True)
    conn = sqlite3.connect(DB_PATH)
    contracts = conn.execute("""
        SELECT ts_code, contract_code, strike_price, option_type, list_date, expiry_date
        FROM mo_contract_master WHERE underlying = 'MO'
    """).fetchall()

    existing_set = {r[0] for r in conn.execute("SELECT DISTINCT contract_code FROM mo_minute_quotes").fetchall()}
    conn.close()

    print(f"[{time.strftime('%H:%M:%S')}] Total: {len(contracts)}, Existing: {len(existing_set)}", flush=True)

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

    total_bars = 0
    total_ok = 0
    total_fail = 0
    start_time = time.time()

    for i, (ts_code, contract_code, strike, opt_type, expire_date, start, end) in enumerate(to_download):
        try:
            count = download_contract(ts_code, start, end, contract_code, strike, opt_type, expire_date)
            total_bars += count
            total_ok += 1
            if count > 0:
                print(f"[{time.strftime('%H:%M:%S')}] [{total_ok}] {contract_code}: {count:,} bars", flush=True)
        except Exception as e:
            total_fail += 1
            print(f"[{time.strftime('%H:%M:%S')}] [FAIL] {contract_code}: {e}", flush=True)

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / (elapsed / 60) if elapsed > 0 else 0
            remaining = len(to_download) - (i + 1)
            eta_min = remaining / rate if rate > 0 else 999
            print(f"[{time.strftime('%H:%M:%S')}] PROGRESS: {i+1}/{len(to_download)}, {total_bars:,} bars, rate={rate:.1f}/min, ETA={eta_min:.0f}min", flush=True)

    elapsed = time.time() - start_time
    print(f"DONE in {elapsed/60:.1f}min: {total_ok} OK, {total_fail} failed, {total_bars:,} bars", flush=True)

if __name__ == "__main__":
    main()
