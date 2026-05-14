"""TDD tests for CalendarCache (in-memory trading day cache)."""

import sqlite3
import tempfile
import time
from datetime import date
from pathlib import Path

import pytest


class TestCalendarCache:
    """Tests for CalendarCache preloading and lookup."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create a SQLite DB with trade_calendar data for 2026."""
        self.db_path = _create_cached_db()
        self.conn = sqlite3.connect(str(self.db_path))

    def teardown_method(self):
        if self.conn:
            self.conn.close()
        if self.db_path and self.db_path.exists():
            try:
                time.sleep(0.1)
                self.db_path.unlink()
            except PermissionError:
                pass

    def _seed_january_2026(self):
        """Seed January 2026 calendar data."""
        # Weekdays (Mon-Fri) that are trading days, plus some holidays
        trading_days = [
            '2026-01-02', '2026-01-05', '2026-01-06', '2026-01-07',
            '2026-01-08', '2026-01-09', '2026-01-12', '2026-01-13',
            '2026-01-14', '2026-01-15', '2026-01-16', '2026-01-19',
            '2026-01-20', '2026-01-21', '2026-01-22', '2026-01-23',
            '2026-01-26', '2026-01-27', '2026-01-28', '2026-01-29',
            '2026-01-30',
        ]
        holidays = [
            '2026-01-01',  # New Year
            '2026-01-03', '2026-01-04',  # Weekend
            '2026-01-10', '2026-01-11',  # Weekend
            '2026-01-17', '2026-01-18',  # Weekend
            '2026-01-24', '2026-01-25',  # Weekend
            '2026-01-31',  # Weekend
        ]

        for d in trading_days:
            self.conn.execute(
                "INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday) VALUES (?, 'ALL', '', 0)",
                (d,)
            )
        for d in holidays:
            self.conn.execute(
                "INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday) VALUES (?, 'ALL', '', 1)",
                (d,)
            )
        self.conn.commit()

    def test_preload_loads_data(self):
        """Cache preloads trading days from DB."""
        self._seed_january_2026()

        from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
        cache = CalendarCache(db_path=str(self.db_path))
        cache.preload(years=[2026])

        assert cache._loaded

    def test_cache_is_trading_day(self):
        """Cached is_trading_day returns correct result."""
        self._seed_january_2026()

        from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
        cache = CalendarCache(db_path=str(self.db_path))
        cache.preload(years=[2026])

        assert cache.is_trading_day(date(2026, 1, 2)) is True   # Friday
        assert cache.is_trading_day(date(2026, 1, 1)) is False  # Holiday
        assert cache.is_trading_day(date(2026, 1, 3)) is False  # Saturday

    def test_cache_miss_falls_back_to_db(self):
        """Date not in cache range falls back to DB check."""
        self._seed_january_2026()

        from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
        cache = CalendarCache(db_path=str(self.db_path))
        # Don't preload — should fall back to DB
        assert cache.is_trading_day(date(2026, 1, 2)) is True

    def test_cache_get_trading_days_range(self):
        """get_trading_days returns list of trading days in range."""
        self._seed_january_2026()

        from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
        cache = CalendarCache(db_path=str(self.db_path))
        cache.preload(years=[2026])

        days = cache.get_trading_days(start=date(2026, 1, 1), end=date(2026, 1, 9))
        # Trading days in Jan 1-9: 2, 5, 6, 7, 8, 9 = 6 days
        assert len(days) == 6
        assert days[0] == date(2026, 1, 2)
        assert days[-1] == date(2026, 1, 9)

    def test_cache_status(self):
        """Cache status returns dict with loaded status."""
        from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
        cache = CalendarCache(db_path=str(self.db_path))

        status = cache.status()
        assert status['loaded'] is False

        self._seed_january_2026()
        cache.preload(years=[2026])
        status = cache.status()
        assert status['loaded'] is True
        assert status['total_days'] > 0

    def test_cache_is_singleton(self):
        """CalendarCache.get_instance returns the same instance."""
        from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
        c1 = CalendarCache.get_instance()
        c2 = CalendarCache.get_instance()
        assert c1 is c2


def _create_cached_db() -> Path:
    """Create a SQLite DB with trade_calendar table."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                exchange_code TEXT NOT NULL DEFAULT 'ALL',
                product_code TEXT NOT NULL DEFAULT '',
                is_holiday INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_date, exchange_code, product_code)
            )
        """)
        conn.commit()
    finally:
        conn.close()

    return db_path
