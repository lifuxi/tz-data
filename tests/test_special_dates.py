"""TDD tests for special date override functionality."""

import sqlite3
import tempfile
import time
from datetime import date
from pathlib import Path

import pytest


class TestSpecialDates:
    """Tests for special_date_override CRUD and override priority."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create a SQLite DB with the required schema."""
        self.db_path = _create_special_dates_db()
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

    def test_create_special_date(self):
        """SpecialDateManager.create inserts a record."""
        from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager
        mgr = SpecialDateManager(db_path=str(self.db_path))
        mgr.create(
            exchange_code='CFFEX',
            trade_date=date(2026, 2, 17),
            override_type='holiday',
            reason='临时休市',
            operator='admin'
        )
        row = self.conn.execute(
            "SELECT exchange_code, trade_date, override_type, reason FROM special_date_override"
        ).fetchone()
        assert row is not None
        assert row[0] == 'CFFEX'
        assert row[1] == '2026-02-17'
        assert row[2] == 'holiday'
        assert row[3] == '临时休市'

    def test_list_special_dates_by_exchange(self):
        """SpecialDateManager.list filters by exchange_code."""
        from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager
        mgr = SpecialDateManager(db_path=str(self.db_path))
        mgr.create('CFFEX', date(2026, 5, 1), 'holiday', '劳动节', 'admin')
        mgr.create('SHFE', date(2026, 5, 1), 'holiday', '劳动节', 'admin')
        mgr.create('CFFEX', date(2026, 10, 1), 'holiday', '国庆节', 'admin')

        results = mgr.list(exchange_code='CFFEX')
        assert len(results) == 2

    def test_list_special_dates_by_date_range(self):
        """SpecialDateManager.list filters by date range."""
        from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager
        mgr = SpecialDateManager(db_path=str(self.db_path))
        mgr.create('CFFEX', date(2026, 1, 27), 'holiday', '春节', 'admin')
        mgr.create('CFFEX', date(2026, 10, 1), 'holiday', '国庆', 'admin')

        results = mgr.list(start_date=date(2026, 1, 1), end_date=date(2026, 6, 30))
        assert len(results) == 1
        assert results[0]['trade_date'] == '2026-01-27'

    def test_delete_special_date(self):
        """SpecialDateManager.delete removes a record."""
        from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager
        mgr = SpecialDateManager(db_path=str(self.db_path))
        mgr.create('CFFEX', date(2026, 3, 15), 'half_day', '设备检修', 'admin')
        count_before = self.conn.execute("SELECT COUNT(*) FROM special_date_override").fetchone()[0]
        assert count_before == 1

        mgr.delete('CFFEX', date(2026, 3, 15))
        count_after = self.conn.execute("SELECT COUNT(*) FROM special_date_override").fetchone()[0]
        assert count_after == 0

    def test_override_priority_makes_trading_day_holiday(self):
        """Special date override can make a weekday holiday even if not in calendar."""
        from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager
        from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator

        # Seed a basic calendar where 2026-06-15 (Monday) is a trading day
        self.conn.execute("""
            INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday)
            VALUES ('2026-06-15', 'ALL', '', 0)
        """)
        self.conn.commit()

        calc = DateCalculator(db_path=str(self.db_path))
        assert calc.is_trading_day(date(2026, 6, 15)) is True

        # Add a special override to make it a holiday
        mgr = SpecialDateManager(db_path=str(self.db_path))
        mgr.create('ALL', date(2026, 6, 15), 'holiday', '特殊休市', 'admin')

        assert calc.is_trading_day(date(2026, 6, 15)) is False

    def test_override_priority_makes_holiday_trading_day(self):
        """Special date override can make a holiday a trading day (调休)."""
        from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager
        from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator

        # Seed a calendar where 2026-02-14 (Saturday) is a holiday/weekend
        self.conn.execute("""
            INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday)
            VALUES ('2026-02-14', 'ALL', '', 1)
        """)
        self.conn.commit()

        calc = DateCalculator(db_path=str(self.db_path))
        assert calc.is_trading_day(date(2026, 2, 14)) is False

        # Add a special override to make it a trading day (调休补班)
        mgr = SpecialDateManager(db_path=str(self.db_path))
        mgr.create('ALL', date(2026, 2, 14), 'workday', '调休工作日', 'admin')

        assert calc.is_trading_day(date(2026, 2, 14)) is True

    def test_special_date_is_idempotent(self):
        """Creating the same special date twice does not fail (upsert)."""
        from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager
        mgr = SpecialDateManager(db_path=str(self.db_path))
        mgr.create('CFFEX', date(2026, 1, 1), 'holiday', '元旦', 'admin')
        mgr.create('CFFEX', date(2026, 1, 1), 'holiday', '元旦更新', 'admin')

        count = self.conn.execute("SELECT COUNT(*) FROM special_date_override").fetchone()[0]
        assert count == 1

        row = self.conn.execute("SELECT reason FROM special_date_override").fetchone()
        assert row[0] == '元旦更新'


def _create_special_dates_db() -> Path:
    """Create a SQLite DB with trade_calendar and special_date_override tables."""
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
                holiday_name TEXT,
                day_of_week INTEGER DEFAULT 0,
                is_weekend INTEGER DEFAULT 0,
                is_workday INTEGER DEFAULT 0,
                special_flag TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_date, exchange_code, product_code)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS special_date_override (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                override_type TEXT NOT NULL,  -- holiday, workday, half_day
                reason TEXT,
                operator TEXT DEFAULT 'system',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(exchange_code, trade_date)
            )
        """)
        conn.commit()
    finally:
        conn.close()

    return db_path
