"""
Structured audit logging for data sync operations.

Records each sync task's start/end time, success/failure, record count,
and errors to the sync_audit_log table in tzdata_market.db.
"""
import logging
import sqlite3
import time
from datetime import datetime
from typing import Optional

from tzdata_pkg.config import TZDATA_MARKET_DB

logger = logging.getLogger(__name__)


class AuditLogger:
    """Records sync operations to the audit log table."""

    def __init__(self):
        self._records: dict[str, dict] = {}

    def log_start(
        self,
        task_id: str,
        task_name: str,
        sync_mode: str = "calendar-driven",
        exchange: Optional[str] = None,
        product: Optional[str] = None,
        trade_date: Optional[str] = None,
    ):
        """Log the start of a sync task."""
        record = {
            "task_id": task_id,
            "task_name": task_name,
            "sync_mode": sync_mode,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "success": 0,
            "records_fetched": 0,
            "error_message": None,
            "exchange": exchange,
            "product": product,
            "trade_date": trade_date,
            "duration_seconds": None,
        }
        self._records[task_id] = record
        logger.info(f"Audit: {task_name} started (task_id={task_id})")

    def log_success(
        self,
        task_id: str,
        records_fetched: int = 0,
    ):
        """Log successful completion of a sync task."""
        record = self._records.get(task_id)
        if not record:
            logger.warning(f"Audit: no start record for task_id={task_id}")
            return
        end = datetime.now()
        start = datetime.fromisoformat(record["start_time"])
        record["end_time"] = end.isoformat()
        record["success"] = 1
        record["records_fetched"] = records_fetched
        record["duration_seconds"] = round((end - start).total_seconds(), 2)
        self._persist(record)

    def log_failure(
        self,
        task_id: str,
        error: Exception,
        records_fetched: int = 0,
    ):
        """Log failed completion of a sync task."""
        record = self._records.get(task_id)
        if not record:
            logger.warning(f"Audit: no start record for task_id={task_id}")
            return
        end = datetime.now()
        start = datetime.fromisoformat(record["start_time"])
        record["end_time"] = end.isoformat()
        record["success"] = 0
        record["error_message"] = str(error)
        record["records_fetched"] = records_fetched
        record["duration_seconds"] = round((end - start).total_seconds(), 2)
        self._persist(record)

    def _persist(self, record: dict):
        """Write audit record to SQLite."""
        try:
            conn = sqlite3.connect(str(TZDATA_MARKET_DB))
            conn.execute("""
                INSERT INTO sync_audit_log
                (task_id, task_name, sync_mode, start_time, end_time,
                 success, records_fetched, error_message, exchange, product,
                 trade_date, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record["task_id"],
                record["task_name"],
                record["sync_mode"],
                record["start_time"],
                record["end_time"],
                record["success"],
                record["records_fetched"],
                record["error_message"],
                record["exchange"],
                record["product"],
                record["trade_date"],
                record["duration_seconds"],
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Audit log persist failed: {e}")

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Get recent audit records."""
        try:
            conn = sqlite3.connect(str(TZDATA_MARKET_DB))
            rows = conn.execute("""
                SELECT id, task_id, task_name, sync_mode, start_time, end_time,
                       success, records_fetched, error_message, exchange, product,
                       trade_date, duration_seconds
                FROM sync_audit_log
                ORDER BY start_time DESC LIMIT ?
            """, (limit,)).fetchall()
            conn.close()
            return [
                {
                    "id": r[0], "task_id": r[1], "task_name": r[2],
                    "sync_mode": r[3], "start_time": r[4], "end_time": r[5],
                    "success": bool(r[6]), "records_fetched": r[7],
                    "error_message": r[8], "exchange": r[9], "product": r[10],
                    "trade_date": r[11], "duration_seconds": r[12],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Audit log query failed: {e}")
            return []


_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    return _audit_logger
