"""
CLI script for trade matching (open/close pairing).

Usage:
    python -m tzdata_pkg.cli.trade_match match          # 执行匹配
    python -m tzdata_pkg.cli.trade_match stats          # 查看匹配统计
    python -m tzdata_pkg.cli.trade_match verify         # 验证匹配完整性
"""
import sys
import argparse

from tzdata_pkg.config import TZDATA_TRADING_DB


def run_match():
    from tzdata_pkg.maintenance.statements.trade_matcher import TradeMatcher

    matcher = TradeMatcher()
    result = matcher.run()
    print(f"\n匹配完成:")
    print(f"  配对记录数: {result['matched_count']}")
    print(f"  绩效记录数: {result['performance_count']}")
    print(f"  净盈亏合计: {result['total_net_pnl']:,.2f}")
    print(f"  按品种:")
    for inst, cnt in sorted(result['by_instrument'].items()):
        print(f"    {inst}: {cnt} 笔")


def show_stats():
    import sqlite3
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    conn.text_factory = lambda x: x.decode('utf-8')

    trades = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    matched = conn.execute("SELECT COUNT(*) FROM matched_trades").fetchone()[0]
    perf = conn.execute("SELECT COUNT(*) FROM trade_performance").fetchone()[0]

    print(f"\n统计数据:")
    print(f"  原始成交: {trades} 笔")
    print(f"  已配对:   {matched} 笔")
    print(f"  绩效记录: {perf} 笔")

    row = conn.execute("SELECT SUM(money_pnl), SUM(commission), SUM(net_pnl) FROM matched_trades").fetchone()
    print(f"\n盈亏汇总:")
    print(f"  价差盈亏: {row[0]:,.2f}" if row[0] else "  价差盈亏: 0")
    print(f"  权利金盈亏: {row[1]:,.2f}" if row[1] else "  权利金盈亏: 0")
    print(f"  净盈亏: {row[2]:,.2f}" if row[2] else "  净盈亏: 0")

    print(f"\n按品种统计:")
    for row in conn.execute("""
        SELECT instrument, COUNT(*) as cnt, SUM(money_pnl) as pnl, SUM(commission) as comm, SUM(net_pnl) as net
        FROM matched_trades
        GROUP BY instrument
        ORDER BY cnt DESC
        LIMIT 20
    """):
        print(f"  {row[0]:<20} {row[1]:>5} 笔  盈亏={row[4]:>12,.2f}  手续费={row[3]:>10,.2f}")

    conn.close()


def verify():
    import sqlite3
    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    conn.text_factory = lambda x: x.decode('utf-8')

    matched = conn.execute("SELECT COUNT(*) FROM matched_trades").fetchone()[0]
    open_ids = set(r[0] for r in conn.execute("SELECT open_trade_id FROM matched_trades"))
    close_ids = set(r[0] for r in conn.execute("SELECT close_trade_id FROM matched_trades"))

    all_matched_ids = open_ids | close_ids
    total_trades = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    unmatched = total_trades - len(all_matched_ids)

    print(f"\n匹配验证:")
    print(f"  总成交笔数: {total_trades}")
    print(f"  已参与配对: {len(all_matched_ids)}")
    print(f"  未配对(在仓): {unmatched}")

    # Close trades can be used multiple times (close multiple opens), but total volume must match
    dup_close = conn.execute("SELECT close_trade_id, COUNT(*) FROM matched_trades GROUP BY close_trade_id HAVING COUNT(*) > 1").fetchall()
    if dup_close:
        print(f"\n  平仓被多次使用（部分平仓，属正常）: {len(dup_close)} 笔")
        # Verify total close volume matches original
        vol_mismatch_close = conn.execute("""
            SELECT m.close_trade_id, t.volume, SUM(m.close_volume) as matched_vol
            FROM matched_trades m
            JOIN trades t ON m.close_trade_id = t.id
            GROUP BY m.close_trade_id
            HAVING ABS(t.volume - matched_vol) > 0.01
        """).fetchall()
        if vol_mismatch_close:
            print(f"  错误: 发现平仓成交量不匹配!")
            for r in vol_mismatch_close[:5]:
                print(f"    close_trade_id={r[0]}, 原始vol={r[1]}, 已匹配vol={r[2]}")
        else:
            print(f"  平仓成交量: 正常")
    else:
        print(f"  平仓唯一性: 正常")

    # Open trades can be used multiple times (partial close), but total volume must match
    vol_mismatch = conn.execute("""
        SELECT m.open_trade_id, t.volume, SUM(m.open_volume) as matched_vol
        FROM matched_trades m
        JOIN trades t ON m.open_trade_id = t.id
        GROUP BY m.open_trade_id
        HAVING ABS(t.volume - matched_vol) > 0.01
    """).fetchall()
    if vol_mismatch:
        print(f"\n  错误: 发现开仓成交量不匹配!")
        for r in vol_mismatch[:10]:
            print(f"    open_trade_id={r[0]}, 原始vol={r[1]}, 已匹配vol={r[2]}")
    else:
        print(f"  开仓成交量: 正常")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="交易开平匹配")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("match", help="执行开平匹配")
    subparsers.add_parser("stats", help="查看匹配统计")
    subparsers.add_parser("verify", help="验证匹配完整性")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "match":
        run_match()
    elif args.command == "stats":
        show_stats()
    elif args.command == "verify":
        verify()


if __name__ == "__main__":
    main()
