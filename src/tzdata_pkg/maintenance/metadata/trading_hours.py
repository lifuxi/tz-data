"""
Trading hours management.
Manages trading session templates and checks if a given time is within trading hours.
Supports day sessions, night sessions, and pre-open/pre-close auctions.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _time_to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes from midnight."""
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])


def _is_in_range(minutes: int, start: str, end: str) -> bool:
    """
    Check if minutes falls within [start, end] range.
    Handles overnight ranges (e.g. 21:00-02:30).
    """
    start_min = _time_to_minutes(start)
    end_min = _time_to_minutes(end)

    if end_min < start_min:  # Overnight session (e.g. 21:00-02:30)
        return minutes >= start_min or minutes <= end_min
    return start_min <= minutes <= end_min


class TradingHoursManager:
    """Manage trading hours templates and session queries."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            from tzdata_pkg.core.db import SQLitePool
            self._pool = SQLitePool(db_path)
        else:
            from tzdata_pkg.storage.db_registry import DBRegistry
            self._pool = DBRegistry().get_pool('market')

    def create_template(
        self,
        template_id: str,
        template_name: str,
        exchange_code: str,
        product_type: str,
        normal_schedule: list[dict],
        night_schedule: Optional[list[dict]] = None,
        pre_open: Optional[dict] = None,
        pre_close: Optional[dict] = None,
        is_default: int = 0,
    ) -> None:
        """
        Create a trading hours template.

        Args:
            normal_schedule: List of {"start": "HH:MM", "end": "HH:MM"}
            night_schedule: Optional night session schedule
            pre_open: Optional pre-open auction time
            pre_close: Optional pre-close auction time
        """
        with self._pool.transaction() as conn:
            conn.execute("""
                INSERT INTO trading_hours_template
                    (template_id, template_name, exchange_code, product_type,
                     normal_schedule, night_schedule, pre_open, pre_close, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                template_id, template_name, exchange_code, product_type,
                json.dumps(normal_schedule, ensure_ascii=False),
                json.dumps(night_schedule, ensure_ascii=False) if night_schedule else None,
                json.dumps(pre_open, ensure_ascii=False) if pre_open else None,
                json.dumps(pre_close, ensure_ascii=False) if pre_close else None,
                is_default
            ))

    def get_template(self, template_id: str) -> Optional[dict]:
        """Get template by ID."""
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT id, template_id, template_name, exchange_code, product_type,"
                " normal_schedule, night_schedule, pre_open, pre_close, is_default, created_at"
                " FROM trading_hours_template WHERE template_id = ?",
                (template_id,)
            ).fetchone()

        if row is None:
            return None

        result = {
            'id': row[0],
            'template_id': row[1],
            'template_name': row[2],
            'exchange_code': row[3],
            'product_type': row[4],
            'normal_schedule': json.loads(row[5]) if row[5] else [],
            'night_schedule': json.loads(row[6]) if row[6] else None,
            'pre_open': json.loads(row[7]) if row[7] else None,
            'pre_close': json.loads(row[8]) if row[8] else None,
            'is_default': row[9],
            'created_at': row[10],
        }
        return result

    def get_sessions(self, template_id: str) -> list[dict]:
        """
        Get all trading sessions (day + night) for a template.

        Returns:
            List of {"start": "HH:MM", "end": "HH:MM", "type": "day/night"} dicts
        """
        tmpl = self.get_template(template_id)
        if tmpl is None:
            return []

        sessions = []
        for s in tmpl.get('normal_schedule', []):
            sessions.append({"start": s['start'], "end": s['end'], "type": "day"})
        for s in (tmpl.get('night_schedule') or []):
            sessions.append({"start": s['start'], "end": s['end'], "type": "night"})

        return sessions

    def is_trading_time(self, template_id: str, time_str: str) -> bool:
        """
        Check if a specific time (HH:MM) is within trading hours.

        Args:
            template_id: Template ID
            time_str: Time in "HH:MM" format

        Returns:
            True if within trading hours
        """
        sessions = self.get_sessions(template_id)
        if not sessions:
            return False

        minutes = _time_to_minutes(time_str)

        for s in sessions:
            if _is_in_range(minutes, s['start'], s['end']):
                return True

        return False
