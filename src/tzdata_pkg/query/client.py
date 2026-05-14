"""TzDataClient — unified Python SDK for tz-data.

Usage:
    from tzdata_pkg.query import TzDataClient

    client = TzDataClient()

    # Market data
    quotes = client.quotes.get(exchange="CFFEX", contract="MO2505")
    positions = client.positions.get(contract="MO2505", trade_date="2025-05-01")
    contracts = client.contracts.list(exchange="CFFEX")

    # Trading data
    bills = client.bills.list(account_id="123")
    trades = client.trades.list(start_date="2025-01-01")
    pnl = client.trades.pnl_summary(account_id="123")

    # Analysis data
    signals = client.signals.get(signal_type="entry_long")
    regime = client.market_regime.get()
    iv_data = client.options.iv_snapshot(underlying="MO")
"""

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.query.market import MarketQuery
from tzdata_pkg.query.trading import TradingQuery
from tzdata_pkg.query.analysis import AnalysisQuery


class _MarketAccessor:
    """Namespace for market data queries."""

    def __init__(self, registry: DBRegistry):
        self._query = MarketQuery(registry)

    def get(self, **kwargs):
        """Alias for quotes()."""
        return self._query.quotes(**kwargs)

    quotes = property(lambda self: self._query.quotes)
    positions = property(lambda self: self._query.positions)
    contracts = property(lambda self: self._query.contracts)
    top_holders = property(lambda self: self._query.top_holders)
    quote_summary = property(lambda self: self._query.quote_summary)


class _TradingAccessor:
    """Namespace for trading data queries."""

    def __init__(self, registry: DBRegistry):
        self._query = TradingQuery(registry)

    bills = property(lambda self: self._query.bills)
    trades = property(lambda self: self._query.trades)
    matched_trades = property(lambda self: self._query.matched_trades)
    positions = property(lambda self: self._query.positions)
    account_summary = property(lambda self: self._query.account_summary)
    pnl_summary = property(lambda self: self._query.pnl_summary)


class _AnalysisAccessor:
    """Namespace for analysis data queries."""

    def __init__(self, registry: DBRegistry):
        self._query = AnalysisQuery(registry)

    def get(self, **kwargs):
        """Alias for signals()."""
        return self._query.signals(**kwargs)

    institution_features = property(lambda self: self._query.institution_features)
    signals = property(lambda self: self._query.signals)
    market_regime = property(lambda self: self._query.market_regime)
    tushare_daily = property(lambda self: self._query.tushare_daily)
    option_features = property(lambda self: self._query.option_features)
    options = property(lambda self: type("_Options", (), {
        "iv_snapshot": lambda _, **kw: self._query.iv_snapshot(**kw),
        "features": lambda _, **kw: self._query.option_features(**kw),
    })())


class TzDataClient:
    """Unified query interface for tz-data.

    Provides three namespaces:
    - client.quotes / client.positions / client.contracts — market data
    - client.bills / client.trades / client.pnl_summary — trading data
    - client.signals / client.market_regime / client.options — analysis data

    All methods return lists of dicts.
    """

    def __init__(self):
        self._registry = DBRegistry()

        # Market data accessors
        self._market = MarketQuery(self._registry)
        self.quotes = self._market.quotes
        self.positions = self._market.positions
        self.contracts = self._market.contracts
        self.top_holders = self._market.top_holders
        self.quote_summary = self._market.quote_summary

        # Trading data accessors
        self._trading = TradingQuery(self._registry)
        self.bills = self._trading.bills
        self.trades = self._trading.trades
        self.matched_trades = self._trading.matched_trades
        self.positions_summary = self._trading.positions
        self.account_summary = self._trading.account_summary
        self.pnl_summary = self._trading.pnl_summary

        # Analysis data accessors
        self._analysis = AnalysisQuery(self._registry)
        self.institution_features = self._analysis.institution_features
        self.signals = self._analysis.signals
        self.market_regime = self._analysis.market_regime
        self.tushare_daily = self._analysis.tushare_daily
        self.option_features = self._analysis.option_features
        self.iv_snapshot = self._analysis.iv_snapshot

    # ── Convenience methods ─────────────────────────────────

    def status(self) -> dict:
        """Get data status summary across all databases.

        Returns:
            Dict with table names and row counts.
        """
        result = {"databases": {}}
        for db_name in ["market", "trading", "analysis"]:
            tables = {}
            pool = self._registry.get_pool(db_name)
            with pool.connection() as conn:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
                for (table,) in rows:
                    try:
                        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        tables[table] = count
                    except Exception:
                        tables[table] = -1
            result["databases"][db_name] = tables
        return result

    def close(self):
        """Close all database connections."""
        for db_name in ["market", "trading", "analysis"]:
            try:
                self._registry.get_pool(db_name).close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
