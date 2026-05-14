"""TDD tests for contract expiry data.

Tests:
- CRUD operations on contract_expiry table
- UNIQUE(symbol) constraint
- Query by symbol, expiry_date, exchange
- Date parsing and expiry detection
"""
import sqlite3
import pytest


class TestContractExpiryCRUD:
    """CRUD operations on contract_expiry table."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE contract_expiry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                exchange TEXT NOT NULL,
                product_type TEXT,
                expiry_date TEXT NOT NULL,
                underlying_symbol TEXT,
                strike_price DECIMAL(20,4),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        yield
        self.conn.close()

    def _insert_contract(self, symbol="MO2603-C-8500", exchange="CFFEX",
                         product_type="option", expiry_date="2026-03-20",
                         underlying="MO", strike=8500.0):
        self.conn.execute(
            """INSERT INTO contract_expiry
               (symbol, exchange, product_type, expiry_date, underlying_symbol, strike_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (symbol, exchange, product_type, expiry_date, underlying, strike)
        )

    def test_insert_option_contract(self):
        """Insert an option contract with full details."""
        self._insert_contract()
        row = self.conn.execute(
            "SELECT * FROM contract_expiry WHERE symbol = 'MO2603-C-8500'"
        ).fetchone()
        assert row is not None
        assert row[1] == "MO2603-C-8500"
        assert row[2] == "CFFEX"
        assert row[3] == "option"
        assert row[4] == "2026-03-20"
        assert abs(row[6] - 8500.0) < 0.0001

    def test_insert_future_contract(self):
        """Insert a future contract (no strike price)."""
        self._insert_contract(
            symbol="IM2606", product_type="future",
            expiry_date="2026-06-19", underlying="IM", strike=0.0
        )
        row = self.conn.execute(
            "SELECT * FROM contract_expiry WHERE symbol = 'IM2606'"
        ).fetchone()
        assert row is not None
        assert row[3] == "future"
        assert row[6] == 0.0

    def test_unique_symbol_constraint(self):
        """UNIQUE(symbol) constraint enforced."""
        self._insert_contract()
        with pytest.raises(sqlite3.IntegrityError):
            self._insert_contract()

    def test_query_by_symbol(self):
        """Query by exact symbol."""
        self._insert_contract()
        row = self.conn.execute(
            "SELECT * FROM contract_expiry WHERE symbol = ?",
            ("MO2603-C-8500",)
        ).fetchone()
        assert row[2] == "CFFEX"

    def test_query_by_exchange(self):
        """Query all contracts from an exchange."""
        self._insert_contract(symbol="MO2603-C-8500", exchange="CFFEX")
        self._insert_contract(symbol="IO2603-C-3800", exchange="CFFEX")
        self._insert_contract(symbol="CU2603", exchange="SHFE")
        rows = self.conn.execute(
            "SELECT symbol FROM contract_expiry WHERE exchange = 'CFFEX'"
        ).fetchall()
        assert len(rows) == 2
        assert {r[0] for r in rows} == {"MO2603-C-8500", "IO2603-C-3800"}

    def test_query_by_expiry_date(self):
        """Query contracts expiring on a specific date."""
        self._insert_contract(symbol="MO2603-C-8500", expiry_date="2026-03-20")
        self._insert_contract(symbol="MO2603-P-8500", expiry_date="2026-03-20")
        self._insert_contract(symbol="MO2606-C-8500", expiry_date="2026-06-19")
        rows = self.conn.execute(
            "SELECT symbol FROM contract_expiry WHERE expiry_date = '2026-03-20'"
        ).fetchall()
        assert len(rows) == 2

    def test_query_expiring_soon(self):
        """Query contracts expiring within a date range."""
        self._insert_contract(symbol="MO2603-C-8500", expiry_date="2026-03-20")
        self._insert_contract(symbol="MO2604-C-8500", expiry_date="2026-04-17")
        self._insert_contract(symbol="MO2606-C-8500", expiry_date="2026-06-19")
        rows = self.conn.execute(
            """SELECT symbol FROM contract_expiry
               WHERE expiry_date >= ? AND expiry_date <= ?
               ORDER BY expiry_date""",
            ("2026-03-01", "2026-04-30")
        ).fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "MO2603-C-8500"
        assert rows[1][0] == "MO2604-C-8500"

    def test_query_by_underlying(self):
        """Query all options on same underlying."""
        self._insert_contract(symbol="MO2603-C-8500", underlying="MO")
        self._insert_contract(symbol="MO2603-P-8500", underlying="MO")
        self._insert_contract(symbol="IO2603-C-3800", underlying="IO")
        rows = self.conn.execute(
            "SELECT symbol FROM contract_expiry WHERE underlying_symbol = 'MO'"
        ).fetchall()
        assert len(rows) == 2

    def test_query_by_strike_range(self):
        """Query options within strike price range."""
        self._insert_contract(symbol="MO2603-C-8000", strike=8000.0)
        self._insert_contract(symbol="MO2603-C-8500", strike=8500.0)
        self._insert_contract(symbol="MO2603-C-9000", strike=9000.0)
        rows = self.conn.execute(
            """SELECT symbol FROM contract_expiry
               WHERE strike_price >= ? AND strike_price <= ?
               ORDER BY strike_price""",
            (8200.0, 8800.0)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "MO2603-C-8500"

    def test_update_expiry_date(self):
        """Update contract expiry date."""
        self._insert_contract(expiry_date="2026-03-20")
        self.conn.execute(
            "UPDATE contract_expiry SET expiry_date = ? WHERE symbol = ?",
            ("2026-03-21", "MO2603-C-8500")
        )
        row = self.conn.execute(
            "SELECT expiry_date FROM contract_expiry WHERE symbol = 'MO2603-C-8500'"
        ).fetchone()
        assert row[0] == "2026-03-21"

    def test_delete_contract(self):
        """Delete a contract record."""
        self._insert_contract()
        self.conn.execute(
            "DELETE FROM contract_expiry WHERE symbol = 'MO2603-C-8500'"
        )
        count = self.conn.execute(
            "SELECT COUNT(*) FROM contract_expiry"
        ).fetchone()[0]
        assert count == 0

    def test_multiple_exchanges(self):
        """Contracts from different exchanges coexist."""
        exchanges = [("CU2603", "SHFE"), ("M2603", "DCE"), ("CF2603", "CZCE"), ("MO2603", "CFFEX")]
        for sym, ex in exchanges:
            self._insert_contract(symbol=sym, exchange=ex, product_type="future",
                                  expiry_date="2026-03-20", underlying=sym[:2], strike=0.0)
        rows = self.conn.execute("SELECT symbol, exchange FROM contract_expiry ORDER BY symbol").fetchall()
        assert len(rows) == 4
        assert {(r[0], r[1]) for r in rows} == set(exchanges)
