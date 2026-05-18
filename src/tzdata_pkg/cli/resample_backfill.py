"""
CLI for historical multi-frequency resample backfill.

Reads 1min data from SQLite minute_quotes, resamples into 5min/15min/30min/60min,
and writes results back to SQLite + QuestDB.

Usage:
    python -m tzdata_pkg.cli.resample_backfill --freq 5min
    python -m tzdata_pkg.cli.resample_backfill --freq all
    python -m tzdata_pkg.cli.resample_backfill --freq 5min --contract IF0
    python -m tzdata_pkg.cli.resample_backfill --freq all --date-range 20250101 20251231
"""
import argparse
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

import pandas as pd

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.maintenance.analysis.resampler import TARGET_FREQUENCIES
from tzdata_pkg.maintenance.analysis.resample_writer import ResampleWriter


def get_contracts(pool, contract_filter: str = None) -> list[str]:
    """Get list of contracts that have 1min data."""
    with pool.connection() as conn:
        if contract_filter:
            cursor = conn.execute(
                "SELECT DISTINCT contract_code FROM minute_quotes "
                "WHERE frequency = '1min' AND contract_code = ?",
                (contract_filter,),
            )
        else:
            cursor = conn.execute(
                "SELECT DISTINCT contract_code FROM minute_quotes "
                "WHERE frequency = '1min'"
            )
        return [row[0] for row in cursor.fetchall()]


def get_trade_dates(pool, contract: str, start_date: str = None, end_date: str = None) -> list[str]:
    """Get list of trade dates for a contract."""
    query = (
        "SELECT DISTINCT trade_date FROM minute_quotes "
        "WHERE contract_code = ? AND frequency = '1min'"
    )
    params = [contract]
    if start_date:
        query += " AND trade_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND trade_date <= ?"
        params.append(end_date)
    query += " ORDER BY trade_date"

    with pool.connection() as conn:
        cursor = conn.execute(query, params)
        return [row[0] for row in cursor.fetchall()]


def backfill_contract_date(
    pool,
    contract: str,
    trade_date: str,
    freq: str,
) -> dict:
    """Resample 1min data for a specific contract + date."""
    with pool.connection() as conn:
        cursor = conn.execute("""
            SELECT exchange, contract_code, trade_date, trade_time,
                   open, high, low, close, volume, turnover, open_interest, vwap
            FROM minute_quotes
            WHERE contract_code = ? AND trade_date = ? AND frequency = '1min'
            ORDER BY trade_time
        """, (contract, trade_date))

        rows = cursor.fetchall()
        if not rows:
            return {"status": "no_data"}

    df = pd.DataFrame(rows, columns=[
        "exchange", "contract_code", "trade_date", "trade_time",
        "open", "high", "low", "close", "volume", "turnover",
        "open_interest", "vwap",
    ])

    exchange = df["exchange"].iloc[0]

    result = ResampleWriter.resample_and_write(
        df, freq, contract, exchange,
        write_to_sqlite=True,
        write_to_questdb=True,
    )

    return {
        "status": "ok",
        "input_bars": len(df),
        "output_bars": result.get("validation", {}).get("resampled_bars", 0),
        "sqlite": result["sqlite_count"],
        "questdb": result["questdb_count"],
    }


def run_backfill(
    frequencies: list[str],
    contract_filter: str = None,
    start_date: str = None,
    end_date: str = None,
):
    """Execute backfill for specified frequencies."""
    pool = DBRegistry().get_pool("market")
    contracts = get_contracts(pool, contract_filter)

    if not contracts:
        print("No contracts with 1min data found.")
        return

    print(f"Backfill: {len(contracts)} contracts, frequencies: {frequencies}")
    if start_date:
        print(f"  Date range: {start_date} ~ {end_date or 'now'}")

    total_dates = 0
    total_skipped = 0
    total_written = 0
    t0 = time.time()

    for contract in contracts:
        dates = get_trade_dates(pool, contract, start_date, end_date)
        if not dates:
            continue

        print(f"\n[{contract}] {len(dates)} trading days")

        for trade_date in dates:
            for freq in frequencies:
                result = backfill_contract_date(pool, contract, trade_date, freq)

                if result["status"] == "no_data":
                    total_skipped += 1
                else:
                    total_written += result["output_bars"]

            total_dates += 1

            if total_dates % 50 == 0:
                elapsed = time.time() - t0
                print(f"  Progress: {total_dates} dates processed, "
                      f"{total_written:,} bars written, {total_skipped} skipped "
                      f"({elapsed:.0f}s)")

    elapsed = time.time() - t0
    print(f"\nBackfill complete: {total_dates} dates, {total_written:,} bars written, "
          f"{total_skipped} skipped in {elapsed:.0f}s ({total_written / max(1, elapsed):.0f} bars/s)")


def main():
    parser = argparse.ArgumentParser(description="Resample backfill CLI")
    parser.add_argument(
        "--freq",
        choices=["5min", "15min", "30min", "60min", "all"],
        default="all",
        help="Target frequency (default: all)",
    )
    parser.add_argument(
        "--contract",
        type=str,
        default=None,
        help="Filter by contract code (e.g. IF0)",
    )
    parser.add_argument(
        "--date-range",
        nargs=2,
        metavar=("START", "END"),
        default=None,
        help="Date range YYYYMMDD YYYYMMDD",
    )

    args = parser.parse_args()

    if args.freq == "all":
        frequencies = TARGET_FREQUENCIES
    else:
        frequencies = [args.freq]

    start_date = args.date_range[0] if args.date_range else None
    end_date = args.date_range[1] if args.date_range else None

    run_backfill(frequencies, args.contract, start_date, end_date)


if __name__ == "__main__":
    main()
