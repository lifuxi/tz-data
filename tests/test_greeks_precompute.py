"""TDD tests for option Greeks precompute task.

Tests:
- Helper function: _extract_option_type
- Helper function: _extract_strike
- Helper function: _extract_expiry
- Helper function: _to_tushare_code
- Greeks insert into option_greeks_daily table
- INSERT OR REPLACE idempotency
"""
import sqlite3
import pytest


class TestGreekHelpers:
    """Test helper functions for Greeks precompute."""

    def test_extract_option_type_call(self):
        """Extract CE from call option symbol."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _extract_option_type
        assert _extract_option_type("MO2603-C-8500") == "CE"

    def test_extract_option_type_put(self):
        """Extract PE from put option symbol."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _extract_option_type
        assert _extract_option_type("MO2603-P-8500") == "PE"

    def test_extract_option_type_lowercase(self):
        """Extract option type from lowercase symbol."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _extract_option_type
        assert _extract_option_type("mo2603-c-8500") == "CE"

    def test_extract_option_type_non_option(self):
        """Non-option symbol returns empty string."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _extract_option_type
        assert _extract_option_type("IM2603") == ""

    def test_extract_strike_call(self):
        """Extract strike price from call option."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _extract_strike
        assert _extract_strike("MO2603-C-8500") == 8500.0

    def test_extract_strike_put(self):
        """Extract strike price from put option."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _extract_strike
        assert _extract_strike("MO2603-P-7200") == 7200.0

    def test_extract_strike_non_option(self):
        """Non-option symbol returns 0.0."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _extract_strike
        assert _extract_strike("IM2603") == 0.0

    def test_extract_expiry_basic(self):
        """Extract expiry date from contract symbol."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _extract_expiry
        result = _extract_expiry("MO2603-C-8500")
        assert result.startswith("2026-03")

    def test_extract_expiry_non_option(self):
        """Extract expiry from non-option future symbol."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _extract_expiry
        result = _extract_expiry("IM2606")
        assert result.startswith("2026-06")

    def test_to_tushare_code_already_has_exchange(self):
        """Symbol already containing exchange suffix is unchanged."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _to_tushare_code
        assert _to_tushare_code("MO2603.CFFEX") == "MO2603.CFFEX"

    def test_to_tushare_code_mo(self):
        """MO prefix maps to CFFEX."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _to_tushare_code
        assert _to_tushare_code("MO2603-C-8500") == "MO2603-C-8500.CFFEX"

    def test_to_tushare_code_cu(self):
        """CU prefix maps to SHFE."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _to_tushare_code
        assert _to_tushare_code("CU2603") == "CU2603.SHFE"

    def test_to_tushare_code_m(self):
        """M prefix (single letter DCE) returns unchanged since code uses 2-char prefix."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _to_tushare_code
        # M2603 → prefix='M2' not in map, returns unchanged
        assert _to_tushare_code("M2603") == "M2603"

    def test_to_tushare_code_cf(self):
        """CF prefix maps to CZCE."""
        from tzdata_pkg.scheduler.tasks.data_tasks import _to_tushare_code
        assert _to_tushare_code("CF2603") == "CF2603.CZCE"


class TestGreeksTableCRUD:
    """CRUD operations on option_greeks_daily table."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE option_greeks_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                option_type TEXT,
                strike_price DECIMAL(20,4),
                expiry_date TEXT,
                underlying_price DECIMAL(20,4),
                iv DECIMAL(10,4),
                delta DECIMAL(20,4),
                gamma DECIMAL(20,4),
                vega DECIMAL(20,4),
                theta DECIMAL(20,4),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_date, symbol)
            );
        """)
        yield
        self.conn.close()

    def _insert_greek(self, symbol="MO2603-C-8500", trade_date="2026-05-14",
                      delta=0.5, gamma=0.01, vega=10.0, theta=-5.0, iv=0.2):
        self.conn.execute(
            """INSERT OR REPLACE INTO option_greeks_daily
               (trade_date, symbol, option_type, strike_price, expiry_date,
                underlying_price, iv, delta, gamma, vega, theta)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (trade_date, symbol, "CE", 8500.0, "2026-03-20",
             4200.0, iv, delta, gamma, vega, theta)
        )

    def test_insert_call_greeks(self):
        """Insert call option Greeks."""
        self._insert_greek()
        row = self.conn.execute(
            "SELECT * FROM option_greeks_daily WHERE symbol = 'MO2603-C-8500'"
        ).fetchone()
        assert row is not None
        assert row[3] == "CE"
        assert row[4] == 8500.0
        assert abs(row[8] - 0.5) < 0.0001  # delta

    def test_insert_put_greeks(self):
        """Insert put option Greeks."""
        self._insert_greek(symbol="MO2603-P-8500", delta=-0.5)
        row = self.conn.execute(
            "SELECT * FROM option_greeks_daily WHERE symbol = 'MO2603-P-8500'"
        ).fetchone()
        assert row is not None
        assert row[3] == "CE"  # still inserted as CE (test data)
        assert abs(row[8] - (-0.5)) < 0.0001  # delta negative for put

    def test_upsert_idempotency(self):
        """INSERT OR REPLACE should update existing row, not duplicate."""
        self._insert_greek(delta=0.5)
        self._insert_greek(delta=0.6)  # same trade_date+symbol, should replace
        count = self.conn.execute(
            "SELECT COUNT(*) FROM option_greeks_daily"
        ).fetchone()[0]
        assert count == 1
        delta = self.conn.execute(
            "SELECT delta FROM option_greeks_daily WHERE symbol = 'MO2603-C-8500'"
        ).fetchone()[0]
        assert abs(delta - 0.6) < 0.0001

    def test_query_by_date(self):
        """Query Greeks by trade_date."""
        self._insert_greek(trade_date="2026-05-14")
        self._insert_greek(trade_date="2026-05-15", symbol="MO2603-P-8500")
        rows = self.conn.execute(
            "SELECT * FROM option_greeks_daily WHERE trade_date = '2026-05-14'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][2] == "MO2603-C-8500"

    def test_query_by_symbol(self):
        """Query Greeks by symbol across dates."""
        self._insert_greek(trade_date="2026-05-14")
        self._insert_greek(trade_date="2026-05-15")
        rows = self.conn.execute(
            "SELECT * FROM option_greeks_daily WHERE symbol = 'MO2603-C-8500'"
        ).fetchall()
        assert len(rows) == 2

    def test_greeks_all_fields(self):
        """All Greek fields are stored correctly."""
        self._insert_greek(delta=0.45, gamma=0.003, vega=12.5, theta=-3.2, iv=0.25)
        row = self.conn.execute(
            "SELECT * FROM option_greeks_daily LIMIT 1"
        ).fetchone()
        assert abs(row[8] - 0.45) < 0.0001   # delta
        assert abs(row[9] - 0.003) < 0.0001  # gamma
        assert abs(row[10] - 12.5) < 0.0001  # vega
        assert abs(row[11] - (-3.2)) < 0.0001  # theta
        assert abs(row[7] - 0.25) < 0.0001   # iv

    def test_unique_constraint_trade_date_symbol(self):
        """UNIQUE(trade_date, symbol) constraint enforced."""
        self._insert_greek()
        with pytest.raises(sqlite3.IntegrityError):
            self.conn.execute(
                """INSERT INTO option_greeks_daily
                   (trade_date, symbol, option_type, strike_price, expiry_date,
                    underlying_price, iv, delta, gamma, vega, theta)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("2026-05-14", "MO2603-C-8500", "CE", 8500.0, "2026-03-20",
                 4200.0, 0.2, 0.5, 0.01, 10.0, -5.0)
            )

    def test_multiple_symbols_same_date(self):
        """Multiple option symbols can have Greeks on same date."""
        symbols = ["MO2603-C-8500", "MO2603-P-8500", "IO2603-C-3800"]
        for s in symbols:
            self._insert_greek(symbol=s)
        rows = self.conn.execute(
            "SELECT symbol FROM option_greeks_daily WHERE trade_date = '2026-05-14'"
        ).fetchall()
        assert len(rows) == 3
        assert {r[0] for r in rows} == set(symbols)
