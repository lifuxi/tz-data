"""tz-data shared SQLAlchemy models.

Provides canonical table definitions for tz-data's databases.
Used by both tz-data (internal) and tz2.0 (consumer) to ensure
schema consistency across projects.

Usage:
    from tzdata_pkg.models import bills, trades, positions_summary, account_summary
    from sqlalchemy import select

    stmt = select(bills).where(bills.c.account_id == "321980")
"""

from tzdata_pkg.models.trading import (
    bills,
    bill_raw_sections,
    trades,
    matched_trades,
    trade_performance,
    positions_summary,
    account_summary,
    account_cashflow,
    trade_comparison_analysis,
    cffex_daily_settlement,
    strategies,
    strategy_performance_summary,
    strategy_summary,
    backtest_results,
    option_sim_strategies,
    option_sim_trades,
    option_sim_iv_series,
    paper_accounts,
    paper_position,
    paper_trade,
    paper_order,
    reports,
    report_templates,
    risk_config,
    risk_history,
    futures_accounts,
    statement_status,
    bill_fund_flows,
    option_greeks_daily,
    daily_index_prices,
    contract_expiry,
)
from tzdata_pkg.models.version import SCHEMA_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "bills",
    "bill_raw_sections",
    "trades",
    "matched_trades",
    "trade_performance",
    "positions_summary",
    "account_summary",
    "account_cashflow",
    "trade_comparison_analysis",
    "cffex_daily_settlement",
    "strategies",
    "strategy_performance_summary",
    "strategy_summary",
    "backtest_results",
    "option_sim_strategies",
    "option_sim_trades",
    "option_sim_iv_series",
    "paper_accounts",
    "paper_position",
    "paper_trade",
    "paper_order",
    "reports",
    "report_templates",
    "risk_config",
    "risk_history",
    "futures_accounts",
    "statement_status",
    "bill_fund_flows",
    "option_greeks_daily",
    "daily_index_prices",
    "contract_expiry",
]
