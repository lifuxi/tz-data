"""Analysis data query module.

Provides user-friendly access to institution features, signals, Tushare data.
"""

from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.storage.analysis_store import AnalysisStore


class AnalysisQuery:
    """High-level analysis data queries."""

    def __init__(self, registry: DBRegistry):
        self._store = AnalysisStore(registry)

    def institution_features(self, member_name: Optional[str] = None,
                             trade_date: Optional[str] = None) -> list[dict]:
        """Query institution daily features.

        Args:
            member_name: Institution member name
            trade_date: Specific date

        Returns:
            List of institution feature dicts.
        """
        return self._store.get_institution_features(
            member_name=member_name, trade_date=trade_date,
        )

    def signals(self, signal_type: Optional[str] = None,
                start_date: Optional[str] = None,
                end_date: Optional[str] = None) -> list[dict]:
        """Query trading signals.

        Args:
            signal_type: Filter by type (entry_long, entry_short, etc.)
            start_date: Start date
            end_date: End date

        Returns:
            List of signal dicts.
        """
        return self._store.get_signals(
            signal_type=signal_type, start_date=start_date, end_date=end_date,
        )

    def market_regime(self, trade_date: Optional[str] = None) -> list[dict]:
        """Query market regime classification.

        Returns:
            List of market regime dicts.
        """
        return self._store.get_market_regime(trade_date=trade_date)

    def tushare_daily(self, ts_code: Optional[str] = None,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> list[dict]:
        """Query Tushare daily data.

        Args:
            ts_code: Tushare contract code
            start_date: Start date
            end_date: End date

        Returns:
            List of Tushare daily dicts.
        """
        return self._store.get_tushare_daily(
            ts_code=ts_code, start_date=start_date, end_date=end_date,
        )

    def option_features(self, trade_date: Optional[str] = None,
                        contract: Optional[str] = None) -> list[dict]:
        """Query option features (IV, Greeks).

        Args:
            trade_date: Specific date
            contract: Contract code

        Returns:
            List of option feature dicts.
        """
        clauses = []
        params = []
        if trade_date:
            clauses.append("trade_date = ?")
            params.append(trade_date)
        if contract:
            clauses.append("contract_code = ?")
            params.append(contract)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM option_features WHERE {where} ORDER BY trade_date DESC, contract_code"

        pool = self._store.registry.get_pool("analysis")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def iv_snapshot(self, underlying: Optional[str] = None,
                    trade_date: Optional[str] = None) -> list[dict]:
        """Get IV snapshot for all options of an underlying.

        Args:
            underlying: Underlying product (MO, IO, HO)
            trade_date: Specific date (defaults to latest)

        Returns:
            List of dicts with contract_code, iv, delta, gamma, etc.
        """
        clauses = []
        params = []
        if trade_date:
            clauses.append("trade_date = ?")
            params.append(trade_date)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM option_features WHERE {where} ORDER BY iv"

        pool = self._store.registry.get_pool("analysis")
        with pool.connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            results = [dict(zip(cols, row)) for row in cursor.fetchall()]

        if underlying:
            results = [r for r in results if r.get("contract_code", "").startswith(underlying)]

        return results
