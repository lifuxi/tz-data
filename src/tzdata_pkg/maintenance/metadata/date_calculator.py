"""
Date calculator for trade calendar operations.
Provides next/prev trading day, trading day count, and signed offset calculations.
"""
import sqlite3
from datetime import date, timedelta
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry


class DateCalculator:
    """Date calculation utilities for trade calendars."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: Optional explicit SQLite path for testing.
                     If None, uses the default DBRegistry.
        """
        if db_path:
            from tzdata_pkg.core.db import SQLitePool
            self._pool = SQLitePool(db_path)
        else:
            self._pool = DBRegistry().get_pool('market')

    def _has_calendar_data(self) -> bool:
        """Check if trade_calendar table has any data."""
        try:
            with self._pool.connection() as conn:
                row = conn.execute("SELECT COUNT(*) FROM trade_calendar").fetchone()
                return row[0] > 0
        except sqlite3.OperationalError:
            return False

    def _is_trading(self, d: date, exchange_code: str = 'ALL') -> bool:
        """Check if a date is a trading day (DB-based)."""
        # First check special date overrides (highest priority)
        override = self._get_special_override(d, exchange_code)
        if override is not None:
            return override['override_type'] in ('workday', 'half_day')

        date_str = d.isoformat()
        try:
            with self._pool.connection() as conn:
                row = conn.execute("""
                    SELECT is_holiday FROM trade_calendar
                    WHERE trade_date = ? AND exchange_code = ?
                    ORDER BY product_code LIMIT 1
                """, (date_str, exchange_code)).fetchone()
        except sqlite3.OperationalError:
            return d.weekday() < 5
        if row is None:
            return d.weekday() < 5
        return row[0] == 0

    def _get_special_override(self, d: date, exchange_code: str = 'ALL') -> Optional[dict]:
        """Check if a date has a special override (highest priority)."""
        date_str = d.isoformat()
        try:
            with self._pool.connection() as conn:
                # Exchange-specific override
                row = conn.execute("""
                    SELECT exchange_code, trade_date, override_type, reason
                    FROM special_date_override
                    WHERE exchange_code = ? AND trade_date = ?
                """, (exchange_code, date_str)).fetchone()

                if row is None and exchange_code != 'ALL':
                    # Fall back to 'ALL' override
                    row = conn.execute("""
                        SELECT exchange_code, trade_date, override_type, reason
                        FROM special_date_override
                        WHERE exchange_code = 'ALL' AND trade_date = ?
                    """, (date_str,)).fetchone()
        except sqlite3.OperationalError:
            return None

        if row is None:
            return None

        return {
            'exchange_code': row[0],
            'trade_date': row[1],
            'override_type': row[2],
            'reason': row[3],
        }

    def is_trading_day(self, trade_date: date, exchange_code: str = 'ALL') -> bool:
        """
        Check if a date is a trading day.

        Args:
            trade_date: Date to check
            exchange_code: Exchange scope (default 'ALL')

        Returns:
            True if trading day, False otherwise
        """
        if not self._has_calendar_data():
            raise ValueError("DateCalculator has no trade calendar data")
        return self._is_trading(trade_date, exchange_code)

    def get_next_trading_day(self, from_date: date, n: int = 1,
                             exchange_code: str = 'ALL') -> date:
        """
        Find the nth trading day after the given date.

        Args:
            from_date: Starting date
            n: Number of trading days forward (default 1)
            exchange_code: Exchange scope

        Returns:
            The nth trading day after from_date
        """
        if not self._has_calendar_data():
            raise ValueError("DateCalculator has no trade calendar data")
        if n < 0:
            return self.get_prev_trading_day(from_date, n=-n, exchange_code=exchange_code)

        current = from_date
        found = 0
        max_iterations = 365 * 3  # Safety limit: 3 years of days
        for _ in range(max_iterations):
            current += timedelta(days=1)
            if self._is_trading(current, exchange_code):
                found += 1
                if found == n:
                    return current
        raise ValueError(f"Could not find {n} trading days after {from_date}")

    def get_prev_trading_day(self, from_date: date, n: int = 1,
                             exchange_code: str = 'ALL') -> date:
        """
        Find the nth trading day before the given date.

        Args:
            from_date: Starting date
            n: Number of trading days backward (default 1)
            exchange_code: Exchange scope

        Returns:
            The nth trading day before from_date
        """
        if not self._has_calendar_data():
            raise ValueError("DateCalculator has no trade calendar data")
        if n < 0:
            return self.get_next_trading_day(from_date, n=-n, exchange_code=exchange_code)

        current = from_date
        found = 0
        max_iterations = 365 * 3
        for _ in range(max_iterations):
            current -= timedelta(days=1)
            if self._is_trading(current, exchange_code):
                found += 1
                if found == n:
                    return current
        raise ValueError(f"Could not find {n} trading days before {from_date}")

    def get_trading_days_count(self, start_date: date, end_date: date,
                               exchange_code: str = 'ALL') -> int:
        """
        Count trading days in a date range (inclusive).

        Uses DB to look up holiday dates and subtracts from total weekdays.
        Weekend dates stored as holidays in the DB are not double-counted.

        Args:
            start_date: Range start (inclusive)
            end_date: Range end (inclusive)
            exchange_code: Exchange scope

        Returns:
            Number of trading days, or 0 if start > end
        """
        if start_date > end_date:
            return 0
        if not self._has_calendar_data():
            return 0

        with self._pool.connection() as conn:
            # Get all holiday dates in range
            rows = conn.execute("""
                SELECT trade_date FROM trade_calendar
                WHERE trade_date BETWEEN ? AND ?
                  AND exchange_code = ?
                  AND is_holiday = 1
            """, (start_date.isoformat(), end_date.isoformat(), exchange_code)).fetchall()
            holiday_dates = {row[0] for row in rows}

        # Count weekdays that are NOT holidays
        count = 0
        current = start_date
        while current <= end_date:
            if current.weekday() < 5 and current.isoformat() not in holiday_dates:
                count += 1
            current += timedelta(days=1)

        return count

    def add_trading_days(self, from_date: date, n: int,
                         exchange_code: str = 'ALL') -> date:
        """
        Add (signed) trading day offset to a date.

        If the starting date is not a trading day, it first snaps to the nearest
        trading day, then applies the offset.

        Args:
            from_date: Starting date
            n: Signed offset (+forward, -backward, 0=nearest trading day)
            exchange_code: Exchange scope

        Returns:
            Resulting trading day
        """
        if n > 0:
            # If starting date is not a trading day, snap to next trading day first
            start = from_date if self._is_trading(from_date, exchange_code) else from_date
            return self.get_next_trading_day(start, n=n, exchange_code=exchange_code)
        elif n < 0:
            start = from_date if self._is_trading(from_date, exchange_code) else from_date
            return self.get_prev_trading_day(start, n=-n, exchange_code=exchange_code)
        else:
            # n == 0: find nearest trading day
            if self._is_trading(from_date, exchange_code):
                return from_date
            # Try next and previous, return whichever is closer
            try:
                nxt = self.get_next_trading_day(from_date, exchange_code=exchange_code)
            except ValueError:
                nxt = None
            try:
                prev = self.get_prev_trading_day(from_date, exchange_code=exchange_code)
            except ValueError:
                prev = None
            if nxt is None:
                return prev
            if prev is None:
                return nxt
            dist_next = (nxt - from_date).days
            dist_prev = (from_date - prev).days
            return prev if dist_prev <= dist_next else nxt

    def get_trading_days_list(self, start_date: date, end_date: date,
                              exchange_code: str = 'ALL') -> list[date]:
        """
        Get all trading days in a range (inclusive, sorted).

        Args:
            start_date: Range start
            end_date: Range end
            exchange_code: Exchange scope

        Returns:
            Sorted list of trading day dates
        """
        if start_date > end_date:
            return []
        if not self._has_calendar_data():
            return []

        with self._pool.connection() as conn:
            rows = conn.execute("""
                SELECT trade_date FROM trade_calendar
                WHERE trade_date BETWEEN ? AND ?
                  AND exchange_code = ?
                  AND is_holiday = 0
                ORDER BY trade_date
            """, (start_date.isoformat(), end_date.isoformat(), exchange_code)).fetchall()

        return [date.fromisoformat(row[0]) for row in rows]

    def get_last_trading_day_of_month(self, year: int, month: int,
                                      exchange_code: str = 'ALL') -> date:
        """
        Find the last trading day of a given month.

        Args:
            year: Year
            month: Month (1-12)
            exchange_code: Exchange scope

        Returns:
            Last trading day of the month
        """
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        end_date = date(year, month, last_day)
        # Walk backwards from the last calendar day
        for i in range(31):
            check = end_date - timedelta(days=i)
            if check.month != month:
                break
            if self._is_trading(check, exchange_code):
                return check
        raise ValueError(f"No trading day found in {year}-{month:02d}")

    def get_first_trading_day_of_month(self, year: int, month: int,
                                       exchange_code: str = 'ALL') -> date:
        """
        Find the first trading day of a given month.

        Args:
            year: Year
            month: Month (1-12)
            exchange_code: Exchange scope

        Returns:
            First trading day of the month
        """
        start_date = date(year, month, 1)
        for i in range(31):
            check = start_date + timedelta(days=i)
            if check.month != month:
                break
            if self._is_trading(check, exchange_code):
                return check
        raise ValueError(f"No trading day found in {year}-{month:02d}")

    def snap_to_trading_day(self, target_date: date, direction: str = 'forward',
                            exchange_code: str = 'ALL') -> date:
        """
        Snap a date to the nearest trading day.

        Args:
            target_date: Date to snap
            direction: 'forward', 'backward', or 'nearest'
            exchange_code: Exchange scope

        Returns:
            Nearest trading day
        """
        if self._is_trading(target_date, exchange_code):
            return target_date

        if direction == 'forward':
            return self.get_next_trading_day(target_date, exchange_code=exchange_code)
        elif direction == 'backward':
            return self.get_prev_trading_day(target_date, exchange_code=exchange_code)
        else:
            # nearest
            try:
                nxt = self.get_next_trading_day(target_date, exchange_code=exchange_code)
            except ValueError:
                nxt = None
            try:
                prev = self.get_prev_trading_day(target_date, exchange_code=exchange_code)
            except ValueError:
                prev = None
            if nxt is None:
                return prev
            if prev is None:
                return nxt
            return prev if (target_date - prev).days <= (nxt - target_date).days else nxt

    def get_trading_day_offset(self, from_date: date, to_date: date,
                               exchange_code: str = 'ALL') -> int:
        """
        Calculate the number of trading days between two dates.

        Positive if to_date > from_date, negative if to_date < from_date.

        Args:
            from_date: Start date
            to_date: End date
            exchange_code: Exchange scope

        Returns:
            Signed trading day offset
        """
        if from_date == to_date:
            return 0

        if from_date < to_date:
            return self.get_trading_days_count(from_date, to_date, exchange_code) - 1
        else:
            return -(self.get_trading_days_count(to_date, from_date, exchange_code) - 1)
