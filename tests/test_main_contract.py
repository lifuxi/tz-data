"""TDD tests for main contract identification."""

import sqlite3
import tempfile
import time
from datetime import date
from pathlib import Path

import pytest


class TestMainContractIdentification:
    """Tests for main contract identification logic."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create a SQLite DB with required tables."""
        self.db_path = _create_main_contract_db()
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

    def _seed_data(self):
        """Seed contract and daily_quotes data."""
        # Products
        self.conn.execute(
            "INSERT INTO product_config (exchange_code, product_code, product_name) VALUES (?, ?, ?)",
            ('CFFEX', 'IM', '中证1000期货')
        )
        self.conn.execute(
            "INSERT INTO product_config (exchange_code, product_code, product_name) VALUES (?, ?, ?)",
            ('CFFEX', 'IF', '沪深300期货')
        )

        # Contracts: IM2601, IM2602, IM2603, IM2606
        for code in ['IM2601', 'IM2602', 'IM2603', 'IM2606']:
            self.conn.execute(
                "INSERT INTO contract_info (contract_code, exchange_code, product_code, contract_type, listing_date, last_trade_date) VALUES (?, ?, ?, 'futures', '2025-01-01', ?)",
                (code, 'CFFEX', 'IM', f'2026-{code[4:6]}-20')
            )

        # daily_quotes: IM2603 has highest open_interest on 2026-01-15
        self.conn.execute(
            "INSERT INTO daily_quotes (exchange, contract_code, trade_date, close, volume, open_interest) VALUES (?, ?, ?, ?, ?, ?)",
            ('CFFEX', 'IM2601', '2026-01-15', 6000, 50000, 30000)
        )
        self.conn.execute(
            "INSERT INTO daily_quotes (exchange, contract_code, trade_date, close, volume, open_interest) VALUES (?, ?, ?, ?, ?, ?)",
            ('CFFEX', 'IM2603', '2026-01-15', 6010, 80000, 60000)  # Main
        )
        self.conn.execute(
            "INSERT INTO daily_quotes (exchange, contract_code, trade_date, close, volume, open_interest) VALUES (?, ?, ?, ?, ?, ?)",
            ('CFFEX', 'IM2606', '2026-01-15', 6020, 20000, 15000)
        )
        self.conn.commit()

    def test_get_main_contract_by_open_interest(self):
        """Main contract is determined by highest open_interest."""
        from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
        self._seed_data()

        svc = MainContractService(db_path=str(self.db_path))
        main = svc.get_main_contract('IM', date(2026, 1, 15))

        assert main == 'IM2603'

    def test_get_main_contract_fallback_to_volume(self):
        """When open_interest data is missing, fallback to volume."""
        from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
        self._seed_data()

        svc = MainContractService(db_path=str(self.db_path))

        # Remove open_interest data, rely on volume only
        with svc._pool.transaction() as conn:
            conn.execute("UPDATE daily_quotes SET open_interest = NULL")
            conn.execute("UPDATE daily_quotes SET volume = 50000 WHERE contract_code = 'IM2601'")
            conn.execute("UPDATE daily_quotes SET volume = 80000 WHERE contract_code = 'IM2603'")
            conn.execute("UPDATE daily_quotes SET volume = 20000 WHERE contract_code = 'IM2606'")

        main = svc.get_main_contract('IM', date(2026, 1, 15))
        # IM2603 has highest volume
        assert main == 'IM2603'

    def test_get_main_contract_no_data_returns_none(self):
        """Returns None when no quote data exists for the date."""
        from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
        self._seed_data()

        svc = MainContractService(db_path=str(self.db_path))
        main = svc.get_main_contract('IM', date(2030, 1, 1))

        assert main is None

    def test_set_main_contract_manually(self):
        """Can manually set main contract mapping."""
        from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
        svc = MainContractService(db_path=str(self.db_path))

        svc.set_main_contract('IF', date(2026, 3, 1), 'IF2603')
        svc.set_main_contract('IF', date(2026, 3, 2), 'IF2603')
        svc.set_main_contract('IF', date(2026, 3, 3), 'IF2606')  # rollover

        main = svc.get_main_contract('IF', date(2026, 3, 1))
        assert main == 'IF2603'

        main = svc.get_main_contract('IF', date(2026, 3, 3))
        assert main == 'IF2606'

    def test_get_main_contract_series(self):
        """Get main contract series for a date range."""
        from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
        svc = MainContractService(db_path=str(self.db_path))

        svc.set_main_contract('IM', date(2026, 1, 1), 'IM2601')
        svc.set_main_contract('IM', date(2026, 2, 1), 'IM2602')
        svc.set_main_contract('IM', date(2026, 3, 1), 'IM2603')

        series = svc.get_main_series('IM', date(2026, 1, 1), date(2026, 3, 31))

        assert len(series) == 3
        assert series[0]['contract_code'] == 'IM2601'
        assert series[1]['contract_code'] == 'IM2602'
        assert series[2]['contract_code'] == 'IM2603'

    def test_get_rollover_dates(self):
        """Identify dates when main contract changes."""
        from tzdata_pkg.maintenance.metadata.main_contract import MainContractService
        svc = MainContractService(db_path=str(self.db_path))

        svc.set_main_contract('IM', date(2026, 1, 15), 'IM2601')
        svc.set_main_contract('IM', date(2026, 1, 16), 'IM2601')
        svc.set_main_contract('IM', date(2026, 1, 17), 'IM2602')  # rollover
        svc.set_main_contract('IM', date(2026, 1, 18), 'IM2602')

        rollovers = svc.get_rollover_dates('IM', date(2026, 1, 15), date(2026, 1, 18))

        assert len(rollovers) == 1
        assert rollovers[0]['date'] == '2026-01-17'
        assert rollovers[0]['from_contract'] == 'IM2601'
        assert rollovers[0]['to_contract'] == 'IM2602'


def _create_main_contract_db() -> Path:
    """Create a SQLite DB with required tables."""
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
                listing_date TEXT,
                last_trade_date TEXT,
                status TEXT DEFAULT 'active'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                contract_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                close REAL,
                volume INTEGER,
                open_interest INTEGER,
                UNIQUE(exchange, contract_code, trade_date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS main_contract_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                contract_code TEXT NOT NULL,
                method TEXT DEFAULT 'manual',  -- volume_oi, rule, manual
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_code, trade_date)
            )
        """)
        conn.commit()
    finally:
        conn.close()

    return db_path
