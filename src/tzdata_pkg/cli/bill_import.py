"""Batch bill import CLI: scan, parse, and store all bill files."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from tzdata_pkg.parser.bill_parser import BillParser
from tzdata_pkg.parser.models import BillSummary, TransactionRecord, PositionRecord
from tzdata_pkg.config import get_data_dir

import logging
logger = logging.getLogger(__name__)

# Direction mapping: Chinese -> English
DIRECTION_MAP = {"买": "buy", "卖": "sell", "买入": "buy", "卖出": "sell"}

# Offset flag mapping: Chinese -> English
OFFSET_MAP = {"开": "open", "平": "close", "开仓": "open", "平仓": "close"}


class BillImportService:
    """Import bill files into both tzdata_trading.db and bills.db."""

    def __init__(self, trading_db_path: str, bills_db_path: str):
        self.trading_db_path = trading_db_path
        self.bills_db_path = bills_db_path
        self.parser = BillParser()

    def import_all(self, bill_dir: str, dry_run: bool = False) -> dict:
        """Import all bill files from directory.

        Returns dict with import statistics.
        """
        stats = {
            "total_files": 0,
            "success": 0,
            "failed": 0,
            "errors": [],
            "bills_imported": 0,
            "transactions_imported": 0,
            "positions_imported": 0,
            "files": [],
        }

        bill_path = Path(bill_dir)
        if not bill_path.exists():
            stats["errors"].append(f"Directory not found: {bill_dir}")
            return stats

        txt_files = sorted(bill_path.rglob("*.txt"))
        stats["total_files"] = len(txt_files)

        if not txt_files:
            stats["errors"].append("No .txt files found")
            return stats

        for f in txt_files:
            try:
                self._import_file(f, stats, dry_run)
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{f.name}: {e}")

        return stats

    def _import_file(self, file_path: Path, stats: dict, dry_run: bool) -> None:
        """Parse and store a single bill file."""
        result = self.parser.parse_file(file_path)
        summary = result.summary

        if not summary:
            stats["failed"] += 1
            stats["errors"].append(f"{file_path.name}: no summary parsed")
            return

        if dry_run:
            stats["success"] += 1
            stats["files"].append({
                "file": file_path.name,
                "summary": _summary_to_dict(summary),
                "transactions": len(result.transactions),
                "positions": len(result.positions),
            })
            return

        # Store to both databases
        bill_id = self._store_bill(self.trading_db_path, file_path, summary)
        self._store_bill(self.bills_db_path, file_path, summary)

        # Store fund flows (bill_fund_flows table) — only to trading db
        flow_count = self._store_fund_flows(self.trading_db_path, bill_id, result)

        # Store transactions
        txn_count = 0
        for txn in result.transactions:
            self._store_transaction(self.trading_db_path, bill_id, summary.account_id, txn)
            self._store_transaction(self.bills_db_path, bill_id, summary.account_id, txn)
            txn_count += 1

        # Store positions
        pos_count = 0
        for pos in result.positions:
            self._store_position(self.trading_db_path, summary, pos)
            self._store_position(self.bills_db_path, summary, pos)
            pos_count += 1

        # Run post-processing: snapshot + reconciliation
        try:
            self._run_post_processing(bill_id, summary)
        except Exception as e:
            logger.warning(f"Post-processing failed for bill {bill_id}: {e}")

        stats["success"] += 1
        stats["bills_imported"] += 1
        stats["transactions_imported"] += txn_count
        stats["positions_imported"] += pos_count
        stats["files"].append({
            "file": file_path.name,
            "bill_id": bill_id,
            "transactions": txn_count,
            "positions": pos_count,
        })

        # Publish Redis event for tz2.0 post-processing
        try:
            self._publish_bill_imported(bill_id, summary)
        except Exception as e:
            logger.warning(f"Failed to publish bill.imported event: {e}")

    def _store_bill(self, db_path: str, file_path: Path, summary: BillSummary) -> int:
        """Insert bill summary and return the new bill ID."""
        conn = sqlite3.connect(db_path)
        # Check which schema version we have
        cols = conn.execute("PRAGMA table_info(bills)").fetchall()
        col_names = [c[1] for c in cols]

        if "bill_date_start" in col_names:
            # tzdata_trading.db schema
            cursor = conn.execute(
                """INSERT INTO bills (account_id, bill_date_start, bill_date_end,
                   client_id, client_name, currency, file_path, status,
                   balance_bf, balance_cf, deposit_withdrawal, realized_pl,
                   mtm_pl, exercise_pl, commission, premium_received, premium_paid,
                   client_equity, fund_available, margin_occupied)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    summary.account_id,
                    summary.bill_date_start.isoformat(),
                    summary.bill_date_end.isoformat(),
                    summary.client_id,
                    summary.client_name,
                    summary.currency,
                    str(file_path),
                    "parsed",
                    summary.balance_bf,
                    summary.balance_cf,
                    summary.deposit_withdrawal,
                    summary.realized_pl,
                    summary.mtm_pl,
                    summary.exercise_pl,
                    summary.commission,
                    summary.premium_received,
                    summary.premium_paid,
                    summary.client_equity,
                    summary.fund_available,
                    summary.margin_occupied,
                )
            )
        else:
            # bills.db schema (single bill_date column)
            cursor = conn.execute(
                """INSERT INTO bills (bill_date, file_path, parse_status,
                   client_id, client_name, account_id, currency,
                   balance_bf, balance_cf, deposit_withdrawal, realized_pl,
                   mtm_pl, commission, client_equity, fund_available, margin_occupied,
                   created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    summary.bill_date_end.isoformat(),
                    str(file_path),
                    "success",
                    summary.client_id,
                    summary.client_name,
                    summary.account_id,
                    summary.currency,
                    summary.balance_bf,
                    summary.balance_cf,
                    summary.deposit_withdrawal,
                    summary.realized_pl,
                    summary.mtm_pl,
                    summary.commission,
                    summary.client_equity,
                    summary.fund_available,
                    summary.margin_occupied,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                )
            )
        bill_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return bill_id

    def _store_transaction(self, db_path: str, bill_id: int, account_id: str, txn: TransactionRecord) -> None:
        """Insert a transaction as a flattened trade record."""
        conn = sqlite3.connect(db_path)

        # Check if new columns exist
        trade_cols = [c[1] for c in conn.execute("PRAGMA table_info(trades)").fetchall()]
        has_trade_time = 'trade_time' in trade_cols
        has_order_type = 'order_type' in trade_cols
        has_strategy_tag = 'strategy_tag' in trade_cols

        if has_trade_time and has_order_type and has_strategy_tag:
            conn.execute(
                """INSERT INTO trades (
                   account_id, year, month, trade_date, exchange, product,
                   instrument, direction, offset_flag, volume, price, turnover,
                   commission, total_pnl, premium, trade_id, position_type,
                   trade_time, order_type, strategy_tag)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account_id,
                    txn.date.year,
                    txn.date.month,
                    txn.date.strftime("%Y%m%d"),
                    txn.exchange,
                    txn.product,
                    txn.instrument,
                    DIRECTION_MAP.get(txn.direction, txn.direction),
                    OFFSET_MAP.get(txn.open_close, txn.open_close),
                    txn.lots,
                    txn.price,
                    txn.turnover,
                    txn.fee,
                    txn.realized_pl,
                    txn.premium,
                    txn.trans_no,
                    "option" if txn.instrument_type == "option" else "future",
                    txn.trade_time,
                    txn.order_type,
                    None,  # strategy_tag — set by user tagging or auto-inference later
                )
            )
        else:
            conn.execute(
                """INSERT INTO trades (
                   account_id, year, month, trade_date, exchange, product,
                   instrument, direction, offset_flag, volume, price, turnover,
                   commission, total_pnl, premium, trade_id, position_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account_id,
                    txn.date.year,
                    txn.date.month,
                    txn.date.strftime("%Y%m%d"),
                    txn.exchange,
                    txn.product,
                    txn.instrument,
                    DIRECTION_MAP.get(txn.direction, txn.direction),
                    OFFSET_MAP.get(txn.open_close, txn.open_close),
                    txn.lots,
                    txn.price,
                    txn.turnover,
                    txn.fee,
                    txn.realized_pl,
                    txn.premium,
                    txn.trans_no,
                    "option" if txn.instrument_type == "option" else "future",
                )
            )
        conn.commit()
        conn.close()

    def _store_position(self, db_path: str, summary: BillSummary, pos: PositionRecord) -> None:
        """Insert a position record into positions_summary."""
        conn = sqlite3.connect(db_path)
        cols = conn.execute("PRAGMA table_info(positions_summary)").fetchall()
        col_names = [c[1] for c in cols]

        pos_date = pos.date or summary.bill_date_end
        long_pos = pos.positions if pos.direction in ("买", "buy") else 0
        short_pos = pos.positions if pos.direction in ("卖", "sell") else 0

        if "float_pl" in col_names:
            # tzdata_trading.db schema
            conn.execute(
                """INSERT INTO positions_summary (
                   trade_date, year, month, account_id, instrument, exchange, product,
                   long_position, short_position, prev_settlement, settlement_price,
                   margin_occupied, float_pl)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pos_date.strftime("%Y%m%d"),
                    pos_date.year,
                    pos_date.month,
                    pos.account_id or summary.account_id,
                    pos.instrument,
                    pos.exchange,
                    pos.product,
                    long_pos,
                    short_pos,
                    pos.prev_settle,
                    pos.curr_settle,
                    pos.margin,
                    pos.float_pl,
                )
            )
        else:
            # bills.db schema (has avg_buy_price, avg_sell_price, market_value_*, accumulated_pnl)
            conn.execute(
                """INSERT INTO positions_summary (
                   trade_date, year, month, account_id, instrument, exchange, product,
                   long_position, short_position, prev_settlement, settlement_price,
                   margin_occupied, accumulated_pnl, market_value_long, market_value_short)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pos_date.strftime("%Y%m%d"),
                    pos_date.year,
                    pos_date.month,
                    pos.account_id or summary.account_id,
                    pos.instrument,
                    pos.exchange,
                    pos.product,
                    long_pos,
                    short_pos,
                    pos.prev_settle,
                    pos.curr_settle,
                    pos.margin,
                    pos.mtm_pl,
                    long_pos * pos.curr_settle * 10 if pos.instrument_type == "future" else 0,
                    short_pos * pos.curr_settle * 10 if pos.instrument_type == "future" else 0,
                )
            )
        conn.commit()
        conn.close()

    def _store_fund_flows(self, db_path: str, bill_id: int, result) -> int:
        """将解析结果中的资金变动写入 bill_fund_flows 表。

        Args:
            db_path: 数据库路径
            bill_id: 账单 ID
            result: BillParseResult

        Returns:
            插入的记录数
        """
        flows = BillParser.extract_fund_flows(result, bill_id)
        if not flows:
            return 0

        conn = sqlite3.connect(db_path)
        count = 0
        for f in flows:
            conn.execute(
                """INSERT INTO bill_fund_flows
                   (bill_id, trade_date, flow_type, amount, symbol, description)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    f['bill_id'],
                    f['trade_date'],
                    f['flow_type'],
                    round(f['amount'], 4),
                    f.get('symbol'),
                    f.get('description'),
                )
            )
            count += 1
        conn.commit()
        conn.close()
        logger.debug(f"Stored {count} fund flows for bill {bill_id}")
        return count

    def _run_post_processing(self, bill_id: int, summary: BillSummary) -> None:
        """运行账单后处理：资金流水分类 + 日终快照 + 余额勾稽校验。

        调用 tz2.0 的 BillStorage.post_process_bill 方法（如果可用）。
        """
        try:
            from src.data.bill_storage import BillStorage
            from src.infrastructure.db.database import get_sync_db_session

            with get_sync_db_session() as session:
                storage = BillStorage(session)
                result = storage.post_process_bill(bill_id)
                classified = result.get("classified_count", 0)
                snapshots = result.get("snapshots_generated", 0)
                logger.info(
                    f"Post-processed bill {bill_id}: "
                    f"{classified} classified flows, {snapshots} snapshots"
                )
        except ImportError:
            logger.debug("BillStorage not available, skipping post-processing")
        except Exception as e:
            logger.warning(f"Post-processing for bill {bill_id} failed: {e}")

    def _publish_bill_imported(self, bill_id: int, summary: BillSummary) -> None:
        """Publish Redis pub/sub event to notify tz2.0 for post-processing."""
        import os
        try:
            import redis
        except ImportError:
            return

        redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        r.publish("bill.imported", json.dumps({
            "bill_id": bill_id,
            "client_id": summary.client_id,
            "bill_date": summary.bill_date_end.isoformat(),
        }))
        logger.info(f"Published bill.imported event: bill_id={bill_id}")


def _summary_to_dict(s: BillSummary) -> dict:
    return {
        "client_id": s.client_id,
        "account_id": s.account_id,
        "bill_date_start": str(s.bill_date_start),
        "bill_date_end": str(s.bill_date_end),
        "balance_bf": s.balance_bf,
        "balance_cf": s.balance_cf,
        "client_equity": s.client_equity,
        "commission": s.commission,
        "realized_pl": s.realized_pl,
        "mtm_pl": s.mtm_pl,
    }
