"""
CLI script for MO option minute data synchronization.

Usage:
    python -m tzdata_pkg.cli.sync_mo_minute contracts                          # 列出合约
    python -m tzdata_pkg.cli.sync_mo_minute full --freq 1min --start 2025-01-01 --end 2026-05-15
    python -m tzdata_pkg.cli.sync_mo_minute incremental --freq 1min
"""
import sys
import argparse
from datetime import datetime, date

from tzdata_pkg.config import get_tushare_config


def list_contracts():
    """List all MO option contracts."""
    from tzdata_pkg.download.tushare.mo_minute_downloader import MOMinuteDownloader

    cfg = get_tushare_config()
    downloader = MOMinuteDownloader(token=cfg.get("token", ""), freq="1min")
    contracts = downloader.get_mo_contracts()
    downloader.close()

    if not contracts:
        print("  (无 MO 合约)")
        return

    print(f"\n{'合约代码':<20} {'类型':<6} {'行权价':<10} {'到期日':<12} {'上市日':<12}")
    print("-" * 70)
    for c in sorted(contracts, key=lambda x: x["contract_code"]):
        opt_type = "看涨" if c["option_type"] == "call" else "看跌"
        print(f"{c['contract_code']:<20} {opt_type:<6} {c['strike']:<10.0f} "
              f"{c['expire_date']:<12} {c['list_date']:<12}")
    print(f"\n共 {len(contracts)} 个合约")


def sync_full(freq: str, start: str, end: str):
    """Full sync for all MO contracts."""
    from tzdata_pkg.download.tushare.mo_minute_downloader import MOMinuteDownloader

    cfg = get_tushare_config()
    token = cfg.get("token", "")
    if not token:
        print("错误: TUSHARE_TOKEN 未配置")
        return

    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()

    print(f"开始全量同步: freq={freq}, {start} -> {end}")
    downloader = MOMinuteDownloader(token=token, freq=freq)

    try:
        result = downloader.download_all_contracts(start_date, end_date)
        total = sum(result.values())
        print(f"\n同步完成: 共 {total} 条分钟K线")
        for code, count in sorted(result.items()):
            if count > 0:
                print(f"  {code}: {count} bars")
    finally:
        downloader.close()


def sync_incremental(freq: str):
    """Incremental sync since last sync date."""
    from tzdata_pkg.download.tushare.mo_minute_downloader import MOMinuteDownloader

    cfg = get_tushare_config()
    token = cfg.get("token", "")
    if not token:
        print("错误: TUSHARE_TOKEN 未配置")
        return

    print(f"开始增量同步: freq={freq}")
    downloader = MOMinuteDownloader(token=token, freq=freq)

    try:
        result = downloader.download_incremental()
        if not result:
            print("  数据已是最新，无需同步")
            return
        total = sum(result.values())
        print(f"\n同步完成: 共 {total} 条新增分钟K线")
        for code, count in sorted(result.items()):
            if count > 0:
                print(f"  {code}: +{count} bars")
    finally:
        downloader.close()


def main():
    parser = argparse.ArgumentParser(description="MO 期权分钟数据同步")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("contracts", help="列出 MO 合约列表")

    full_parser = subparsers.add_parser("full", help="全量同步")
    full_parser.add_argument("--freq", choices=["1min", "5min", "15min", "30min", "60min"],
                             default="1min", help="频率")
    full_parser.add_argument("--start", required=True, help="起始日期 YYYY-MM-DD")
    full_parser.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")

    inc_parser = subparsers.add_parser("incremental", help="增量同步")
    inc_parser.add_argument("--freq", choices=["1min", "5min", "15min", "30min", "60min"],
                            default="1min", help="频率")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "contracts":
        list_contracts()
    elif args.command == "full":
        sync_full(args.freq, args.start, args.end)
    elif args.command == "incremental":
        sync_incremental(args.freq)


if __name__ == "__main__":
    main()
