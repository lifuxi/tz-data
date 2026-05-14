"""
Market data store: quotes, positions, contracts.
Provides CRUD operations for tzdata_market.db tables.
"""
from datetime import date
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry


class MarketStore:
    """CRUD operations for market data."""

    def __init__(self, registry: DBRegistry):
        self.registry = registry

    # ── Quotes ──────────────────────────────────────────────

    def get_quotes(
        self,
        exchange: Optional[str] = None,
        contract: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: str = "daily",
    ) -> list[dict]:
        """Query daily or minute quotes."""
        if frequency == "daily":
            return self._query_daily(exchange, contract, start_date, end_date)
        return self._query_minute(exchange, contract, start_date, end_date)

    def _query_daily(self, exchange, contract, start_date, end_date) -> list[dict]:
        clauses = []
        params: list = []
        if exchange:
            clauses.append("exchange = ?")
            params.append(exchange)
        if contract:
            clauses.append("contract_code = ?")
            params.append(contract)
        if start_date:
            clauses.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM daily_quotes WHERE {where} ORDER BY trade_date, contract_code"

        pool = self.registry.get_pool("market")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def _query_minute(self, exchange, contract, start_date, end_date) -> list[dict]:
        clauses = []
        params: list = []
        if exchange:
            clauses.append("exchange = ?")
            params.append(exchange)
        if contract:
            clauses.append("contract_code = ?")
            params.append(contract)
        if start_date:
            clauses.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM minute_quotes WHERE {where} ORDER BY trade_date, trade_time"

        pool = self.registry.get_pool("market")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Positions ───────────────────────────────────────────

    def get_positions(
        self,
        exchange: Optional[str] = None,
        contract: Optional[str] = None,
        trade_date: Optional[str] = None,
    ) -> list[dict]:
        """Query position ranking data."""
        clauses = []
        params: list = []
        if exchange:
            clauses.append("exchange = ?")
            params.append(exchange)
        if contract:
            clauses.append("contract_code = ?")
            params.append(contract)
        if trade_date:
            clauses.append("trade_date = ?")
            params.append(trade_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM position_detail WHERE {where} ORDER BY trade_date DESC, long_volume DESC"

        pool = self.registry.get_pool("market")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Contracts ───────────────────────────────────────────

    def list_contracts(
        self,
        exchange: Optional[str] = None,
        variety: Optional[str] = None,
        contract_type: Optional[str] = None,
    ) -> list[dict]:
        """List available contracts."""
        clauses = []
        params: list = []
        if exchange:
            clauses.append("exchange = ?")
            params.append(exchange)
        if variety:
            clauses.append("variety = ?")
            params.append(variety)
        if contract_type:
            clauses.append("contract_type = ?")
            params.append(contract_type)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM contracts WHERE {where} ORDER BY contract_code"

        pool = self.registry.get_pool("market")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def save_quotes(self, rows: list[dict]) -> int:
        """Insert or replace daily quotes. Returns count."""
        if not rows:
            return 0
        pool = self.registry.get_pool("market")
        count = 0
        with pool.transaction() as conn:
            for r in rows:
                conn.execute("""
                    INSERT INTO daily_quotes
                        (exchange, contract_code, trade_date, open, high, low, close,
                         settle, prev_settle, volume, turnover, open_interest)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(exchange, contract_code, trade_date)
                    DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, settle=excluded.settle,
                        volume=excluded.volume, turnover=excluded.turnover,
                        open_interest=excluded.open_interest
                """, (
                    r["exchange"], r["contract_code"], r["trade_date"],
                    r.get("open"), r.get("high"), r.get("low"), r.get("close"),
                    r.get("settle"), r.get("prev_settle"),
                    r.get("volume", 0), r.get("turnover", 0),
                    r.get("open_interest", 0),
                ))
                count += 1
        return count
