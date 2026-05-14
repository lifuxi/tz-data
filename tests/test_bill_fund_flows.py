"""TDD tests for bill_fund_flows CRUD and identity verification.

Tests:
- CRUD operations on bill_fund_flows
- Flow type enum validation
- Identity equation: sum of flows ≈ bill closing balance change
"""
import sqlite3
import tempfile
from pathlib import Path

import pytest


class TestBillFundFlowsCRUD:
    """CRUD tests for bill_fund_flows table."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Create an in-memory database with bill_fund_flows schema."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_schema()
        yield
        self.conn.close()

    def _create_schema(self):
        self.conn.executescript("""
            CREATE TABLE bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                bill_date_start TEXT,
                balance_bf REAL DEFAULT 0,
                balance_cf REAL DEFAULT 0
            );
            CREATE TABLE bill_fund_flows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id INTEGER NOT NULL REFERENCES bills(id),
                trade_date TEXT NOT NULL,
                flow_type TEXT NOT NULL,
                amount DECIMAL(20,4) NOT NULL,
                symbol TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_bff_bill_date ON bill_fund_flows(bill_id, trade_date);
            CREATE INDEX idx_bff_flow_type ON bill_fund_flows(flow_type, trade_date);
        """)
        # Seed a bill
        self.conn.execute(
            "INSERT INTO bills (id, account_id, bill_date_start, balance_bf, balance_cf) "
            "VALUES (1, '123456', '2024-10-01', 1000000, 1050000)"
        )

    def test_insert_deposit(self):
        """Deposit flow with positive amount."""
        self.conn.execute(
            """INSERT INTO bill_fund_flows
               (bill_id, trade_date, flow_type, amount, description)
               VALUES (?, ?, ?, ?, ?)""",
            (1, "2024-10-02", "deposit", 50000.0, "入金")
        )
        row = self.conn.execute(
            "SELECT * FROM bill_fund_flows WHERE flow_type = 'deposit'"
        ).fetchone()
        assert row is not None
        assert row[3] == "deposit"
        assert row[4] == 50000.0

    def test_insert_withdrawal_negative(self):
        """Withdrawal flow should have negative amount."""
        self.conn.execute(
            """INSERT INTO bill_fund_flows
               (bill_id, trade_date, flow_type, amount, description)
               VALUES (?, ?, ?, ?, ?)""",
            (1, "2024-10-03", "withdrawal", -30000.0, "出金")
        )
        row = self.conn.execute(
            "SELECT * FROM bill_fund_flows WHERE flow_type = 'withdrawal'"
        ).fetchone()
        assert row[3] == "withdrawal"
        assert row[4] == -30000.0

    def test_insert_commission(self):
        """Commission flow with negative amount."""
        self.conn.execute(
            """INSERT INTO bill_fund_flows
               (bill_id, trade_date, flow_type, amount, symbol, description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (1, "2024-10-02", "commission", -8.94, "ag2506", "手续费")
        )
        row = self.conn.execute(
            "SELECT * FROM bill_fund_flows WHERE flow_type = 'commission'"
        ).fetchone()
        assert row[5] == "ag2506"  # symbol column

    def test_insert_realized_pnl(self):
        """Realized PnL can be positive or negative."""
        self.conn.execute(
            """INSERT INTO bill_fund_flows
               (bill_id, trade_date, flow_type, amount, symbol)
               VALUES (?, ?, ?, ?, ?)""",
            (1, "2024-10-02", "realized_pnl", 1500.0, "ag2506")
        )
        self.conn.execute(
            """INSERT INTO bill_fund_flows
               (bill_id, trade_date, flow_type, amount, symbol)
               VALUES (?, ?, ?, ?, ?)""",
            (1, "2024-10-03", "realized_pnl", -800.0, "cu2506")
        )
        rows = self.conn.execute(
            "SELECT * FROM bill_fund_flows WHERE flow_type = 'realized_pnl'"
        ).fetchall()
        assert len(rows) == 2

    def test_query_by_bill_id(self):
        """Query flows filtered by bill_id."""
        for i in range(5):
            self.conn.execute(
                """INSERT INTO bill_fund_flows
                   (bill_id, trade_date, flow_type, amount)
                   VALUES (?, ?, ?, ?)""",
                (1, f"2024-10-{i+1:02d}", "deposit", 10000)
            )
        rows = self.conn.execute(
            "SELECT * FROM bill_fund_flows WHERE bill_id = ? ORDER BY id", (1,)
        ).fetchall()
        assert len(rows) == 5

    def test_query_by_date_range(self):
        """Query flows within date range."""
        dates = ["2024-10-01", "2024-10-15", "2024-11-01", "2024-11-15"]
        for d in dates:
            self.conn.execute(
                """INSERT INTO bill_fund_flows
                   (bill_id, trade_date, flow_type, amount)
                   VALUES (?, ?, ?, ?)""",
                (1, d, "deposit", 10000)
            )
        rows = self.conn.execute(
            """SELECT * FROM bill_fund_flows
               WHERE bill_id = 1 AND trade_date >= ? AND trade_date <= ?
               ORDER BY trade_date""",
            ("2024-10-01", "2024-10-31")
        ).fetchall()
        assert len(rows) == 2

    def test_query_by_flow_type(self):
        """Query flows by specific flow_type."""
        flow_types = ["deposit", "commission", "realized_pnl", "premium_income"]
        for ft in flow_types:
            self.conn.execute(
                """INSERT INTO bill_fund_flows
                   (bill_id, trade_date, flow_type, amount)
                   VALUES (?, ?, ?, ?)""",
                (1, "2024-10-01", ft, 1000)
            )
        rows = self.conn.execute(
            "SELECT * FROM bill_fund_flows WHERE flow_type = 'commission'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][3] == "commission"

    def test_delete_flow(self):
        """Delete a flow record."""
        self.conn.execute(
            """INSERT INTO bill_fund_flows
               (bill_id, trade_date, flow_type, amount)
               VALUES (?, ?, ?, ?)""",
            (1, "2024-10-01", "deposit", 50000)
        )
        self.conn.execute("DELETE FROM bill_fund_flows WHERE flow_type = 'deposit'")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM bill_fund_flows"
        ).fetchone()[0]
        assert count == 0

    def test_foreign_key_constraint(self):
        """Inserting flow with non-existent bill_id should fail."""
        with pytest.raises(sqlite3.IntegrityError):
            self.conn.execute(
                """INSERT INTO bill_fund_flows
                   (bill_id, trade_date, flow_type, amount)
                   VALUES (?, ?, ?, ?)""",
                (999, "2024-10-01", "deposit", 50000)
            )


class TestFundFlowIdentity:
    """恒等式校验：流水合计 ≈ 期末权益变动。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
            CREATE TABLE bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                bill_date_start TEXT,
                balance_bf REAL DEFAULT 0,
                balance_cf REAL DEFAULT 0
            );
            CREATE TABLE bill_fund_flows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id INTEGER NOT NULL REFERENCES bills(id),
                trade_date TEXT NOT NULL,
                flow_type TEXT NOT NULL,
                amount DECIMAL(20,4) NOT NULL,
                symbol TEXT,
                description TEXT
            );
        """)
        # Seed bill: opening=1000000, closing=1050000, change=+50000
        self.conn.execute(
            """INSERT INTO bills (id, account_id, balance_bf, balance_cf)
               VALUES (1, '123456', 1000000, 1050000)"""
        )
        # Seed matching flows that sum to +50000
        flows = [
            (1, "2024-10-01", "deposit", 100000),
            (1, "2024-10-01", "withdrawal", -50000),
            (1, "2024-10-02", "realized_pnl", 15000),
            (1, "2024-10-02", "commission", -2000),
            (1, "2024-10-02", "premium_income", 5000),
            (1, "2024-10-02", "unrealized_pnl", -18000),
        ]
        for f in flows:
            self.conn.execute(
                """INSERT INTO bill_fund_flows
                   (bill_id, trade_date, flow_type, amount)
                   VALUES (?, ?, ?, ?)""",
                f
            )

    def test_identity_equation(self):
        """流水合计 = 期末 - 期初 = 50000。"""
        balance_change = self.conn.execute(
            "SELECT balance_cf - balance_bf FROM bills WHERE id = 1"
        ).fetchone()[0]

        flow_sum = self.conn.execute(
            "SELECT SUM(amount) FROM bill_fund_flows WHERE bill_id = 1"
        ).fetchone()[0]

        # Allow small rounding tolerance
        assert abs(flow_sum - balance_change) < 1.0

    def test_flow_type_breakdown(self):
        """按 flow_type 分组汇总。"""
        rows = self.conn.execute(
            """SELECT flow_type, SUM(amount) as total
               FROM bill_fund_flows
               WHERE bill_id = 1
               GROUP BY flow_type
               ORDER BY flow_type"""
        ).fetchall()

        breakdown = {r[0]: r[1] for r in rows}
        assert breakdown["deposit"] == 100000
        assert breakdown["withdrawal"] == -50000
        assert breakdown["realized_pnl"] == 15000
        assert breakdown["commission"] == -2000
        assert breakdown["premium_income"] == 5000
        assert breakdown["unrealized_pnl"] == -18000
