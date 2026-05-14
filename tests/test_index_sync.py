"""TDD tests for index daily sync task.

Tests:
- CRUD operations on daily_index_prices table
- INSERT OR REPLACE idempotency
- Date range queries
- Multiple index codes (000852, 000300)
"""
import sqlite3
import pytest


class TestIndexPricesCRUD:
    """CRUD operations on daily_index_prices table."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE daily_index_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                open DECIMAL(20,4),
                high DECIMAL(20,4),
                low DECIMAL(20,4),
                close DECIMAL(20,4),
                volume BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(index_code, trade_date)
            );
        """)
        yield
        self.conn.close()

    def _insert_price(self, code="000852", date="2026-05-14",
                      open=5800.0, high=5850.0, low=5780.0, close=5830.0, volume=1000000):
        self.conn.execute(
            """INSERT OR REPLACE INTO daily_index_prices
               (index_code, trade_date, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (code, date, open, high, low, close, volume)
        )

    def test_insert_zz1000(self):
        """Insert 000852 (中证1000) daily price."""
        self._insert_price()
        row = self.conn.execute(
            "SELECT * FROM daily_index_prices WHERE index_code = '000852'"
        ).fetchone()
        assert row is not None
        assert row[1] == "000852"
        assert abs(row[6] - 5830.0) < 0.0001  # close

    def test_insert_hs300(self):
        """Insert 000300 (沪深300) daily price."""
        self._insert_price(code="000300", close=3900.0)
        row = self.conn.execute(
            "SELECT * FROM daily_index_prices WHERE index_code = '000300'"
        ).fetchone()
        assert row is not None
        assert abs(row[6] - 3900.0) < 0.0001

    def test_upsert_idempotency(self):
        """INSERT OR REPLACE should update existing row, not duplicate."""
        self._insert_price(close=5830.0)
        self._insert_price(close=5850.0)  # same code+date
        count = self.conn.execute(
            "SELECT COUNT(*) FROM daily_index_prices WHERE index_code = '000852'"
        ).fetchone()[0]
        assert count == 1
        close = self.conn.execute(
            "SELECT close FROM daily_index_prices WHERE index_code = '000852' AND trade_date = '2026-05-14'"
        ).fetchone()[0]
        assert abs(close - 5850.0) < 0.0001

    def test_ohlc_data_integrity(self):
        """All OHLCV fields stored correctly."""
        self._insert_price(open=5800.0, high=5850.0, low=5780.0, close=5830.0, volume=1234567)
        row = self.conn.execute(
            "SELECT * FROM daily_index_prices LIMIT 1"
        ).fetchone()
        assert abs(row[3] - 5800.0) < 0.0001   # open
        assert abs(row[4] - 5850.0) < 0.0001   # high
        assert abs(row[5] - 5780.0) < 0.0001   # low
        assert abs(row[6] - 5830.0) < 0.0001   # close
        assert row[7] == 1234567               # volume

    def test_query_by_date_range(self):
        """Query prices within date range."""
        dates = ["2026-05-10", "2026-05-12", "2026-05-15", "2026-05-20"]
        for d in dates:
            self._insert_price(date=d)
        rows = self.conn.execute(
            """SELECT * FROM daily_index_prices
               WHERE index_code = '000852' AND trade_date >= ? AND trade_date <= ?
               ORDER BY trade_date""",
            ("2026-05-11", "2026-05-18")
        ).fetchall()
        assert len(rows) == 2
        assert rows[0][2] == "2026-05-12"
        assert rows[1][2] == "2026-05-15"

    def test_query_by_index_code(self):
        """Query prices by specific index code."""
        self._insert_price(code="000852", date="2026-05-14")
        self._insert_price(code="000300", date="2026-05-14")
        rows = self.conn.execute(
            "SELECT * FROM daily_index_prices WHERE index_code = '000300'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "000300"

    def test_multiple_dates_same_code(self):
        """Multiple dates for same index code."""
        for i in range(10):
            self._insert_price(date=f"2026-05-{i+1:02d}")
        rows = self.conn.execute(
            "SELECT * FROM daily_index_prices WHERE index_code = '000852' ORDER BY trade_date"
        ).fetchall()
        assert len(rows) == 10

    def test_multiple_codes_same_date(self):
        """Multiple index codes on same date."""
        self._insert_price(code="000852", date="2026-05-14", close=5830.0)
        self._insert_price(code="000300", date="2026-05-14", close=3900.0)
        rows = self.conn.execute(
            "SELECT * FROM daily_index_prices WHERE trade_date = '2026-05-14'"
        ).fetchall()
        assert len(rows) == 2
        closes = {r[1]: r[6] for r in rows}
        assert abs(closes["000852"] - 5830.0) < 0.0001
        assert abs(closes["000300"] - 3900.0) < 0.0001

    def test_unique_constraint(self):
        """UNIQUE(index_code, trade_date) constraint enforced."""
        self._insert_price()
        with pytest.raises(sqlite3.IntegrityError):
            self.conn.execute(
                """INSERT INTO daily_index_prices
                   (index_code, trade_date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("000852", "2026-05-14", 5800.0, 5850.0, 5780.0, 5830.0, 1000000)
            )

    def test_delete_price(self):
        """Delete a price record."""
        self._insert_price()
        self.conn.execute(
            "DELETE FROM daily_index_prices WHERE index_code = '000852'"
        )
        count = self.conn.execute(
            "SELECT COUNT(*) FROM daily_index_prices"
        ).fetchone()[0]
        assert count == 0

    def test_close_higher_than_open(self):
        """Verify price relationship: close > open (up day)."""
        self._insert_price(open=5800.0, close=5850.0)
        row = self.conn.execute(
            "SELECT open, close FROM daily_index_prices LIMIT 1"
        ).fetchone()
        assert row[1] > row[0]

    def test_close_lower_than_open(self):
        """Verify price relationship: close < open (down day)."""
        self._insert_price(open=5800.0, close=5750.0)
        row = self.conn.execute(
            "SELECT open, close FROM daily_index_prices LIMIT 1"
        ).fetchone()
        assert row[1] < row[0]
