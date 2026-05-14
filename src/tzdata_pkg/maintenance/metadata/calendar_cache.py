"""
Calendar cache: in-memory trading day cache for fast lookups.
Preloads trading days from DB into a dict for O(1) lookup.
"""
import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


class CalendarCache:
    """Singleton in-memory cache for trading day data."""

    _instance: Optional['CalendarCache'] = None

    @classmethod
    def get_instance(cls) -> 'CalendarCache':
        """Get or create the singleton cache instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            from tzdata_pkg.core.db import SQLitePool
            self._pool = SQLitePool(db_path)
        else:
            from tzdata_pkg.storage.db_registry import DBRegistry
            self._pool = DBRegistry().get_pool('market')

        # Set of trading days as date objects (exchange_code -> set of dates)
        self._trading_days: dict[str, set[date]] = {}
        # Sorted list of all trading days for range queries
        self._trading_days_sorted: list[date] = []
        self._loaded = False

    def preload(self, years: list[int] | None = None, exchange_code: str = 'ALL') -> None:
        """
        Preload trading days into memory.

        Args:
            years: List of years to preload (e.g. [2025, 2026, 2027])
                   If None, loads all available data.
            exchange_code: Exchange code to preload
        """
        with self._pool.connection() as conn:
            if years:
                placeholders = ','.join('?' for _ in years)
                year_conditions = ','.join(f'"{y}%"' for y in years)
                query = f"""
                    SELECT trade_date FROM trade_calendar
                    WHERE exchange_code = ?
                      AND (trade_date LIKE {','.join('?' for _ in years)})
                      AND is_holiday = 0
                    ORDER BY trade_date
                """
                params = [exchange_code] + [f"{y}" for y in years]
                # Rebuild query with LIKE patterns
                like_parts = [f"trade_date LIKE '{y}%'" for y in years]
                query = f"""
                    SELECT trade_date FROM trade_calendar
                    WHERE exchange_code = ?
                      AND ({' OR '.join(like_parts)})
                      AND is_holiday = 0
                    ORDER BY trade_date
                """
                params = [exchange_code]
                rows = conn.execute(query, params).fetchall()
            else:
                rows = conn.execute("""
                    SELECT trade_date FROM trade_calendar
                    WHERE exchange_code = ? AND is_holiday = 0
                    ORDER BY trade_date
                """, (exchange_code,)).fetchall()

        self._trading_days[exchange_code] = {
            date.fromisoformat(row[0]) for row in rows
        }
        self._trading_days_sorted = sorted(self._trading_days[exchange_code])
        self._loaded = True

        logger.info(f"CalendarCache preloaded {len(self._trading_days_sorted)} trading days for {exchange_code}")

    def is_trading_day(self, d: date, exchange_code: str = 'ALL') -> bool:
        """
        Check if a date is a trading day (cache-first, DB fallback).

        Args:
            d: Date to check
            exchange_code: Exchange code

        Returns:
            True if trading day
        """
        # Try cache first
        if self._loaded and exchange_code in self._trading_days:
            return d in self._trading_days[exchange_code]

        # Fallback to DB
        date_str = d.isoformat()
        with self._pool.connection() as conn:
            row = conn.execute("""
                SELECT is_holiday FROM trade_calendar
                WHERE trade_date = ? AND exchange_code = ?
                LIMIT 1
            """, (date_str, exchange_code)).fetchone()

        if row is None:
            return d.weekday() < 5
        return row[0] == 0

    def get_trading_days(self, start: date, end: date, exchange_code: str = 'ALL') -> list[date]:
        """
        Get trading days in a range (cache-first, DB fallback).

        Args:
            start: Range start (inclusive)
            end: Range end (inclusive)
            exchange_code: Exchange code

        Returns:
            Sorted list of trading days
        """
        if self._loaded and exchange_code in self._trading_days:
            # Use binary search on sorted list
            from bisect import bisect_left, bisect_right
            idx_start = bisect_left(self._trading_days_sorted, start)
            idx_end = bisect_right(self._trading_days_sorted, end)
            return self._trading_days_sorted[idx_start:idx_end]

        # Fallback to DB
        with self._pool.connection() as conn:
            rows = conn.execute("""
                SELECT trade_date FROM trade_calendar
                WHERE exchange_code = ? AND is_holiday = 0
                  AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date
            """, (exchange_code, start.isoformat(), end.isoformat())).fetchall()

        return [date.fromisoformat(row[0]) for row in rows]

    def status(self) -> dict:
        """Get cache status."""
        return {
            'loaded': self._loaded,
            'total_days': len(self._trading_days_sorted),
            'exchanges': list(self._trading_days.keys()),
        }

    def clear(self) -> None:
        """Clear all cached data."""
        self._trading_days.clear()
        self._trading_days_sorted.clear()
        self._loaded = False
