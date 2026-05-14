"""TDD tests for contract sync from Tushare."""

import sqlite3
import tempfile
import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


class TestContractSync:
    """Tests for syncing contracts from Tushare opt_basic/fut_basic."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create a SQLite DB with contract/product schema."""
        self.db_path = _create_contract_db()
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
        return pd.DataFrame(rows)

    def test_sync_futures_inserts_contracts(self):
        """Sync futures inserts new contracts into contract_info."""
        from tzdata_pkg.cli.import_contracts import ContractSyncService

        mock_df = self._make_mock_df([
            {'ts_code': 'IM2606.CFFEX', 'symbol': 'IM2606', 'exchange': 'CFFEX',
             'contract_type': 'FUT', 'list_date': '20250616', 'delist_date': '20260619'},
            {'ts_code': 'IF2606.CFFEX', 'symbol': 'IF2606', 'exchange': 'CFFEX',
             'contract_type': 'FUT', 'list_date': '20250616', 'delist_date': '20260619'},
        ])

        svc = ContractSyncService(db_path=str(self.db_path))
        svc._fetch_futures = MagicMock(return_value=mock_df)
        result = svc.sync_futures(exchange='CFFEX')

        assert result['inserted'] == 2

        row = self.conn.execute("SELECT contract_code FROM contract_info WHERE contract_code='IM2606'").fetchone()
        assert row is not None

    def test_sync_futures_incremental(self):
        """Sync skips already-existing contracts."""
        from tzdata_pkg.cli.import_contracts import ContractSyncService

        # Pre-seed one contract
        self.conn.execute(
            "INSERT INTO contract_info (contract_code, exchange_code, product_code) VALUES (?, ?, ?)",
            ('IM2606', 'CFFEX', 'IM')
        )
        self.conn.commit()

        mock_df = self._make_mock_df([
            {'ts_code': 'IM2606.CFFEX', 'symbol': 'IM2606', 'exchange': 'CFFEX',
             'contract_type': 'FUT', 'list_date': '20250616', 'delist_date': '20260619'},
            {'ts_code': 'IC2606.CFFEX', 'symbol': 'IC2606', 'exchange': 'CFFEX',
             'contract_type': 'FUT', 'list_date': '20250616', 'delist_date': '20260619'},
        ])

        svc = ContractSyncService(db_path=str(self.db_path))
        svc._fetch_futures = MagicMock(return_value=mock_df)
        result = svc.sync_futures(exchange='CFFEX')

        assert result['inserted'] == 1  # Only IC2606 is new

    def test_sync_options_inserts_contracts(self):
        """Sync options from opt_basic inserts new contracts."""
        from tzdata_pkg.cli.import_contracts import ContractSyncService

        mock_df = self._make_mock_df([
            {'ts_code': 'MO2606-C-5500.CFFEX', 'symbol': 'MO2606-C-5500', 'exchange': 'CFFEX',
             'call_put': 'C', 'strike_price': 5500.0, 'list_date': '20250624', 'delist_date': '20260619'},
            {'ts_code': 'MO2606-P-5500.CFFEX', 'symbol': 'MO2606-P-5500', 'exchange': 'CFFEX',
             'call_put': 'P', 'strike_price': 5500.0, 'list_date': '20250624', 'delist_date': '20260619'},
        ])

        svc = ContractSyncService(db_path=str(self.db_path))
        svc._fetch_options = MagicMock(return_value=mock_df)
        result = svc.sync_options(exchange='CFFEX')

        assert result['inserted'] == 2

        row = self.conn.execute("SELECT contract_code, contract_type, strike_price FROM contract_info WHERE contract_code='MO2606-C-5500'").fetchone()
        assert row is not None
        assert row[1] == 'option_call'
        assert row[2] == 5500.0

    def test_mark_expired_contracts(self):
        """Contracts with last_trade_date <= today are marked as expired."""
        from tzdata_pkg.cli.import_contracts import ContractSyncService

        self.conn.execute(
            "INSERT INTO contract_info (contract_code, exchange_code, last_trade_date, status) VALUES (?, ?, ?, ?)",
            ('IM2506', 'CFFEX', '2025-06-20', 'active')
        )
        self.conn.execute(
            "INSERT INTO contract_info (contract_code, exchange_code, last_trade_date, status) VALUES (?, ?, ?, ?)",
            ('IM2606', 'CFFEX', '2026-06-19', 'active')
        )
        self.conn.commit()

        svc = ContractSyncService(db_path=str(self.db_path))
        result = svc.mark_expired(reference_date=date(2026, 1, 1))

        assert result['expired'] == 1

        status = self.conn.execute("SELECT status FROM contract_info WHERE contract_code='IM2506'").fetchone()
        assert status[0] == 'expired'

        status2 = self.conn.execute("SELECT status FROM contract_info WHERE contract_code='IM2606'").fetchone()
        assert status2[0] == 'active'

    def test_get_expiring_contracts(self):
        """Query contracts expiring within N days."""
        from tzdata_pkg.cli.import_contracts import ContractSyncService

        self.conn.execute(
            "INSERT INTO contract_info (contract_code, exchange_code, last_trade_date, status) VALUES (?, ?, ?, ?)",
            ('IM2601', 'CFFEX', '2026-01-16', 'active')
        )
        self.conn.execute(
            "INSERT INTO contract_info (contract_code, exchange_code, last_trade_date, status) VALUES (?, ?, ?, ?)",
            ('IM2606', 'CFFEX', '2026-06-19', 'active')
        )
        self.conn.commit()

        svc = ContractSyncService(db_path=str(self.db_path))
        result = svc.get_expiring(reference_date=date(2026, 1, 1), days_ahead=30)

        assert len(result) == 1
        assert result[0]['contract_code'] == 'IM2601'

    def test_sync_empty_response(self):
        """Sync handles empty Tushare response gracefully."""
        from tzdata_pkg.cli.import_contracts import ContractSyncService

        svc = ContractSyncService(db_path=str(self.db_path))
        svc._fetch_futures = MagicMock(return_value=None)
        result = svc.sync_futures(exchange='CFFEX')

        assert result['inserted'] == 0


def _create_contract_db() -> Path:
    """Create a SQLite DB with contract_info and product_config tables."""
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
                multiplier REAL,
                price_tick REAL,
                margin_rate REAL,
                option_style TEXT,
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
                last_trade_date TEXT,
                delivery_date TEXT,
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
