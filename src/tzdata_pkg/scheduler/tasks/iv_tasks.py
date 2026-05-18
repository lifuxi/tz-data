"""Celery tasks for IV benchmark and smile snapshot computation.

Scheduled tasks:
- 19:30  Daily IV benchmark computation (compute_iv_benchmark)
- 19:40  IV smile snapshot (compute_iv_smile_snapshot)
- Sat 10:30  IO/HO multi-variety sync (sync_multi_variety_iv)
"""

import json
import logging
from datetime import date, datetime, timedelta

from tzdata_pkg.scheduler.celery_app import celery_app
from tzdata_pkg.scheduler.task_logger import log_beat_task

logger = logging.getLogger(__name__)


@celery_app.task
@log_beat_task
def compute_iv_benchmark():
    """Daily IV benchmark computation for MO/IO/HO.

    Computes ATM IV, HV_20, HV_60, IV-HV spread, skew, term structure,
    percentile, regime, PCR and stores in iv_benchmark table.
    """
    from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader

    trade_date = date.today().isoformat()
    logger.info(f"Computing IV benchmark for {trade_date}")

    downloader = IVBenchmarkDownloader()
    result = downloader.compute_daily(trade_date)

    ok_count = sum(1 for v in result.values() if v.get("status") == "ok")
    logger.info(
        f"IV benchmark {trade_date}: {ok_count}/{len(result)} varieties computed. "
        f"Details: {json.dumps(result, default=str)}"
    )
    return result


@celery_app.task
@log_beat_task
def compute_iv_smile_snapshot():
    """Daily IV smile snapshot for MO/IO/HO.

    Captures smile curve (strike-IV mapping) per expiry and stores
    in iv_smile_snapshot table.
    """
    from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader
    from tzdata_pkg.config import TZDATA_TRADING_DB
    import sqlite3

    trade_date = date.today().isoformat()
    logger.info(f"Computing IV smile snapshot for {trade_date}")

    downloader = IVBenchmarkDownloader()
    downloader._ensure_tables()

    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    total = 0
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS iv_smile_snapshot (
                trade_date   TEXT NOT NULL,
                variety      TEXT NOT NULL,
                expiry_date  TEXT NOT NULL,
                smile_data   TEXT,
                atm_iv       REAL,
                skew_ratio   REAL,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trade_date, variety, expiry_date)
            )
        """)

        for variety in ["MO", "IO", "HO"]:
            rows = conn.execute("""
                SELECT expire_date, strike, iv, option_type
                FROM mo_daily_iv_quotes
                WHERE trade_date = ? AND underlying = ?
                  AND iv IS NOT NULL AND strike IS NOT NULL
                  AND expire_date IS NOT NULL
                ORDER BY expire_date, strike
            """, (trade_date.replace("-", ""), variety)).fetchall()

            if not rows:
                continue

            from collections import defaultdict
            expiry_groups = defaultdict(list)
            for expire_date, strike, iv, opt_type in rows:
                expiry_groups[expire_date].append({
                    "strike": float(strike),
                    "iv": float(iv),
                    "option_type": opt_type,
                })

            for expiry_date in expiry_groups:
                contracts = expiry_groups[expiry_date]
                strikes = sorted(set(c["strike"] for c in contracts))

                call_ivs = []
                put_ivs = []
                for s in strikes:
                    calls = [c for c in contracts if c["option_type"] == "C" and c["strike"] == s]
                    puts = [c for c in contracts if c["option_type"] == "P" and c["strike"] == s]
                    call_ivs.append(calls[0]["iv"] if calls else None)
                    put_ivs.append(puts[0]["iv"] if puts else None)

                # ATM IV (strike closest to midpoint)
                mid_strike = (strikes[0] + strikes[-1]) / 2
                atm_contract = min(contracts, key=lambda c: abs(c["strike"] - mid_strike))
                atm_iv = atm_contract["iv"]

                # Skew ratio: OTM Put IV / OTM Call IV
                otm_put_ivs = [iv for iv in put_ivs if iv is not None]
                otm_call_ivs = [iv for iv in call_ivs if iv is not None]
                skew_ratio = None
                if otm_put_ivs and otm_call_ivs:
                    skew_ratio = sum(otm_put_ivs) / len(otm_put_ivs) / (sum(otm_call_ivs) / len(otm_call_ivs))

                smile_data = json.dumps({
                    "strikes": strikes,
                    "call_iv": call_ivs,
                    "put_iv": put_ivs,
                })

                conn.execute("""
                    INSERT OR REPLACE INTO iv_smile_snapshot
                    (trade_date, variety, expiry_date, smile_data, atm_iv, skew_ratio)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (trade_date, variety, expiry_date, smile_data, round(atm_iv, 4),
                       round(skew_ratio, 4) if skew_ratio else None))

                total += 1

        conn.commit()
    finally:
        conn.close()

    logger.info(f"IV smile snapshot {trade_date}: {total} snapshots stored")
    return {"trade_date": trade_date, "total": total}


@celery_app.task
@log_beat_task
def sync_multi_variety_iv():
    """Saturday IO/HO data sync.

    Downloads IV data for IO and HO varieties to supplement Monday-Friday
    MO-only sync.
    """
    from tzdata_pkg.download.tushare.option_iv_downloader import OptionIVDownloader

    logger.info("Starting multi-variety IV sync (IO/HO)")

    downloader = OptionIVDownloader(varieties=['IO', 'HO'])
    result = downloader.download_incremental(varieties=['IO', 'HO'])

    logger.info(f"Multi-variety IV sync result: {result}")
    return result


@celery_app.task
@log_beat_task
def backfill_iv_benchmark(start_date: str = None, end_date: str = None):
    """Manual backfill task for IV benchmarks.

    Args:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
    """
    from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader

    if not start_date:
        start_date = (date.today() - timedelta(days=90)).isoformat()
    if not end_date:
        end_date = date.today().isoformat()

    logger.info(f"Backfilling IV benchmark: {start_date} to {end_date}")

    downloader = IVBenchmarkDownloader()
    result = downloader.compute_backfill(start_date, end_date)

    logger.info(f"IV benchmark backfill complete: {result}")
    return result
