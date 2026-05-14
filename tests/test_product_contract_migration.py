"""TDD tests for product/contract schema migration v3"""

import sqlite3
import tempfile
from pathlib import Path
import pytest


class TestProductContractMigrationV3:
    """Tests for migration v3 adding multiplier, price_tick, etc. to product_config and contract_info"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create a SQLite DB with the pre-v3 schema"""
        self.db_path = _create_pre_v3_schema_db()
        self.conn = sqlite3.connect(str(self.db_path))

    def teardown_method(self):
        if self.conn:
            self.conn.close()
        if self.db_path and self.db_path.exists():
            try:
                self.db_path.unlink()
            except PermissionError:
                pass

    def test_product_config_has_existing_columns(self):
        """Pre-v3 product_config has basic columns"""
        columns = self._get_columns('product_config')
        assert 'product_code' in columns
        assert 'product_name' in columns

    def test_product_config_lacks_new_columns(self):
        """Pre-v3 product_config does NOT have new fields"""
        columns = self._get_columns('product_config')
        assert 'multiplier' not in columns
        assert 'price_tick' not in columns
        assert 'margin_rate' not in columns
        assert 'option_style' not in columns

    def test_contract_info_has_existing_columns(self):
        """Pre-v3 contract_info has basic columns"""
        columns = self._get_columns('contract_info')
        assert 'contract_code' in columns
        assert 'listing_date' in columns
        assert 'expiry_date' in columns

    def test_contract_info_lacks_new_columns(self):
        """Pre-v3 contract_info does NOT have new fields"""
        columns = self._get_columns('contract_info')
        assert 'last_trade_date' not in columns
        assert 'delivery_date' not in columns

    def test_migration_adds_product_columns(self):
        """Migration adds multiplier, price_tick, margin_rate, option_style to product_config"""
        from tzdata_pkg.maintenance.metadata.migrate_calendar_v3 import migrate
        migrate(db_path=str(self.db_path))

        columns = self._get_columns('product_config')
        assert 'multiplier' in columns
        assert 'price_tick' in columns
        assert 'margin_rate' in columns
        assert 'option_style' in columns

    def test_migration_adds_contract_columns(self):
        """Migration adds last_trade_date, delivery_date to contract_info"""
        from tzdata_pkg.maintenance.metadata.migrate_calendar_v3 import migrate
        migrate(db_path=str(self.db_path))

        columns = self._get_columns('contract_info')
        assert 'last_trade_date' in columns
        assert 'delivery_date' in columns

    def test_migration_preserves_data(self):
        """Migration preserves existing product and contract data"""
        self.conn.execute(
            "INSERT INTO product_config (exchange_code, product_code, product_name) VALUES (?, ?, ?)",
            ('CFFEX', 'MO', '中证1000期权')
        )
        self.conn.execute(
            "INSERT INTO contract_info (contract_code, exchange_code, product_code) VALUES (?, ?, ?)",
            ('MO2506', 'CFFEX', 'MO')
        )
        self.conn.commit()

        from tzdata_pkg.maintenance.metadata.migrate_calendar_v3 import migrate
        migrate(db_path=str(self.db_path))

        row = self.conn.execute(
            "SELECT product_code, product_name FROM product_config WHERE product_code = 'MO'"
        ).fetchone()
        assert row is not None
        assert row[1] == '中证1000期权'

        row = self.conn.execute(
            "SELECT contract_code FROM contract_info WHERE contract_code = 'MO2506'"
        ).fetchone()
        assert row is not None

    def test_migration_is_idempotent(self):
        """Running migration v3 twice does not fail"""
        from tzdata_pkg.maintenance.metadata.migrate_calendar_v3 import migrate
        migrate(db_path=str(self.db_path))
        migrate(db_path=str(self.db_path))

        columns = self._get_columns('product_config')
        assert 'multiplier' in columns

    def test_new_columns_accept_nullable_values(self):
        """New columns accept NULL (default) values"""
        from tzdata_pkg.maintenance.metadata.migrate_calendar_v3 import migrate
        migrate(db_path=str(self.db_path))

        # Insert product without specifying new fields
        self.conn.execute(
            "INSERT INTO product_config (exchange_code, product_code, product_name) VALUES (?, ?, ?)",
            ('CFFEX', 'IF', '沪深300期货')
        )
        self.conn.commit()

        row = self.conn.execute("SELECT multiplier, price_tick FROM product_config WHERE product_code = 'IF'").fetchone()
        assert row is not None

    def _get_columns(self, table):
        rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [row[1] for row in rows]


def _create_pre_v3_schema_db() -> Path:
    """Create a SQLite DB with product_config and contract_info (pre-v3 schema)"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange_code TEXT NOT NULL,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_type TEXT,
                is_tracked INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(exchange_code, product_code)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contract_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_code TEXT NOT NULL UNIQUE,
                exchange_code TEXT,
                product_code TEXT,
                contract_type TEXT,
                underlying_contract TEXT,
                strike_price REAL,
                listing_date TEXT,
                expiry_date TEXT,
                delisting_date TEXT,
                multiplier REAL,
                tick_size REAL,
                status TEXT DEFAULT 'active',
                is_tracked INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()

    return db_path
