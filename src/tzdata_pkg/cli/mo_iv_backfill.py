"""MO option IV backfill CLI.

Usage:
    python -m tzdata_pkg.cli.mo_iv_backfill --start 2022-07-22 --end 2026-05-14
    python -m tzdata_pkg.cli.mo_iv_backfill --start 2026-05-01  # to today
    python -m tzdata_pkg.cli.mo_iv_backfill --incremental        # since last stored date
"""
import argparse
import logging
import time
from datetime import date, datetime

from tzdata_pkg.download.tushare.mo_iv_downloader import MOIVDownloader

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="MO option IV backfill")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--incremental", action="store_true", help="Incremental sync")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    downloader = MOIVDownloader()
    try:
        if args.incremental:
            print(f"[{time.strftime('%H:%M:%S')}] Running incremental IV sync...", flush=True)
            result = downloader.download_incremental()
            print(f"Result: {result}", flush=True)
        elif args.start:
            start_date = date.fromisoformat(args.start)
            end_date = date.fromisoformat(args.end) if args.end else date.today()

            print(
                f"[{time.strftime('%H:%M:%S')}] Backfilling IV: {start_date} to {end_date}",
                flush=True,
            )

            t0 = time.time()
            result = downloader.backfill(start_date, end_date)
            elapsed = time.time() - t0

            print(
                f"DONE in {elapsed/60:.1f}min: "
                f"{result['total_success']} IVs calculated, "
                f"{result['total_fail']} failed",
                flush=True,
            )
        else:
            parser.print_help()
    finally:
        downloader.close()


if __name__ == "__main__":
    main()
