"""TDD tests for trading hours management."""

import sqlite3
import tempfile
import time
from pathlib import Path

import pytest


class TestTradingHoursManagement:
    """Tests for trading hours template and session management."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create a SQLite DB with trading_hours tables."""
        self.db_path = _create_trading_hours_db()
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

    def test_create_template(self):
        """Create a trading hours template."""
        from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager
        mgr = TradingHoursManager(db_path=str(self.db_path))

        mgr.create_template(
            template_id='cffex_if',
            template_name='中金所股指期货',
            exchange_code='CFFEX',
            product_type='index_future',
            normal_schedule=[{"start": "09:30", "end": "11:30"}, {"start": "13:00", "end": "15:00"}],
            is_default=1
        )

        row = self.conn.execute(
            "SELECT template_name, exchange_code FROM trading_hours_template WHERE template_id = 'cffex_if'"
        ).fetchone()
        assert row is not None
        assert row[0] == '中金所股指期货'
        assert row[1] == 'CFFEX'

    def test_get_template(self):
        """Retrieve template by ID."""
        from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager
        mgr = TradingHoursManager(db_path=str(self.db_path))

        mgr.create_template(
            template_id='cffex_mo',
            template_name='中金所股指期权',
            exchange_code='CFFEX',
            product_type='index_option',
            normal_schedule=[{"start": "09:30", "end": "11:30"}, {"start": "13:00", "end": "15:00"}]
        )

        tmpl = mgr.get_template('cffex_mo')
        assert tmpl is not None
        assert tmpl['template_name'] == '中金所股指期权'

    def test_is_trading_time(self):
        """Check if a specific time is within trading hours."""
        from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager
        mgr = TradingHoursManager(db_path=str(self.db_path))

        mgr.create_template(
            template_id='cffex_if',
            template_name='中金所股指期货',
            exchange_code='CFFEX',
            product_type='index_future',
            normal_schedule=[{"start": "09:30", "end": "11:30"}, {"start": "13:00", "end": "15:00"}]
        )

        assert mgr.is_trading_time('cffex_if', '10:00') is True
        assert mgr.is_trading_time('cffex_if', '12:00') is False  # lunch break
        assert mgr.is_trading_time('cffex_if', '14:00') is True
        assert mgr.is_trading_time('cffex_if', '15:30') is False

    def test_is_trading_time_with_night_session(self):
        """Handle night session trading hours."""
        from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager
        mgr = TradingHoursManager(db_path=str(self.db_path))

        mgr.create_template(
            template_id='shfe_au',
            template_name='上期所黄金期货',
            exchange_code='SHFE',
            product_type='commodity_future',
            normal_schedule=[{"start": "09:00", "end": "11:30"}, {"start": "13:30", "end": "15:00"}],
            night_schedule=[{"start": "21:00", "end": "02:30"}]
        )

        assert mgr.is_trading_time('shfe_au', '10:00') is True
        assert mgr.is_trading_time('shfe_au', '22:00') is True  # night session
        assert mgr.is_trading_time('shfe_au', '16:00') is False

    def test_get_sessions_for_date(self):
        """Get all trading sessions for a given date."""
        from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager
        mgr = TradingHoursManager(db_path=str(self.db_path))

        mgr.create_template(
            template_id='shfe_au',
            template_name='上期所黄金期货',
            exchange_code='SHFE',
            product_type='commodity_future',
            normal_schedule=[{"start": "09:00", "end": "11:30"}, {"start": "13:30", "end": "15:00"}],
            night_schedule=[{"start": "21:00", "end": "02:30"}]
        )

        sessions = mgr.get_sessions('shfe_au')
        assert len(sessions) == 3  # 2 normal + 1 night
        assert sessions[0]['start'] == '09:00'
        assert sessions[2]['start'] == '21:00'


def _create_trading_hours_db() -> Path:
    """Create a SQLite DB with trading_hours tables."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trading_hours_template (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id TEXT NOT NULL UNIQUE,
                template_name TEXT NOT NULL,
                exchange_code TEXT NOT NULL,
                product_type TEXT NOT NULL,
                normal_schedule TEXT NOT NULL,
                night_schedule TEXT,
                pre_open TEXT,
                pre_close TEXT,
                is_default INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_trading_hours (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange_code TEXT NOT NULL,
                product_code TEXT NOT NULL,
                template_id TEXT,
                effective_date TEXT,
                schedule_override TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(exchange_code, product_code, effective_date)
            )
        """)
        conn.commit()
    finally:
        conn.close()

    return db_path
