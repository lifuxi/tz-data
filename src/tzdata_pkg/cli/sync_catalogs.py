"""
CLI script for data catalog synchronization.

Usage:
    python -m tzdata_pkg.cli.sync_catalogs list
    python -m tzdata_pkg.cli.sync_catalogs sync --id 1 --mode incremental
    python -m tzdata_pkg.cli.sync_catalogs sync --id 1 --mode full --start 2025-01-01 --end 2026-05-15
    python -m tzdata_pkg.cli.sync_catalogs sync-all --mode incremental
"""
import sys
import argparse
from datetime import date, datetime

DATA_TYPE_LABELS = {
    'daily': '日线行情',
    'minute': '分钟行情',
    'top20_holdings': 'Top20持仓',
}


def list_catalogs():
    """List all data catalogs."""
    from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

    catalogs = CatalogManager.list_catalogs()
    if not catalogs:
        print("  (无数据目录)")
        return

    print(f"\n{'ID':<4} {'目录名称':<25} {'交易所':<8} {'品种':<6} {'数据类型':<12} {'数据源':<15} {'启用':<4} {'最后同步'}")
    print("-" * 120)
    for c in catalogs:
        dtype = DATA_TYPE_LABELS.get(c['data_type'], c['data_type'])
        enabled = '是' if c['is_enabled'] else '否'
        last_sync = c.get('last_sync_at', '-') or '-'
        print(f"{c['id']:<4} {c['catalog_name']:<25} {c['exchange_code']:<8} {c['product_code'] or '-':<6} {dtype:<12} {c['data_source']:<15} {enabled:<4} {last_sync}")
    print(f"\n共 {len(catalogs)} 个目录")


def sync_catalog(catalog_id: int, mode: str, start: str = None, end: str = None):
    """Sync a specific catalog."""
    from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine

    engine = SyncEngine(catalog_id=catalog_id, mode=mode)

    if mode == 'full' and start and end:
        start_date = datetime.strptime(start, '%Y-%m-%d').date()
        end_date = datetime.strptime(end, '%Y-%m-%d').date()
        engine._calculate_full_range = lambda: (start_date, end_date)

    print(f"开始同步: catalog_id={catalog_id}, mode={mode}")
    result = engine.execute()

    if result.success:
        print(f"  成功: {result.records_fetched} 条记录, "
              f"{result.batches_completed}/{result.total_batches} 批, "
              f"耗时 {result.duration_seconds:.1f}s")
    else:
        print(f"  失败: {result.error_message}")


def sync_all(mode: str, start: str = None, end: str = None):
    """Sync all enabled catalogs."""
    from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

    catalogs = CatalogManager.get_enabled_catalogs()
    if not catalogs:
        print("  (无启用的数据目录)")
        return

    print(f"开始同步 {len(catalogs)} 个启用的目录 (mode={mode})...\n")
    for c in catalogs:
        dtype = DATA_TYPE_LABELS.get(c['data_type'], c['data_type'])
        print(f"[{c['id']}] {c['catalog_name']} ({dtype})")
        sync_catalog(c['id'], mode, start, end)
        print()


def main():
    parser = argparse.ArgumentParser(description='数据目录同步工具')
    subparsers = parser.add_subparsers(dest='command')

    # list
    subparsers.add_parser('list', help='列出所有数据目录')

    # sync
    sync_parser = subparsers.add_parser('sync', help='同步指定数据目录')
    sync_parser.add_argument('--id', type=int, required=True, help='目录ID')
    sync_parser.add_argument('--mode', choices=['incremental', 'full'], default='incremental', help='同步模式')
    sync_parser.add_argument('--start', help='全量同步起始日期 (YYYY-MM-DD)')
    sync_parser.add_argument('--end', help='全量同步结束日期 (YYYY-MM-DD)')

    # sync-all
    sync_all_parser = subparsers.add_parser('sync-all', help='同步所有启用的数据目录')
    sync_all_parser.add_argument('--mode', choices=['incremental', 'full'], default='incremental', help='同步模式')
    sync_all_parser.add_argument('--start', help='全量同步起始日期 (YYYY-MM-DD)')
    sync_all_parser.add_argument('--end', help='全量同步结束日期 (YYYY-MM-DD)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == 'list':
        list_catalogs()
    elif args.command == 'sync':
        sync_catalog(args.id, args.mode, args.start, args.end)
    elif args.command == 'sync-all':
        sync_all(args.mode, args.start, args.end)


if __name__ == '__main__':
    main()
