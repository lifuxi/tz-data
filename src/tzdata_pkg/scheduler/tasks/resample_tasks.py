"""
Celery tasks for OHLCV multi-frequency resampling.

Based on 1-minute bar data, generates 5min/15min/30min/60min K-bars
and writes them to SQLite + QuestDB.
"""
import logging

import pandas as pd

from tzdata_pkg.scheduler.celery_app import celery_app
from tzdata_pkg.scheduler.task_logger import log_beat_task
from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.maintenance.analysis.resampler import TARGET_FREQUENCIES
from tzdata_pkg.maintenance.analysis.resample_writer import ResampleWriter

logger = logging.getLogger(__name__)


@celery_app.task
@log_beat_task
def daily_resample_multi_freq():
    """Daily resampling of latest 1min data into 5min/15min/30min/60min bars.

    Runs at 16:00 on trading days (after market close).
    Only processes the most recent trading day for each contract.
    """
    pool = DBRegistry().get_pool("market")
    results = []

    with pool.connection() as conn:
        # Get all contracts that have 1min data
        cursor = conn.execute("""
            SELECT DISTINCT contract_code
            FROM minute_quotes
            WHERE frequency = '1min'
        """)
        contracts = [row[0] for row in cursor.fetchall()]

    logger.info(f"Resampling task: {len(contracts)} contracts with 1min data")

    for contract in contracts:
        contract_results = {"contract": contract, "freq_results": {}}

        for freq in TARGET_FREQUENCIES:
            try:
                result = _resample_contract_latest(pool, contract, freq)
                contract_results["freq_results"][freq] = result
            except Exception as e:
                logger.warning(f"Resample {contract} @ {freq} failed: {e}")
                contract_results["freq_results"][freq] = {"error": str(e)}

        results.append(contract_results)

    return {"task": "daily_resample_multi_freq", "contracts": len(contracts), "results": results}


def _resample_contract_latest(pool, contract_code: str, freq: str) -> dict:
    """Resample the latest trading day for a contract."""
    with pool.connection() as conn:
        # Get the latest trade date for this contract at 1min
        row = conn.execute("""
            SELECT MAX(trade_date) FROM minute_quotes
            WHERE contract_code = ? AND frequency = '1min'
        """, (contract_code,)).fetchone()

        if not row or not row[0]:
            return {"status": "no_data"}

        latest_date = row[0]

        # Fetch all 1min bars for that date
        cursor = conn.execute("""
            SELECT exchange, contract_code, trade_date, trade_time,
                   open, high, low, close, volume, turnover, open_interest, vwap
            FROM minute_quotes
            WHERE contract_code = ? AND trade_date = ? AND frequency = '1min'
            ORDER BY trade_time
        """, (contract_code, latest_date))

        rows = cursor.fetchall()
        if not rows:
            return {"status": "no_data", "date": latest_date}

    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=[
        "exchange", "contract_code", "trade_date", "trade_time",
        "open", "high", "low", "close", "volume", "turnover",
        "open_interest", "vwap",
    ])

    exchange = df["exchange"].iloc[0]

    result = ResampleWriter.resample_and_write(
        df, freq, contract_code, exchange,
        write_to_sqlite=True,
        write_to_questdb=True,
    )

    return {
        "status": "ok",
        "date": latest_date,
        "input_bars": len(df),
        "output_bars": result.get("validation", {}).get("resampled_bars", 0),
        "sqlite_count": result["sqlite_count"],
        "questdb_count": result["questdb_count"],
        "valid": result.get("validation", {}).get("valid", False),
    }
