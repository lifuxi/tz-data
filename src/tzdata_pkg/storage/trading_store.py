"""
Trading data store: bills, trades, accounts, positions.
Provides CRUD operations for tzdata_trading.db tables.
"""
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry


class TradingStore:
    """CRUD operations for trading data."""

    def __init__(self, registry: DBRegistry):
        self.registry = registry

    # ── Bills ───────────────────────────────────────────────

    def list_bills(self, account_id: Optional[str] = None) -> list[dict]:
        """List uploaded bills."""
        clauses = []
        params: list = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM bills WHERE {where} ORDER BY bill_date_start DESC"

        pool = self.registry.get_pool("trading")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Trades ──────────────────────────────────────────────

    def list_trades(
        self,
        account_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        instrument: Optional[str] = None,
    ) -> list[dict]:
        """Query trade records."""
        clauses = []
        params: list = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if start_date:
            clauses.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("trade_date <= ?")
            params.append(end_date)
        if instrument:
            clauses.append("instrument = ?")
            params.append(instrument)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM trades WHERE {where} ORDER BY trade_date, id"

        pool = self.registry.get_pool("trading")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Matched Trades ──────────────────────────────────────

    def list_matched_trades(
        self,
        instrument: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """Query matched (open-close pair) trades."""
        clauses = []
        params: list = []
        if instrument:
            clauses.append("instrument = ?")
            params.append(instrument)
        if start_date:
            clauses.append("close_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("close_date <= ?")
            params.append(end_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM matched_trades WHERE {where} ORDER BY close_date DESC"

        pool = self.registry.get_pool("trading")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Positions ───────────────────────────────────────────

    def get_positions_summary(
        self,
        instrument: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """Query position summary."""
        clauses = []
        params: list = []
        if instrument:
            clauses.append("instrument = ?")
            params.append(instrument)
        if start_date:
            clauses.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM positions_summary WHERE {where} ORDER BY trade_date DESC, instrument"

        pool = self.registry.get_pool("trading")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Account Summary ─────────────────────────────────────

    def get_account_summary(self, account_id: Optional[str] = None) -> list[dict]:
        """Query account monthly summaries."""
        clauses = []
        params: list = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM account_summary WHERE {where} ORDER BY year, month"

        pool = self.registry.get_pool("trading")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
