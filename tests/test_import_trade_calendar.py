"""TDD tests for Tushare trade calendar import."""

import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


class TestTradeCalendarImport:
    """Tests for importing trade calendar from Tushare."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create a SQLite DB with trade_calendar schema."""
        self.db_path = _create_calendar_db()
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

    def _make_mock_df(self, rows):
        """Create a mock DataFrame from list of dicts."""
        return pd.DataFrame(rows)

    def test_import_creates_calendar_records(self):
        """Importing from Tushare inserts records into trade_calendar."""
        from tzdata_pkg.cli.import_trade_calendar import CalendarImporter

        mock_df = self._make_mock_df([
            {'cal_date': '20260101', 'is_open': 0, 'pre_trade_date': '20251231'},
            {'cal_date': '20260102', 'is_open': 1, 'pre_trade_date': '20251231'},
            {'cal_date': '20260105', 'is_open': 1, 'pre_trade_date': '20260102'},
        ])

        importer = CalendarImporter(db_path=str(self.db_path))
        importer._fetch_from_tushare = MagicMock(return_value=mock_df)
        importer.import_calendar(exchange='CFFEX', start_date='2026-01-01', end_date='2026-01-31')

        count = self.conn.execute("SELECT COUNT(*) FROM trade_calendar WHERE exchange_code='CFFEX'").fetchone()[0]
        assert count == 3

    def test_import_maps_is_open_correctly(self):
        """Tushare is_open=0 maps to is_holiday=1, is_open=1 maps to is_holiday=0."""
        from tzdata_pkg.cli.import_trade_calendar import CalendarImporter

        mock_df = self._make_mock_df([
            {'cal_date': '20260101', 'is_open': 0, 'pre_trade_date': ''},
            {'cal_date': '20260102', 'is_open': 1, 'pre_trade_date': '20260101'},
        ])

        importer = CalendarImporter(db_path=str(self.db_path))
        importer._fetch_from_tushare = MagicMock(return_value=mock_df)
        importer.import_calendar(exchange='CFFEX', start_date='2026-01-01', end_date='2026-01-31')

        holiday = self.conn.execute("SELECT is_holiday FROM trade_calendar WHERE trade_date='2026-01-01' AND exchange_code='CFFEX'").fetchone()
        assert holiday[0] == 1

        trading = self.conn.execute("SELECT is_holiday FROM trade_calendar WHERE trade_date='2026-01-02' AND exchange_code='CFFEX'").fetchone()
        assert trading[0] == 0

    def test_import_is_incremental(self):
        """Import skips dates that already exist (no duplicates)."""
        from tzdata_pkg.cli.import_trade_calendar import CalendarImporter

        # First import
        mock_df1 = self._make_mock_df([
            {'cal_date': '20260102', 'is_open': 1, 'pre_trade_date': '20260101'},
            {'cal_date': '20260105', 'is_open': 1, 'pre_trade_date': '20260102'},
        ])
        importer = CalendarImporter(db_path=str(self.db_path))
        importer._fetch_from_tushare = MagicMock(return_value=mock_df1)
        importer.import_calendar(exchange='CFFEX', start_date='2026-01-01', end_date='2026-01-31')

        # Second import with overlapping dates
        mock_df2 = self._make_mock_df([
            {'cal_date': '20260102', 'is_open': 1, 'pre_trade_date': '20260101'},  # duplicate
            {'cal_date': '20260106', 'is_open': 1, 'pre_trade_date': '20260105'},  # new
        ])
        importer._fetch_from_tushare = MagicMock(return_value=mock_df2)
        importer.import_calendar(exchange='CFFEX', start_date='2026-01-01', end_date='2026-01-31')

        count = self.conn.execute("SELECT COUNT(*) FROM trade_calendar WHERE exchange_code='CFFEX'").fetchone()[0]
        assert count == 3  # 0102, 0105, 0106 — no dupes

    def test_import_also_populates_all_exchange(self):
        """Import populates both exchange-specific and 'ALL' exchange records."""
        from tzdata_pkg.cli.import_trade_calendar import CalendarImporter

        mock_df = self._make_mock_df([
            {'cal_date': '20260102', 'is_open': 1, 'pre_trade_date': '20260101'},
        ])

        importer = CalendarImporter(db_path=str(self.db_path))
        importer._fetch_from_tushare = MagicMock(return_value=mock_df)
        importer.import_calendar(exchange='CFFEX', start_date='2026-01-01', end_date='2026-01-31')

        all_count = self.conn.execute("SELECT COUNT(*) FROM trade_calendar WHERE exchange_code='ALL'").fetchone()[0]
        cffex_count = self.conn.execute("SELECT COUNT(*) FROM trade_calendar WHERE exchange_code='CFFEX'").fetchone()[0]
        assert all_count == 1
        assert cffex_count == 1

    def test_import_returns_record_count(self):
        """Import returns the number of newly inserted records."""
        from tzdata_pkg.cli.import_trade_calendar import CalendarImporter

        mock_df = self._make_mock_df([
            {'cal_date': '20260102', 'is_open': 1, 'pre_trade_date': '20260101'},
            {'cal_date': '20260105', 'is_open': 1, 'pre_trade_date': '20260102'},
        ])

        importer = CalendarImporter(db_path=str(self.db_path))
        importer._fetch_from_tushare = MagicMock(return_value=mock_df)
        result = importer.import_calendar(exchange='CFFEX', start_date='2026-01-01', end_date='2026-01-31')

        assert result['inserted'] == 2

    def test_import_empty_response(self):
        """Import handles empty Tushare response gracefully."""
        from tzdata_pkg.cli.import_trade_calendar import CalendarImporter

        importer = CalendarImporter(db_path=str(self.db_path))
        importer._fetch_from_tushare = MagicMock(return_value=None)
        result = importer.import_calendar(exchange='CFFEX', start_date='2026-01-01', end_date='2026-01-31')

        assert result['inserted'] == 0


def _create_calendar_db() -> Path:
    """Create a SQLite DB with trade_calendar table (new schema)."""
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
        conn.commit()
    finally:
        conn.close()

    return db_path
