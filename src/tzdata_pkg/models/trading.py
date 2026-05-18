"""SQLAlchemy Core Table definitions for tzdata_trading.db.

These are canonical table definitions that both tz-data and tz2.0
should use to ensure schema consistency.
"""

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, Table,
)
from sqlalchemy import MetaData

metadata = MetaData()


# ── Bills & Statements ─────────────────────────────────────────────

bills = Table(
    "bills", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String(50), nullable=False, index=True),
    Column("bill_date_start", String(20), nullable=False, index=True),
    Column("bill_date_end", String(20), nullable=False),
    Column("client_id", String(50), index=True),
    Column("client_name", String(100)),
    Column("currency", String(10), default="CNY"),
    Column("file_path", String(500)),
    Column("status", String(20), default="parsed"),
    Column("balance_bf", Float, default=0.0),
    Column("balance_cf", Float, default=0.0),
    Column("deposit_withdrawal", Float, default=0.0),
    Column("realized_pl", Float, default=0.0),
    Column("mtm_pl", Float, default=0.0),
    Column("exercise_pl", Float, default=0.0),
    Column("commission", Float, default=0.0),
    Column("premium_received", Float, default=0.0),
    Column("premium_paid", Float, default=0.0),
    Column("client_equity", Float, default=0.0),
    Column("fund_available", Float, default=0.0),
    Column("margin_occupied", Float, default=0.0),
    Column("created_at", DateTime),
)

bill_raw_sections = Table(
    "bill_raw_sections", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("bill_id", Integer, ForeignKey("bills.id")),
    Column("section_type", String(50), nullable=False),
    Column("raw_content", Text),
    Column("created_at", DateTime),
)


# ── Trades ─────────────────────────────────────────────────────────

trades = Table(
    "trades", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String(50), index=True),
    Column("year", Integer),
    Column("month", Integer),
    Column("trade_date", String(20), nullable=False, index=True),
    Column("exchange", String(20)),
    Column("product", String(30)),
    Column("instrument", String(30), nullable=False, index=True),
    Column("direction", String(10)),
    Column("offset_flag", String(10)),
    Column("volume", Integer),
    Column("price", Float),
    Column("turnover", Float),
    Column("commission", Float, default=0.0),
    Column("total_pnl", Float, default=0.0),
    Column("premium", Float, default=0.0),
    Column("trade_id", String(50)),
    Column("position_type", String(20)),
    # tz2.0 analysis extensions
    Column("trade_time", String(20)),
    Column("order_type", String(20)),
    Column("slippage", Float),
    Column("strategy_tag", String(50)),
    Column("vwap", Float),
    Column("created_at", DateTime),
)

matched_trades = Table(
    "matched_trades", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("instrument", String(30), nullable=False, index=True),
    Column("exchange", String(20)),
    Column("product", String(30)),
    Column("is_option", Integer, default=0),
    Column("open_trade_id", Integer),
    Column("open_date", String(20)),
    Column("open_price", Float),
    Column("open_volume", Integer),
    Column("open_premium", Float, default=0.0),
    Column("open_direction", String(10)),
    Column("close_trade_id", Integer),
    Column("close_date", String(20), index=True),
    Column("close_price", Float),
    Column("close_volume", Integer),
    Column("close_premium", Float, default=0.0),
    Column("holding_days", Integer),
    Column("price_pnl", Float, default=0.0),
    Column("premium_pnl", Float, default=0.0),
    Column("money_pnl", Float, default=0.0),
    Column("commission", Float, default=0.0),
    Column("net_pnl", Float, default=0.0),
    Column("status", String(20), default="closed"),
    # tz2.0 analysis extensions
    Column("multiplier", Integer, default=1),
)

trade_performance = Table(
    "trade_performance", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("matched_trade_id", Integer),
    Column("instrument", String(30)),
    Column("is_option", Integer, default=0),
    Column("open_date", String(20)),
    Column("close_date", String(20)),
    Column("open_volume", Integer),
    Column("open_direction", String(10)),
    Column("money_pnl", Float, default=0.0),
    Column("premium_pnl", Float, default=0.0),
    Column("commission", Float, default=0.0),
    Column("net_pnl", Float, default=0.0),
    Column("pnl_ratio", Float),
    Column("holding_days", Integer),
    Column("underlying", String(30)),
    Column("expiry", String(20)),
    Column("option_type", String(10)),
    Column("strike", Float),
    Column("delta", Float),
    Column("gamma", Float),
    Column("vega", Float),
    Column("theta", Float),
    Column("strategy_type", String(30)),
    Column("strategy_id", String(50)),
    Column("close_year", Integer),
    Column("close_month", Integer),
    Column("close_quarter", Integer),
)


# ── Positions & Accounts ───────────────────────────────────────────

positions_summary = Table(
    "positions_summary", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String(50)),
    Column("year", Integer),
    Column("month", Integer),
    Column("trade_date", String(20), nullable=False, index=True),
    Column("instrument", String(30), nullable=False, index=True),
    Column("exchange", String(20)),
    Column("product", String(30)),
    Column("long_position", Integer, default=0),
    Column("short_position", Integer, default=0),
    Column("prev_settlement", Float),
    Column("settlement_price", Float),
    Column("accumulated_pnl", Float, default=0.0),
    Column("margin_occupied", Float, default=0.0),
    Column("float_pl", Float, default=0.0),
    Column("created_at", DateTime),
)

account_summary = Table(
    "account_summary", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", String(50), index=True),
    Column("year", Integer, index=True),
    Column("month", Integer, index=True),
    Column("start_date", String(20)),
    Column("end_date", String(20)),
    Column("balance_b_f", Float, default=0.0),
    Column("balance_c_f", Float, default=0.0),
    Column("deposit_withdrawal", Float, default=0.0),
    Column("total_pnl", Float, default=0.0),
    Column("accumulated_pnl", Float, default=0.0),
    Column("exercise_pnl", Float, default=0.0),
    Column("commission", Float, default=0.0),
    Column("client_equity", Float, default=0.0),
    Column("margin_occupied", Float, default=0.0),
    Column("fund_available", Float, default=0.0),
    Column("risk_degree", Float, default=0.0),
    Column("margin_call", Float, default=0.0),
    Column("premium_received", Float, default=0.0),
    Column("premium_paid", Float, default=0.0),
    Column("market_value_long", Float, default=0.0),
    Column("market_value_short", Float, default=0.0),
    Column("market_value_equity", Float, default=0.0),
    Column("created_at", DateTime),
)

account_cashflow = Table(
    "account_cashflow", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("time", DateTime),
    Column("type", String(50), nullable=False),
    Column("amount", Float, nullable=False),
    Column("balance", Float),
    Column("description", Text),
)


# ── Trade Comparison ───────────────────────────────────────────────

trade_comparison_analysis = Table(
    "trade_comparison_analysis", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("analysis_date", String(20)),
    Column("instrument", String(30)),
    Column("exchange", String(20)),
    Column("product", String(30)),
    Column("is_option", Integer, default=0),
    Column("open_trade_id", Integer),
    Column("open_date", String(20)),
    Column("open_price", Float),
    Column("open_volume", Integer),
    Column("open_direction", String(10)),
    Column("open_premium", Float),
    Column("actual_close_date", String(20)),
    Column("actual_close_price", Float),
    Column("actual_close_volume", Integer),
    Column("actual_money_pnl", Float),
    Column("actual_premium_pnl", Float),
    Column("actual_net_pnl", Float),
    Column("virtual_close_price", Float),
    Column("virtual_money_pnl", Float),
    Column("virtual_premium_pnl", Float),
    Column("virtual_net_pnl", Float),
    Column("pnl_difference", Float),
    Column("pnl_difference_ratio", Float),
)


# ── Market Reference ───────────────────────────────────────────────

cffex_daily_settlement = Table(
    "cffex_daily_settlement", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trade_date", String(20), nullable=False, index=True),
    Column("instrument", String(30), nullable=False),
    Column("product", String(30)),
    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float),
    Column("settle", Float),
    Column("prev_settle", Float),
    Column("volume", Integer),
    Column("turnover", Float),
    Column("open_interest", Float),
    Column("delta", Float),
    Column("source", String(20), default="cffex"),
    Column("created_at", DateTime),
)

daily_index_prices = Table(
    "daily_index_prices", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("index_code", String(20), nullable=False),
    Column("trade_date", String(20), nullable=False),
    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float),
    Column("volume", Integer),
    Column("created_at", DateTime),
)

option_greeks_daily = Table(
    "option_greeks_daily", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("trade_date", String(20), nullable=False),
    Column("symbol", String(30), nullable=False),
    Column("option_type", String(10)),
    Column("strike_price", Float),
    Column("expiry_date", String(20)),
    Column("underlying_price", Float),
    Column("iv", Float),
    Column("delta", Float),
    Column("gamma", Float),
    Column("vega", Float),
    Column("theta", Float),
    Column("created_at", DateTime),
)

contract_expiry = Table(
    "contract_expiry", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("symbol", String(30), nullable=False, unique=True),
    Column("exchange", String(20), nullable=False),
    Column("product_type", String(20)),
    Column("expiry_date", String(20), nullable=False),
    Column("underlying_symbol", String(30)),
    Column("strike_price", Float),
    Column("created_at", DateTime),
)


# ── Strategies ─────────────────────────────────────────────────────

strategies = Table(
    "strategies", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("description", Text),
    Column("type", String(30)),
    Column("status", String(20), default="active"),
    Column("created_at", DateTime),
)

strategy_summary = Table(
    "strategy_summary", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("strategy_id", Integer),
    Column("date", String(20)),
    Column("total_equity", Float, default=0.0),
    Column("daily_pnl", Float, default=0.0),
    Column("daily_return", Float, default=0.0),
    Column("cumulative_return", Float, default=0.0),
    Column("drawdown", Float, default=0.0),
    Column("sharpe_ratio", Float),
    Column("created_at", DateTime),
)

strategy_performance_summary = Table(
    "strategy_performance_summary", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("strategy_id", Integer),
    Column("strategy_name", String(100)),
    Column("period_start", String(20)),
    Column("period_end", String(20)),
    Column("total_trades", Integer),
    Column("win_trades", Integer),
    Column("loss_trades", Integer),
    Column("win_rate", Float),
    Column("total_pnl", Float, default=0.0),
    Column("avg_pnl", Float, default=0.0),
    Column("max_drawdown", Float, default=0.0),
    Column("sharpe_ratio", Float),
    Column("profit_factor", Float),
    Column("avg_holding_days", Float),
    Column("created_at", DateTime),
)

backtest_results = Table(
    "backtest_results", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("strategy_name", String(100)),
    Column("start_date", String(20)),
    Column("end_date", String(20)),
    Column("initial_capital", Float),
    Column("final_equity", Float),
    Column("total_return", Float),
    Column("annual_return", Float),
    Column("max_drawdown", Float),
    Column("sharpe_ratio", Float),
    Column("sortino_ratio", Float),
    Column("calmar_ratio", Float),
    Column("total_trades", Integer),
    Column("win_rate", Float),
    Column("profit_factor", Float),
    Column("params", Text),
    Column("created_at", DateTime),
)


# ── Option Simulation ──────────────────────────────────────────────

option_sim_strategies = Table(
    "option_sim_strategies", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("description", Text),
    Column("underlying", String(30)),
    Column("initial_capital", Float, default=1_000_000),
    Column("status", String(20), default="active"),
    Column("created_at", DateTime),
)

option_sim_trades = Table(
    "option_sim_trades", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("strategy_id", Integer),
    Column("instrument", String(30)),
    Column("direction", String(10)),
    Column("volume", Integer),
    Column("entry_price", Float),
    Column("exit_price", Float),
    Column("entry_date", String(20)),
    Column("exit_date", String(20)),
    Column("pnl", Float, default=0.0),
    Column("commission", Float, default=0.0),
    Column("status", String(20), default="closed"),
    Column("created_at", DateTime),
)

option_sim_iv_series = Table(
    "option_sim_iv_series", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("strategy_id", Integer),
    Column("trade_date", String(20), nullable=False, index=True),
    Column("iv_value", Float),
    Column("iv_percentile", Float),
    Column("iv_rank", Float),
    Column("hv_20", Float),
    Column("hv_60", Float),
    Column("iv_hv_spread", Float),
    Column("created_at", DateTime),
)


# ── Paper Trading ──────────────────────────────────────────────────

paper_accounts = Table(
    "paper_accounts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("initial_capital", Float, default=1_000_000),
    Column("current_equity", Float, default=1_000_000),
    Column("status", String(20), default="active"),
    Column("created_at", DateTime),
)

paper_position = Table(
    "paper_position", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer),
    Column("instrument", String(30), nullable=False),
    Column("direction", String(10)),
    Column("volume", Integer, default=0),
    Column("avg_price", Float),
    Column("current_price", Float),
    Column("unrealized_pnl", Float, default=0.0),
    Column("margin_used", Float, default=0.0),
    Column("updated_at", DateTime),
)

paper_trade = Table(
    "paper_trade", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer),
    Column("instrument", String(30)),
    Column("direction", String(10)),
    Column("volume", Integer),
    Column("price", Float),
    Column("commission", Float, default=0.0),
    Column("trade_date", String(20)),
    Column("notes", Text),
    Column("created_at", DateTime),
)

paper_order = Table(
    "paper_order", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer),
    Column("instrument", String(30)),
    Column("direction", String(10)),
    Column("volume", Integer),
    Column("price", Float),
    Column("order_type", String(20), default="limit"),
    Column("status", String(20), default="pending"),
    Column("created_at", DateTime),
)


# ── Reports & Risk ─────────────────────────────────────────────────

reports = Table(
    "reports", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("title", String(200), nullable=False),
    Column("report_type", String(50)),
    Column("content", Text),
    Column("generated_at", DateTime),
    Column("created_by", Integer),
)

report_templates = Table(
    "report_templates", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("template_type", String(50)),
    Column("content", Text),
    Column("variables", Text),
    Column("created_at", DateTime),
)

risk_config = Table(
    "risk_config", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("key", String(100), nullable=False, unique=True),
    Column("value", Text),
    Column("description", Text),
    Column("updated_at", DateTime),
)

risk_history = Table(
    "risk_history", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("risk_type", String(50), nullable=False),
    Column("level", String(20)),
    Column("detail", Text),
    Column("triggered_at", DateTime),
)


# ── Futures Accounts & Statement Status ────────────────────────────

futures_accounts = Table(
    "futures_accounts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_name", String(100), nullable=False),
    Column("account_number", String(50), unique=True),
    Column("futures_company", String(100)),
    Column("exchanges_supported", Text),
    Column("tracking_start_date", String(20)),
    Column("cfmmc_username", String(100)),
    Column("cfmmc_password_encrypted", Text),
    Column("is_active", Boolean, default=True),
    Column("last_statement_date", String(20)),
    Column("last_sync_at", DateTime),
    Column("created_at", DateTime),
)

statement_status = Table(
    "statement_status", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("account_id", Integer, ForeignKey("futures_accounts.id")),
    Column("statement_date", String(20), nullable=False, index=True),
    Column("upload_status", String(20), default="missing"),
    Column("parse_status", String(20)),
    Column("data_quality_score", Float),
    Column("balance_check_passed", Boolean),
    Column("error_count", Integer, default=0),
    Column("file_path", Text),
    Column("uploaded_at", DateTime),
    Column("parsed_at", DateTime),
)


# ── Bill Fund Flows ────────────────────────────────────────────────

bill_fund_flows = Table(
    "bill_fund_flows", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("bill_id", Integer, ForeignKey("bills.id"), nullable=False),
    Column("trade_date", String(20), nullable=False),
    Column("flow_type", String(50), nullable=False),
    Column("amount", Float, nullable=False),
    Column("symbol", String(30)),
    Column("description", Text),
    Column("created_at", DateTime),
)
