"""Structured event logger for market data lifecycle events."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import structlog

logger = structlog.get_logger("tzdata_market")

VALID_EVENT_TYPES = {
    "connect", "disconnect", "reconnect", "switch",
    "backfill", "gap", "snapshot", "error", "degrade", "recover",
}
VALID_SEVERITIES = {"info", "warning", "error", "critical"}


class MarketEventLogger:
    """Write market data events to market_data_event_log table.

    Events older than 90 days are auto-cleaned by the catalog_auto_expire Celery task.
    """

    def __init__(self, db_pool):
        self._pool = db_pool

    def log(
        self,
        event_type: str,
        source_name: str = "",
        symbol: str = "",
        severity: str = "info",
        message: str = "",
        details: dict | None = None,
    ) -> None:
        """Log a market data event."""
        if event_type not in VALID_EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}")
        if severity not in VALID_SEVERITIES:
            severity = "info"

        details_json = json.dumps(details, ensure_ascii=False) if details else ""
        now = datetime.utcnow().isoformat()

        try:
            with self._pool.transaction() as conn:
                conn.execute(
                    """INSERT INTO market_data_event_log
                       (event_type, source_name, symbol, severity, message, details, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (event_type, source_name, symbol, severity, message, details_json, now),
                )
        except Exception as e:
            logger.warning(f"Failed to write event log: {e}")

    def query(
        self,
        page: int = 1,
        page_size: int = 50,
        severity: str | None = None,
        source_name: str | None = None,
        event_type: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> tuple[list[dict], int]:
        """Query event log with pagination and filters.

        Returns (rows, total_count).
        """
        conditions = []
        params = []

        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if source_name:
            conditions.append("source_name = ?")
            params.append(source_name)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if start_time:
            conditions.append("created_at >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("created_at <= ?")
            params.append(end_time)

        where = " AND ".join(conditions) if conditions else "1=1"

        try:
            with self._pool.connection() as conn:
                # Total count
                cur = conn.execute(f"SELECT COUNT(*) FROM market_data_event_log WHERE {where}", params)
                total = cur.fetchone()[0]

                # Page data
                offset = (page - 1) * page_size
                cur = conn.execute(
                    f"""SELECT id, event_type, source_name, symbol, severity,
                               message, details, created_at
                        FROM market_data_event_log
                        WHERE {where}
                        ORDER BY created_at DESC
                        LIMIT ? OFFSET ?""",
                    params + [page_size, offset],
                )
                rows = [dict(r) for r in cur.fetchall()]
                return rows, total
        except Exception as e:
            logger.warning(f"Event log query failed: {e}")
            return [], 0
