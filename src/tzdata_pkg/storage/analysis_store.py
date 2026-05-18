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

    def _analysis_pool(self):
        return self.registry.get_pool("analysis")

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

        with self._analysis_pool().connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def insert_institution_features(self, features: list[dict]) -> int:
        """Batch insert institution_daily_features."""
        if not features:
            return 0
        with self._analysis_pool().connection() as conn:
            count = 0
            for f in features:
                conn.execute("""
                    INSERT INTO institution_daily_features
                        (trade_date, member_name, contract_code, exchange,
                         long_volume, short_volume, net_volume,
                         long_change, short_change, net_change,
                         member_rank_long, member_rank_short,
                         total_market_long, total_market_short,
                         member_long_pct, member_short_pct,
                         concentration_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f.get("trade_date"), f.get("member_name"), f.get("contract_code"),
                    f.get("exchange"), f.get("long_volume", 0), f.get("short_volume", 0),
                    f.get("net_volume", 0), f.get("long_change", 0), f.get("short_change", 0),
                    f.get("net_change", 0), f.get("member_rank_long"), f.get("member_rank_short"),
                    f.get("total_market_long"), f.get("total_market_short"),
                    f.get("member_long_pct"), f.get("member_short_pct"),
                    f.get("concentration_score"),
                ))
                count += 1
            return count

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

        with self._analysis_pool().connection() as conn:
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

        with self._analysis_pool().connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def insert_market_regime(self, regimes: list[dict]) -> int:
        """Batch insert market_regime records."""
        if not regimes:
            return 0
        with self._analysis_pool().connection() as conn:
            count = 0
            for r in regimes:
                conn.execute("""
                    INSERT INTO market_regime
                        (trade_date, regime_type, contract_code,
                         trend_strength, volatility_level, volume_trend,
                         iv_regime, regime_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get("trade_date"), r.get("regime_type"), r.get("contract_code"),
                    r.get("trend_strength"), r.get("volatility_level"), r.get("volume_trend"),
                    r.get("iv_regime"), r.get("regime_score"),
                ))
                count += 1
            return count

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

        with self._analysis_pool().connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Institution Master ──────────────────────────────────

    def get_institution_master(self, category: Optional[str] = None) -> list[dict]:
        """Query institution master list."""
        clauses = []
        params: list = []
        if category:
            clauses.append("category = ?")
            params.append(category)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM institution_master WHERE {where} ORDER BY member_name"

        with self._analysis_pool().connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    # ── Lead-Lag ────────────────────────────────────────────

    def get_lead_lag(self, trade_date: Optional[str] = None) -> list[dict]:
        """Query institution lead-lag relationships."""
        clauses = []
        params: list = []
        if trade_date:
            clauses.append("trade_date = ?")
            params.append(trade_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM institution_lead_lag WHERE {where} ORDER BY trade_date DESC"

        with self._analysis_pool().connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
