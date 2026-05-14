"""
bill_fund_flows 回填脚本。

从已有的 bill_details 表中提取 deposit 和 transaction 记录，
转换为 bill_fund_flows 格式并插入。

Usage:
    python scripts/backfill_fund_flows.py              # 回填所有账单（需确认）
    python scripts/backfill_fund_flows.py --dry-run    # 仅预览，不执行
    python scripts/backfill_fund_flows.py --yes        # 跳过确认
    python scripts/backfill_fund_flows.py --bill-id 5  # 仅回填指定账单
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DB_PATH = "C:/myspace/tz-data/data/tzdata_trading.db"

# flow_type 映射
DEPOSIT_TYPE_MAP = {
    "入金": "deposit",
    "出金": "withdrawal",
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def count_existing_flows(conn: sqlite3.Connection) -> int:
    """统计现有 bill_fund_flows 记录数。"""
    try:
        return conn.execute("SELECT COUNT(*) FROM bill_fund_flows").fetchone()[0]
    except Exception:
        return 0


def get_bills(conn: sqlite3.Connection, bill_id: int = None) -> list:
    """获取需要回填的账单列表。"""
    if bill_id:
        return conn.execute(
            "SELECT id, account_id, bill_date_start FROM bills WHERE id = ? ORDER BY bill_date_start",
            (bill_id,)
        ).fetchall()
    return conn.execute(
        "SELECT id, account_id, bill_date_start FROM bills ORDER BY bill_date_start"
    ).fetchall()


def extract_flows_from_details(conn: sqlite3.Connection, bill_id: int) -> list:
    """从 bill_details 表提取资金流水记录。"""
    flows = []

    # 1. deposit 记录
    deposits = conn.execute(
        "SELECT data FROM bill_details WHERE bill_id = ? AND detail_type = 'deposit'",
        (bill_id,)
    ).fetchall()

    for (data_json,) in deposits:
        try:
            data = json.loads(data_json)
            date_str = data.get("date", "")
            deposit_amt = data.get("deposit", 0)
            withdrawal_amt = data.get("withdrawal", 0)
            note = data.get("note", "")

            if deposit_amt > 0:
                flows.append({
                    "bill_id": bill_id,
                    "trade_date": date_str[:10],
                    "flow_type": "deposit",
                    "amount": round(deposit_amt, 4),
                    "symbol": None,
                    "description": note or "入金",
                })
            if withdrawal_amt > 0:
                flows.append({
                    "bill_id": bill_id,
                    "trade_date": date_str[:10],
                    "flow_type": "withdrawal",
                    "amount": round(-withdrawal_amt, 4),
                    "symbol": None,
                    "description": note or "出金",
                })
        except Exception as e:
            print(f"  警告: 解析 deposit 失败: {e}")

    # 2. transaction 记录
    transactions = conn.execute(
        "SELECT data FROM bill_details WHERE bill_id = ? AND detail_type = 'transaction'",
        (bill_id,)
    ).fetchall()

    for (data_json,) in transactions:
        try:
            data = json.loads(data_json)
            date_str = data.get("date", "")[:10]
            instrument = data.get("instrument", "")
            fee = data.get("fee", 0)
            premium = data.get("premium", 0)
            realized_pl = data.get("realized_pl", 0)

            if fee != 0:
                flows.append({
                    "bill_id": bill_id,
                    "trade_date": date_str,
                    "flow_type": "commission",
                    "amount": round(-abs(fee), 4),
                    "symbol": instrument,
                    "description": f"手续费 - {instrument}",
                })
            if premium != 0:
                flow_type = "premium_income" if premium > 0 else "premium_expense"
                flows.append({
                    "bill_id": bill_id,
                    "trade_date": date_str,
                    "flow_type": flow_type,
                    "amount": round(premium, 4),
                    "symbol": instrument,
                    "description": f"权利金 - {instrument}",
                })
            if realized_pl != 0:
                flows.append({
                    "bill_id": bill_id,
                    "trade_date": date_str,
                    "flow_type": "realized_pnl",
                    "amount": round(realized_pl, 4),
                    "symbol": instrument,
                    "description": f"平仓盈亏 - {instrument}",
                })
        except Exception as e:
            print(f"  警告: 解析 transaction 失败: {e}")

    return flows


def main():
    parser = argparse.ArgumentParser(description="bill_fund_flows 回填脚本")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不执行")
    parser.add_argument("--yes", action="store_true", help="跳过确认")
    parser.add_argument("--bill-id", type=int, help="仅回填指定账单 ID")
    args = parser.parse_args()

    print("=" * 60)
    print("bill_fund_flows 回填脚本")
    print("=" * 60)

    if not Path(DB_PATH).exists():
        print(f"错误: 数据库不存在: {DB_PATH}")
        sys.exit(1)

    conn = get_conn()

    before = count_existing_flows(conn)
    print(f"现有 bill_fund_flows 记录: {before}")

    bills = get_bills(conn, args.bill_id)
    print(f"待处理账单数: {len(bills)}")

    if args.dry_run:
        print("\n[DRY RUN] 预览将执行的操作:")
        total_preview = 0
        for bill in bills:
            flows = extract_flows_from_details(conn, bill["id"])
            total_preview += len(flows)
            print(f"  bill {bill['id']} ({bill['bill_date_start']}): {len(flows)} 条流水")
        print(f"\n总计: {total_preview} 条流水将被插入")
        conn.close()
        return

    if not args.yes:
        print("\n确认执行 bill_fund_flows 回填？(y/n): ", end="")
        confirm = input()
        if confirm.lower() != "y":
            print("已取消。")
            conn.close()
            return

    start_time = time.time()
    total_inserted = 0
    total_skipped = 0

    for bill in bills:
        bill_id = bill["id"]
        flows = extract_flows_from_details(conn, bill_id)

        for f in flows:
            try:
                conn.execute(
                    """INSERT INTO bill_fund_flows
                       (bill_id, trade_date, flow_type, amount, symbol, description)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f["bill_id"], f["trade_date"], f["flow_type"],
                     f["amount"], f.get("symbol"), f.get("description"))
                )
                total_inserted += 1
            except sqlite3.IntegrityError:
                # 唯一约束冲突（如果有）
                total_skipped += 1

        conn.commit()
        print(f"  bill {bill_id} ({bill['bill_date_start']}): {len(flows)} 条流水")

    elapsed = time.time() - start_time
    after = count_existing_flows(conn)

    print("\n" + "=" * 60)
    print(f"回填完成:")
    print(f"  插入: {total_inserted} 条")
    print(f"  跳过: {total_skipped} 条")
    print(f"  回填前总计: {before}")
    print(f"  回填后总计: {after}")
    print(f"  耗时: {elapsed:.1f}s")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    main()
