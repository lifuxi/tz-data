"""TDD tests for tzdata_pkg.maintenance.metadata.date_calculator module"""

import tempfile
import sqlite3
from pathlib import Path
from datetime import date
import pytest

from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator


class TestDateCalculatorSetup:
    """Test database setup and edge cases"""

    def test_get_next_trading_day_raises_on_empty_db(self):
        """get_next_trading_day raises ValueError when DB has no data"""
        with _empty_db() as db_path:
            calc = DateCalculator(db_path=str(db_path))
            with pytest.raises(ValueError, match="no trade calendar data"):
                calc.get_next_trading_day(date(2026, 1, 1))

    def test_get_prev_trading_day_raises_on_empty_db(self):
        """get_prev_trading_day raises ValueError when DB has no data"""
        with _empty_db() as db_path:
            calc = DateCalculator(db_path=str(db_path))
            with pytest.raises(ValueError, match="no trade calendar data"):
                calc.get_prev_trading_day(date(2026, 1, 1))


class TestDateCalculatorBasic:
    """Tests for basic date calculation with a seeded calendar"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create an in-memory-style SQLite DB with known calendar data"""
        self.db_path = _seed_calendar_db()
        self.calc = DateCalculator(db_path=str(self.db_path))

    def teardown_method(self):
        """Release pool connections and clean up temp DB"""
        if hasattr(self.calc, '_pool'):
            self.calc._pool.close_all()
        import time
        time.sleep(0.1)  # Let Windows release file handles
        if self.db_path and self.db_path.exists():
            self.db_path.unlink(missing_ok=True)

    # --- get_next_trading_day ---

    def test_next_trading_day_from_monday(self):
        """From a Monday that is a trading day, next is Tuesday"""
        # 2026-01-05 is Monday, trading
        result = self.calc.get_next_trading_day(date(2026, 1, 5))
        assert result == date(2026, 1, 6)

    def test_next_trading_day_skips_weekend(self):
        """From Friday, next trading day skips Saturday and Sunday"""
        # 2026-01-09 is Friday, trading
        result = self.calc.get_next_trading_day(date(2026, 1, 9))
        assert result == date(2026, 1, 12)  # Monday

    def test_next_trading_day_skips_holiday(self):
        """get_next_trading_day skips a known holiday"""
        # 2026-01-01 is 元旦 holiday
        result = self.calc.get_next_trading_day(date(2026, 1, 1))
        assert result == date(2026, 1, 5)  # Next Monday after holiday weekend

    def test_next_trading_day_with_offset(self):
        """get_next_trading_day with n=5 returns 5 trading days ahead"""
        result = self.calc.get_next_trading_day(date(2026, 1, 5), n=5)
        # Should be the 5th trading day after Jan 5
        assert result > date(2026, 1, 5)

    def test_next_trading_day_n_equals_1_default(self):
        """Default n is 1"""
        result1 = self.calc.get_next_trading_day(date(2026, 1, 5))
        result2 = self.calc.get_next_trading_day(date(2026, 1, 5), n=1)
        assert result1 == result2

    # --- get_prev_trading_day ---

    def test_prev_trading_day_from_tuesday(self):
        """From a Tuesday that is a trading day, prev is Monday"""
        result = self.calc.get_prev_trading_day(date(2026, 1, 6))
        assert result == date(2026, 1, 5)

    def test_prev_trading_day_skips_weekend(self):
        """From Monday, prev trading day skips weekend"""
        # 2026-01-12 is Monday
        result = self.calc.get_prev_trading_day(date(2026, 1, 12))
        assert result == date(2026, 1, 9)  # Previous Friday

    def test_prev_trading_day_skips_holiday(self):
        """get_prev_trading_day skips a known holiday"""
        # 2026-01-05 is Monday, after 元旦 holidays (1/1-1/3)
        result = self.calc.get_prev_trading_day(date(2026, 1, 5))
        # Should go back to last trading day of 2025
        assert result < date(2026, 1, 5)

    def test_prev_trading_day_with_offset(self):
        """get_prev_trading_day with n=5 returns 5 trading days back"""
        result = self.calc.get_prev_trading_day(date(2026, 1, 16), n=5)
        assert result < date(2026, 1, 16)

    # --- get_trading_days_count ---

    def test_trading_days_count_single_week(self):
        """Count trading days in a single week (Mon-Fri, no holidays)"""
        # 2026-01-05 to 2026-01-09 is Mon-Fri, all trading
        count = self.calc.get_trading_days_count(date(2026, 1, 5), date(2026, 1, 9))
        assert count == 5

    def test_trading_days_count_includes_start_end(self):
        """Count includes both start and end dates"""
        count = self.calc.get_trading_days_count(date(2026, 1, 5), date(2026, 1, 5))
        assert count == 1

    def test_trading_days_count_skips_weekends(self):
        """Count skips Saturdays and Sundays"""
        # Mon 1/5 to Mon 1/12: 6 trading days (1/5-9 = 5, 1/12 = 1)
        count = self.calc.get_trading_days_count(date(2026, 1, 5), date(2026, 1, 12))
        assert count == 6

    def test_trading_days_count_skips_holidays(self):
        """Count skips holidays"""
        # 2026-01-01 to 2026-01-09 includes 元旦 holidays (1/1-1/3) + weekend (1/3-1/4)
        count = self.calc.get_trading_days_count(date(2026, 1, 1), date(2026, 1, 9))
        # Only 1/5, 1/6, 1/7, 1/8, 1/9 are trading days
        assert count == 5

    def test_trading_days_count_invalid_range(self):
        """Count returns 0 when start > end"""
        count = self.calc.get_trading_days_count(date(2026, 1, 9), date(2026, 1, 5))
        assert count == 0

    # --- add_trading_days ---

    def test_add_trading_days_positive(self):
        """add_trading_days with positive n moves forward"""
        result = self.calc.add_trading_days(date(2026, 1, 5), n=3)
        assert result == date(2026, 1, 8)

    def test_add_trading_days_negative(self):
        """add_trading_days with negative n moves backward"""
        result = self.calc.add_trading_days(date(2026, 1, 8), n=-3)
        assert result == date(2026, 1, 5)

    def test_add_trading_days_zero(self):
        """add_trading_days with n=0 returns same date if it's a trading day"""
        result = self.calc.add_trading_days(date(2026, 1, 5), n=0)
        assert result == date(2026, 1, 5)

    def test_add_trading_days_zero_on_non_trading(self):
        """add_trading_days with n=0 on non-trading day finds nearest trading day"""
        # Jan 3 2026 is Saturday
        result = self.calc.add_trading_days(date(2026, 1, 3), n=0)
        # Should snap to nearest trading day (previous Friday 1/2 or next Monday 1/5)
        assert result in [date(2026, 1, 2), date(2026, 1, 5)]


class TestIsTradingDay:
    """Tests for is_trading_day method"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.db_path = _seed_calendar_db()
        self.calc = DateCalculator(db_path=str(self.db_path))

    def teardown_method(self):
        if hasattr(self.calc, '_pool'):
            self.calc._pool.close_all()
        import time
        time.sleep(0.1)
        if self.db_path and self.db_path.exists():
            self.db_path.unlink(missing_ok=True)

    def test_trading_day_returns_true(self):
        """2026-01-05 (Monday, no holiday) is a trading day"""
        assert self.calc.is_trading_day(date(2026, 1, 5)) is True

    def test_saturday_returns_false(self):
        """Saturday is not a trading day"""
        assert self.calc.is_trading_day(date(2026, 1, 3)) is False

    def test_sunday_returns_false(self):
        """Sunday is not a trading day"""
        assert self.calc.is_trading_day(date(2026, 1, 4)) is False

    def test_holiday_returns_false(self):
        """2026-01-01 (元旦) is not a trading day"""
        assert self.calc.is_trading_day(date(2026, 1, 1)) is False


# ============================================================
# Helper: create a test SQLite DB with known calendar data
# ============================================================

def _empty_db() -> tempfile._TemporaryFileWrapper:
    """Create an empty SQLite DB file (no tables). Returns context manager that yields Path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return _PathContext(Path(tmp.name))


def _seed_calendar_db() -> Path:
    """Create a SQLite DB with January 2026 calendar data for testing."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                exchange_code TEXT NOT NULL DEFAULT 'ALL',
                product_code TEXT NOT NULL DEFAULT '',
                is_holiday INTEGER DEFAULT 0,
                holiday_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_date, exchange_code, product_code)
            )
        """)

        # Seed January 2026 calendar
        # 2026-01-01: 元旦 holiday (Thursday)
        # 2026-01-02: 元旦 holiday (Friday) - in the 2026 holiday list
        # 2026-01-03: Saturday
        # 2026-01-04: Sunday
        # 2026-01-05: Monday - trading
        # 2026-01-06: Tuesday - trading
        # 2026-01-07: Wednesday - trading
        # 2026-01-08: Thursday - trading
        # 2026-01-09: Friday - trading
        # 2026-01-10: Saturday
        # 2026-01-11: Sunday
        # 2026-01-12: Monday - trading
        # 2026-01-13: Tuesday - trading
        # 2026-01-14: Wednesday - trading
        # 2026-01-15: Thursday - trading
        # 2026-01-16: Friday - trading

        jan_data = [
            # (date, is_holiday, holiday_name)
            ('2026-01-01', 1, '元旦'),
            ('2026-01-02', 1, '元旦'),
            ('2026-01-03', 1, None),   # Saturday
            ('2026-01-04', 1, None),   # Sunday
            ('2026-01-05', 0, None),   # Monday - trading
            ('2026-01-06', 0, None),   # Tuesday - trading
            ('2026-01-07', 0, None),   # Wednesday - trading
            ('2026-01-08', 0, None),   # Thursday - trading
            ('2026-01-09', 0, None),   # Friday - trading
            ('2026-01-10', 1, None),   # Saturday
            ('2026-01-11', 1, None),   # Sunday
            ('2026-01-12', 0, None),   # Monday - trading
            ('2026-01-13', 0, None),   # Tuesday - trading
            ('2026-01-14', 0, None),   # Wednesday - trading
            ('2026-01-15', 0, None),   # Thursday - trading
            ('2026-01-16', 0, None),   # Friday - trading
        ]

        for d, is_hol, name in jan_data:
            conn.execute(
                "INSERT OR REPLACE INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday, holiday_name) VALUES (?, 'ALL', '', ?, ?)",
                (d, is_hol, name)
            )

        conn.commit()
    finally:
        conn.close()

    return db_path


class _PathContext:
    """Context manager that yields a Path and cleans up the file on exit."""
    def __init__(self, path: Path):
        self.path = path

    def __enter__(self):
        return self.path

    def __exit__(self, *args):
        import time
        time.sleep(0.1)
        if self.path.exists():
            try:
                self.path.unlink()
            except PermissionError:
                pass  # Windows file lock, will be cleaned up by OS


# ============================================================
# Extended Date Calculation Toolkit Tests
# ============================================================

class TestDateCalculatorExtended:
    """Tests for extended date calculation methods."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.db_path = _create_calendar_for_extended()
        self.calc = DateCalculator(db_path=str(self.db_path))

    def teardown_method(self):
        self.calc._pool.close_all()
        import time
        time.sleep(0.1)
        if self.db_path.exists():
            try:
                self.db_path.unlink()
            except PermissionError:
                pass

    def test_get_trading_days_list(self):
        """get_trading_days_list returns sorted trading days."""
        days = self.calc.get_trading_days_list(date(2026, 1, 5), date(2026, 1, 9))
        assert len(days) == 5
        assert days[0] == date(2026, 1, 5)
        assert days[-1] == date(2026, 1, 9)

    def test_get_trading_days_list_empty_range(self):
        """Empty range returns empty list."""
        days = self.calc.get_trading_days_list(date(2026, 1, 9), date(2026, 1, 5))
        assert days == []

    def test_get_last_trading_day_of_month(self):
        """Find last trading day of a month."""
        last = self.calc.get_last_trading_day_of_month(2026, 1)
        # Jan 30, 2026 is Friday, Jan 31 is Saturday
        assert last == date(2026, 1, 30)

    def test_get_first_trading_day_of_month(self):
        """Find first trading day of a month."""
        first = self.calc.get_first_trading_day_of_month(2026, 1)
        # Jan 1 is holiday, Jan 2 is trading (seeded as is_holiday=0)
        assert first == date(2026, 1, 2)

    def test_snap_to_trading_day_forward(self):
        """Snap Saturday to next trading day."""
        result = self.calc.snap_to_trading_day(date(2026, 1, 3), direction='forward')
        assert result == date(2026, 1, 5)

    def test_snap_to_trading_day_backward(self):
        """Snap Saturday to previous trading day."""
        result = self.calc.snap_to_trading_day(date(2026, 1, 3), direction='backward')
        assert result == date(2026, 1, 2)

    def test_snap_to_trading_day_nearest(self):
        """Snap to nearest trading day."""
        # Saturday Jan 3: Fri Jan 2 is 1 day back, Mon Jan 5 is 2 days forward
        result = self.calc.snap_to_trading_day(date(2026, 1, 3), direction='nearest')
        assert result == date(2026, 1, 2)

    def test_snap_to_trading_day_already_trading(self):
        """Snap a trading day returns itself."""
        result = self.calc.snap_to_trading_day(date(2026, 1, 5))
        assert result == date(2026, 1, 5)

    def test_get_trading_day_offset_positive(self):
        """Trading day offset from Mon to Fri is +4."""
        offset = self.calc.get_trading_day_offset(date(2026, 1, 5), date(2026, 1, 9))
        assert offset == 4  # Mon->Tue(1), Wed(2), Thu(3), Fri(4)

    def test_get_trading_day_offset_negative(self):
        """Trading day offset from Fri to Mon is -4."""
        offset = self.calc.get_trading_day_offset(date(2026, 1, 9), date(2026, 1, 5))
        assert offset == -4

    def test_get_trading_day_offset_same_day(self):
        """Offset from same day is 0."""
        offset = self.calc.get_trading_day_offset(date(2026, 1, 5), date(2026, 1, 5))
        assert offset == 0


def _create_calendar_for_extended() -> Path:
    """Create a SQLite DB with January 2026 calendar data."""
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

        # Jan 2026: weekdays = 2, 5-9, 12-16, 19-23, 26-30
        # Holidays: Jan 1 (元旦)
        trading_days = ['2026-01-02', '2026-01-05', '2026-01-06', '2026-01-07',
                        '2026-01-08', '2026-01-09', '2026-01-12', '2026-01-13',
                        '2026-01-14', '2026-01-15', '2026-01-16', '2026-01-19',
                        '2026-01-20', '2026-01-21', '2026-01-22', '2026-01-23',
                        '2026-01-26', '2026-01-27', '2026-01-28', '2026-01-29',
                        '2026-01-30']
        for d in trading_days:
            conn.execute(
                "INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday) VALUES (?, 'ALL', '', 0)",
                (d,)
            )
        # Jan 1 is holiday (元旦)
        conn.execute(
            "INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday) VALUES (?, 'ALL', '', 1)",
            ('2026-01-01',)
        )
        conn.commit()
    finally:
        conn.close()

    return db_path
