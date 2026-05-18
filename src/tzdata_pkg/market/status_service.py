"""Data source status tracking and management."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import structlog

logger = structlog.get_logger("tzdata_market")

DEFAULT_SOURCES = [
    {"source_name": "tushare", "source_type": "historical"},
    {"source_name": "akshare", "source_type": "transition"},
    {"source_name": "qq_finance", "source_type": "transition"},
    {"source_name": "ctp", "source_type": "realtime"},
    {"source_name": "itick", "source_type": "realtime"},
]


class StatusService:
    """Manage data source connection status in data_source_status table."""

    def __init__(self, db_pool):
        self._pool = db_pool
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Ensure all default sources exist in status table."""
        try:
            with self._pool.transaction() as conn:
                for src in DEFAULT_SOURCES:
                    conn.execute(
                        """INSERT OR IGNORE INTO data_source_status
                           (source_name, source_type, status, error_count, symbols_subscribed)
                           VALUES (?, ?, 'disconnected', 0, 0)""",
                        (src["source_name"], src["source_type"]),
                    )
        except Exception as e:
            logger.warning(f"StatusService init defaults failed: {e}")

    def update_status(
        self,
        source_name: str,
        status: str = "connected",
        latency_ms: int = 0,
        latency_p99_ms: int = 0,
        error_count: int = 0,
        symbols_subscribed: int = 0,
    ) -> None:
        """Update source status record."""
        now = datetime.utcnow().isoformat()
        try:
            with self._pool.transaction() as conn:
                conn.execute(
                    """INSERT INTO data_source_status
                       (source_name, status, last_heartbeat, latency_ms,
                        latency_p99_ms, error_count, symbols_subscribed)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(source_name) DO UPDATE SET
                           status=excluded.status,
                           last_heartbeat=excluded.last_heartbeat,
                           latency_ms=excluded.latency_ms,
                           latency_p99_ms=excluded.latency_p99_ms,
                           error_count=excluded.error_count,
                           symbols_subscribed=excluded.symbols_subscribed""",
                    (source_name, status, now, latency_ms,
                     latency_p99_ms, error_count, symbols_subscribed),
                )
        except Exception as e:
            logger.warning(f"StatusService update failed for {source_name}: {e}")

    def get_source(self, source_name: str) -> dict | None:
        """Get a single source status."""
        try:
            with self._pool.connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM data_source_status WHERE source_name = ?",
                    (source_name,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"StatusService get_source failed: {e}")
            return None

    def get_all_sources(self) -> list[dict]:
        """Get all source status records."""
        try:
            with self._pool.connection() as conn:
                cur = conn.execute("SELECT * FROM data_source_status ORDER BY source_name")
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"StatusService get_all_sources failed: {e}")
            return []

    def get_connected_sources(self) -> list[dict]:
        """Get only connected/active sources."""
        try:
            with self._pool.connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM data_source_status WHERE status IN ('connected', 'degraded') ORDER BY source_name",
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"StatusService get_connected_sources failed: {e}")
            return []
