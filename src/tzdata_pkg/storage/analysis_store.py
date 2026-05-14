"""
Analysis data store: institution features, signals, Tushare data.
Provides CRUD operations for tzdata_analysis.db tables.
"""
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry


class AnalysisStore:
    """CRUD operations for analysis data."""

    def __init__(self, registry: DBRegistry):
        self.registry = registry

    # ── Institution Features ────────────────────────────────

    def get_institution_features(
        self,
        member_name: Optional[str] = None,
        trade_date: Optional[str] = None,
    ) -> list[dict]:
        """Query institution daily features."""
        clauses = []
        params: list = []
        if member_name:
            clauses.append("member_name = ?")
            params.append(member_name)
        if trade_date:
            clauses.append("trade_date = ?")
            params.append(trade_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM institution_daily_features WHERE {where} ORDER BY trade_date DESC"

        pool = self.registry.get_pool("analysis")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Signals ─────────────────────────────────────────────

    def get_signals(
        self,
        signal_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """Query trading signals."""
        clauses = []
        params: list = []
        if signal_type:
            clauses.append("signal_type = ?")
            params.append(signal_type)
        if start_date:
            clauses.append("signal_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("signal_date <= ?")
            params.append(end_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM trading_signals WHERE {where} ORDER BY signal_date DESC"

        pool = self.registry.get_pool("analysis")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Market Regime ───────────────────────────────────────

    def get_market_regime(self, trade_date: Optional[str] = None) -> list[dict]:
        """Query market regime classification."""
        clauses = []
        params: list = []
        if trade_date:
            clauses.append("trade_date = ?")
            params.append(trade_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM market_regime WHERE {where} ORDER BY trade_date DESC"

        pool = self.registry.get_pool("analysis")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Tushare Data ────────────────────────────────────────

    def get_tushare_daily(
        self,
        ts_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """Query Tushare daily data."""
        clauses = []
        params: list = []
        if ts_code:
            clauses.append("ts_code = ?")
            params.append(ts_code)
        if start_date:
            clauses.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("trade_date <= ?")
            params.append(end_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM tushare_daily WHERE {where} ORDER BY trade_date"

        pool = self.registry.get_pool("analysis")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
