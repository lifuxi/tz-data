"""
Special date override manager.
Handles manual overrides for the trade calendar (e.g. unexpected holidays,
make-up trading days). Overrides take precedence over auto-generated calendar data.
"""
import sqlite3
from datetime import date
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry


class SpecialDateManager:
    """CRUD operations for special_date_override table."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            from tzdata_pkg.core.db import SQLitePool
            self._pool = SQLitePool(db_path)
        else:
            self._pool = DBRegistry().get_pool('market')

    def create(
        self,
        exchange_code: str,
        trade_date: date,
        override_type: str,
        reason: str = '',
        operator: str = 'system',
    ) -> None:
        """
        Insert or update a special date override (upsert).

        Args:
            exchange_code: Exchange code (e.g. 'CFFEX', 'ALL')
            trade_date: Date to override
            override_type: 'holiday', 'workday', or 'half_day'
            reason: Description of the override
            operator: Who made the change
        """
        with self._pool.transaction() as conn:
            conn.execute("""
                INSERT INTO special_date_override
                    (exchange_code, trade_date, override_type, reason, operator)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(exchange_code, trade_date)
                DO UPDATE SET
                    override_type = excluded.override_type,
                    reason = excluded.reason,
                    operator = excluded.operator,
                    created_at = CURRENT_TIMESTAMP
            """, (exchange_code, trade_date.isoformat(), override_type, reason, operator))

    def list(
        self,
        exchange_code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """
        List special date overrides with optional filters.

        Args:
            exchange_code: Filter by exchange
            start_date: Filter from date (inclusive)
            end_date: Filter to date (inclusive)

        Returns:
            List of override records as dicts
        """
        query = "SELECT exchange_code, trade_date, override_type, reason, operator, created_at FROM special_date_override WHERE 1=1"
        params: list = []

        if exchange_code:
            query += " AND exchange_code = ?"
            params.append(exchange_code)
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY trade_date"

        with self._pool.connection() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                'exchange_code': row[0],
                'trade_date': row[1],
                'override_type': row[2],
                'reason': row[3],
                'operator': row[4],
                'created_at': row[5],
            }
            for row in rows
        ]

    def delete(self, exchange_code: str, trade_date: date) -> None:
        """
        Remove a special date override.

        Args:
            exchange_code: Exchange code
            trade_date: Date to remove override for
        """
        with self._pool.transaction() as conn:
            conn.execute(
                "DELETE FROM special_date_override WHERE exchange_code = ? AND trade_date = ?",
                (exchange_code, trade_date.isoformat())
            )

    def get_override(self, trade_date: date, exchange_code: str = 'ALL') -> Optional[dict]:
        """
        Check if a specific date has a special override.

        Args:
            trade_date: Date to check
            exchange_code: Exchange code (falls back to 'ALL' if no specific override)

        Returns:
            Override dict if found, None otherwise
        """
        date_str = trade_date.isoformat()
        with self._pool.connection() as conn:
            # First check exchange-specific override
            row = conn.execute("""
                SELECT exchange_code, trade_date, override_type, reason, operator
                FROM special_date_override
                WHERE exchange_code = ? AND trade_date = ?
            """, (exchange_code, date_str)).fetchone()

            if row is None and exchange_code != 'ALL':
                # Fall back to 'ALL' override
                row = conn.execute("""
                    SELECT exchange_code, trade_date, override_type, reason, operator
                    FROM special_date_override
                    WHERE exchange_code = 'ALL' AND trade_date = ?
                """, (date_str,)).fetchone()

        if row is None:
            return None

        return {
            'exchange_code': row[0],
            'trade_date': row[1],
            'override_type': row[2],
            'reason': row[3],
            'operator': row[4],
        }
