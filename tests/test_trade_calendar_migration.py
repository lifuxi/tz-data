"""TDD tests for trade_calendar schema migration"""

import sqlite3
import tempfile
from pathlib import Path
from datetime import date
import pytest


class TestTradeCalendarSchemaMigration:
    """Tests for the schema migration adding new columns to trade_calendar"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create a SQLite DB with the OLD schema (before migration)"""
        self.db_path = _create_old_schema_db()
        self.conn = sqlite3.connect(str(self.db_path))

    def teardown_method(self):
        if self.conn:
            self.conn.close()
        if self.db_path and self.db_path.exists():
            try:
                self.db_path.unlink()
            except PermissionError:
                pass

    def test_old_schema_has_required_columns(self):
        """Old schema has base columns: trade_date, exchange_code, is_holiday, holiday_name"""
        columns = self._get_columns()
        assert 'trade_date' in columns
        assert 'exchange_code' in columns
        assert 'is_holiday' in columns
        assert 'holiday_name' in columns

    def test_old_schema_lacks_new_columns(self):
        """Old schema does NOT have new columns before migration"""
        columns = self._get_columns()
        assert 'day_of_week' not in columns
        assert 'is_weekend' not in columns
        assert 'is_workday' not in columns
        assert 'special_flag' not in columns
        assert 'product_code' not in columns

    def test_migration_adds_new_columns(self):
        """Migration adds all required new columns"""
        from tzdata_pkg.maintenance.metadata.migrate_calendar_v2 import migrate
        migrate(db_path=str(self.db_path))

        columns = self._get_columns()
        assert 'day_of_week' in columns
        assert 'is_weekend' in columns
        assert 'is_workday' in columns
        assert 'special_flag' in columns
        assert 'product_code' in columns

    def test_migration_preserves_data(self):
        """Migration preserves existing trade_date data"""
        # Insert test data
        self.conn.execute(
            "INSERT INTO trade_calendar (trade_date, exchange_code, is_holiday, holiday_name) VALUES (?, 'ALL', 0, '')",
            ('2026-01-05',)
        )
        self.conn.commit()

        from tzdata_pkg.maintenance.metadata.migrate_calendar_v2 import migrate
        migrate(db_path=str(self.db_path))

        row = self.conn.execute(
            "SELECT trade_date, exchange_code FROM trade_calendar WHERE trade_date = ?",
            ('2026-01-05',)
        ).fetchone()
        assert row is not None
        assert row[0] == '2026-01-05'
        assert row[1] == 'ALL'

    def test_migration_populates_derived_fields(self):
        """Migration correctly derives day_of_week and is_weekend from existing data"""
        # Insert a known date: 2026-01-05 is Monday (weekday=0)
        self.conn.execute(
            "INSERT INTO trade_calendar (trade_date, exchange_code, is_holiday) VALUES (?, 'ALL', 0)",
            ('2026-01-05',)
        )
        # 2026-01-03 is Saturday
        self.conn.execute(
            "INSERT INTO trade_calendar (trade_date, exchange_code, is_holiday) VALUES (?, 'ALL', 1)",
            ('2026-01-03',)
        )
        self.conn.commit()

        from tzdata_pkg.maintenance.metadata.migrate_calendar_v2 import migrate
        migrate(db_path=str(self.db_path))

        # Monday should have day_of_week=1 (ISO Monday=1) and is_weekend=0
        row = self.conn.execute(
            "SELECT day_of_week, is_weekend FROM trade_calendar WHERE trade_date = ?",
            ('2026-01-05',)
        ).fetchone()
        assert row[0] == 1  # Monday
        assert row[1] == 0

        # Saturday should have day_of_week=6 and is_weekend=1
        row = self.conn.execute(
            "SELECT day_of_week, is_weekend FROM trade_calendar WHERE trade_date = ?",
            ('2026-01-03',)
        ).fetchone()
        assert row[0] == 6  # Saturday
        assert row[1] == 1

    def test_migration_is_idempotent(self):
        """Running migration twice does not fail"""
        from tzdata_pkg.maintenance.metadata.migrate_calendar_v2 import migrate
        migrate(db_path=str(self.db_path))
        # Second run should be a no-op
        migrate(db_path=str(self.db_path))

        columns = self._get_columns()
        assert 'day_of_week' in columns

    def test_new_schema_has_unique_constraint(self):
        """After migration, UNIQUE constraint exists on (trade_date, exchange_code, product_code)"""
        from tzdata_pkg.maintenance.metadata.migrate_calendar_v2 import migrate
        migrate(db_path=str(self.db_path))

        # Try to insert duplicate rows — should fail
        self.conn.execute(
            "INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday) VALUES (?, 'ALL', '', 0)",
            ('2026-01-05',)
        )
        self.conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday) VALUES (?, 'ALL', '', 0)",
                ('2026-01-05',)
            )
            self.conn.commit()

    def _get_columns(self):
        """Get column names from trade_calendar table"""
        rows = self.conn.execute("PRAGMA table_info(trade_calendar)").fetchall()
        return [row[1] for row in rows]


def _create_old_schema_db() -> Path:
    """Create a SQLite DB with the old trade_calendar schema (no product_code, no new fields)"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL UNIQUE,
                exchange_code TEXT NOT NULL DEFAULT 'ALL',
                is_holiday INTEGER DEFAULT 0,
                holiday_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()

    return db_path
