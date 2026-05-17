"""P1-10: Minute-level data completeness tests.

Tests for MinuteCompletenessChecker using mocked DB connections.
"""
import sqlite3
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tzdata_pkg.maintenance.monitoring.minute_completeness import (
    MinuteCompletenessChecker,
    EXPECTED_MINUTES,
)


def _create_test_db():
    """Create temp DB with minute_quotes + data_catalog tables."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS minute_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            contract_code TEXT NOT NULL,
            frequency TEXT DEFAULT '1min',
            trade_time TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume INTEGER DEFAULT 0,
            amount REAL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS data_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            catalog_name TEXT NOT NULL,
            exchange_code TEXT NOT NULL,
            product_code TEXT NOT NULL,
            contract_code TEXT NOT NULL,
            data_type TEXT NOT NULL,
            frequency TEXT DEFAULT '1min',
            data_source TEXT,
            sync_mode TEXT DEFAULT 'incremental',
            enabled INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()
    return db_path


def _insert_minutes(db_path: Path, contract_code: str, trade_date: str,
                    count: int, frequency: str = '1min'):
    """Insert N minute records for a given date/contract."""
    conn = sqlite3.connect(str(db_path))
    base_time = 9 * 60  # 09:00
    for i in range(count):
        minutes = base_time + i
        h = minutes // 60
        m = minutes % 60
        time_str = f"{h:02d}:{m:02d}"
        conn.execute("""
            INSERT INTO minute_quotes
                (trade_date, contract_code, frequency, trade_time, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, 100, 101, 99, 100, 1)
        """, (trade_date, contract_code, frequency, time_str))
    conn.commit()
    conn.close()


def _insert_catalog(db_path: Path, catalog_id: int, contract_code: str, frequency: str = '1min'):
    """Insert a data_catalog row."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        INSERT OR REPLACE INTO data_catalog
            (id, catalog_name, exchange_code, product_code, contract_code,
             data_type, frequency, data_source, sync_mode)
        VALUES (?, 'test_catalog', 'CFFEX', 'IM', ?, 'minute', ?, 'tushare', 'incremental')
    """, (catalog_id, contract_code, frequency))
    conn.commit()
    conn.close()


def _mock_pool(db_path: Path):
    """Create a mock pool that returns a connection to our temp DB."""
    mock_pool = MagicMock()
    conn = sqlite3.connect(str(db_path))
    mock_pool.transaction.return_value.__enter__ = lambda self: conn
    mock_pool.transaction.return_value.__exit__ = lambda self, *args: None
    mock_pool.connection.return_value.__enter__ = lambda self: conn
    mock_pool.connection.return_value.__exit__ = lambda self, *args: None
    return mock_pool, conn


class TestDayCompletenessComplete:
    """Full day of minute data should return 'complete'."""

    def test_full_day_1min(self):
        db_path = _create_test_db()
        try:
            _insert_minutes(db_path, "IM2506", "2025-03-10", 240, '1min')
            mock_pool, conn = _mock_pool(db_path)

            with patch('tzdata_pkg.maintenance.monitoring.minute_completeness.DBRegistry') as MockRegistry:
                MockRegistry.return_value.get_pool.return_value = mock_pool

                result = MinuteCompletenessChecker.check_day_completeness(
                    "IM2506", date(2025, 3, 10), '1min'
                )

            assert result['actual_count'] == 240
            assert result['status'] == 'complete'
            assert result['completeness_pct'] == 100.0
            conn.close()
        finally:
            db_path.unlink()

    def test_full_day_5min(self):
        db_path = _create_test_db()
        try:
            _insert_minutes(db_path, "IM2506", "2025-03-10", 48, '5min')
            mock_pool, conn = _mock_pool(db_path)

            with patch('tzdata_pkg.maintenance.monitoring.minute_completeness.DBRegistry') as MockRegistry:
                MockRegistry.return_value.get_pool.return_value = mock_pool

                result = MinuteCompletenessChecker.check_day_completeness(
                    "IM2506", date(2025, 3, 10), '5min'
                )

            assert result['actual_count'] == 48
            assert result['status'] == 'complete'
            conn.close()
        finally:
            db_path.unlink()


class TestDayCompletenessPartial:
    """Partial minute data should return 'partial' or 'incomplete'."""

    def test_partial_day_1min(self):
        """100 minutes: below threshold (180) → incomplete."""
        db_path = _create_test_db()
        try:
            _insert_minutes(db_path, "IM2506", "2025-03-10", 100, '1min')
            mock_pool, conn = _mock_pool(db_path)

            with patch('tzdata_pkg.maintenance.monitoring.minute_completeness.DBRegistry') as MockRegistry:
                MockRegistry.return_value.get_pool.return_value = mock_pool

                result = MinuteCompletenessChecker.check_day_completeness(
                    "IM2506", date(2025, 3, 10), '1min'
                )

            assert result['actual_count'] == 100
            assert result['status'] == 'incomplete'
            conn.close()
        finally:
            db_path.unlink()

    def test_near_complete_1min(self):
        """220 minutes: above 90% of 240 → complete."""
        db_path = _create_test_db()
        try:
            _insert_minutes(db_path, "IM2506", "2025-03-10", 220, '1min')
            mock_pool, conn = _mock_pool(db_path)

            with patch('tzdata_pkg.maintenance.monitoring.minute_completeness.DBRegistry') as MockRegistry:
                MockRegistry.return_value.get_pool.return_value = mock_pool

                result = MinuteCompletenessChecker.check_day_completeness(
                    "IM2506", date(2025, 3, 10), '1min'
                )

            assert result['actual_count'] == 220
            assert result['status'] == 'complete'
            conn.close()
        finally:
            db_path.unlink()


class TestDayCompletenessMissing:
    """No data for a date should return 'missing'."""

    def test_no_data(self):
        db_path = _create_test_db()
        try:
            mock_pool, conn = _mock_pool(db_path)

            with patch('tzdata_pkg.maintenance.monitoring.minute_completeness.DBRegistry') as MockRegistry:
                MockRegistry.return_value.get_pool.return_value = mock_pool

                result = MinuteCompletenessChecker.check_day_completeness(
                    "IM2506", date(2025, 3, 10), '1min'
                )

            assert result['status'] == 'missing'
            assert result['actual_count'] == 0
            conn.close()
        finally:
            db_path.unlink()


class TestDateRangeCompleteness:
    """Check completeness across multiple trading days."""

    def test_mixed_completeness(self):
        db_path = _create_test_db()
        try:
            _insert_catalog(db_path, 1, "IM2506")
            _insert_minutes(db_path, "IM2506", "2025-03-10", 240, '1min')  # complete (240)
            _insert_minutes(db_path, "IM2506", "2025-03-11", 200, '1min')  # partial (180<=200<216)
            # 2025-03-12: no data → missing

            mock_pool, conn = _mock_pool(db_path)

            with patch('tzdata_pkg.maintenance.monitoring.minute_completeness.DBRegistry') as MockRegistry:
                MockRegistry.return_value.get_pool.return_value = mock_pool

                trading_days = [
                    date(2025, 3, 10),
                    date(2025, 3, 11),
                    date(2025, 3, 12),
                ]

                result = MinuteCompletenessChecker.check_date_range_completeness(
                    1, trading_days, '1min'
                )

            assert result['total_trading_days'] == 3
            assert result['complete_days'] == 1
            assert result['missing_days'] == 1
            assert result['partial_days'] == 1
            conn.close()
        finally:
            db_path.unlink()


class TestExpectedMinutesConfig:
    """Verify expected minute counts are reasonable."""

    def test_1min_day_only(self):
        assert EXPECTED_MINUTES['1min']['day_only'] == 240

    def test_1min_with_night(self):
        assert EXPECTED_MINUTES['1min']['with_night'] == 480

    def test_5min_day_only(self):
        assert EXPECTED_MINUTES['5min']['day_only'] == 48  # 240 / 5

    def test_threshold_less_than_expected(self):
        """Threshold should be less than expected count."""
        for freq, config in EXPECTED_MINUTES.items():
            assert config['min_threshold'] < config['day_only'], \
                f"{freq} threshold should be less than expected"
