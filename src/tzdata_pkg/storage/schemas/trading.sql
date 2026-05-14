-- tzdata_trading.db: Bills, trades, accounts, positions
-- Consolidates bills.db (core tables) + option_sim.db

CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    bill_date_start TEXT NOT NULL,     -- YYYY-MM-DD
    bill_date_end TEXT NOT NULL,
    client_id TEXT,
    client_name TEXT,
    currency TEXT DEFAULT 'CNY',
    file_path TEXT,
    status TEXT DEFAULT 'parsed',      -- uploaded, parsed, error
    balance_bf REAL DEFAULT 0.0,
    balance_cf REAL DEFAULT 0.0,
    deposit_withdrawal REAL DEFAULT 0.0,
    realized_pl REAL DEFAULT 0.0,
    mtm_pl REAL DEFAULT 0.0,
    exercise_pl REAL DEFAULT 0.0,
    commission REAL DEFAULT 0.0,
    premium_received REAL DEFAULT 0.0,
    premium_paid REAL DEFAULT 0.0,
    client_equity REAL DEFAULT 0.0,
    fund_available REAL DEFAULT 0.0,
    margin_occupied REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bills_account ON bills(account_id);
CREATE INDEX IF NOT EXISTS idx_bills_date ON bills(bill_date_start, bill_date_end);

CREATE TABLE IF NOT EXISTS bill_raw_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER,
    section_type TEXT NOT NULL,        -- summary, deposits, transactions, positions
    raw_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(id)
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT,
    year INTEGER,
    month INTEGER,
    trade_date TEXT NOT NULL,
    exchange TEXT,
    product TEXT,
    instrument TEXT NOT NULL,
    direction TEXT,                    -- 买/卖, buy/sell
    offset_flag TEXT,                  -- 开/平/平今/平昨
    volume INTEGER,
    price REAL,
    turnover REAL,
    commission REAL DEFAULT 0.0,
    total_pnl REAL DEFAULT 0.0,
    premium REAL DEFAULT 0.0,
    trade_id TEXT,
    position_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument);
CREATE INDEX IF NOT EXISTS idx_trades_account ON trades(account_id);

CREATE TABLE IF NOT EXISTS matched_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument TEXT NOT NULL,
    exchange TEXT,
    product TEXT,
    is_option INTEGER DEFAULT 0,
    open_trade_id INTEGER,
    open_date TEXT,
    open_price REAL,
    open_volume INTEGER,
    open_premium REAL DEFAULT 0.0,
    open_direction TEXT,
    close_trade_id INTEGER,
    close_date TEXT,
    close_price REAL,
    close_volume INTEGER,
    close_premium REAL DEFAULT 0.0,
    holding_days INTEGER,
    price_pnl REAL DEFAULT 0.0,
    premium_pnl REAL DEFAULT 0.0,
    money_pnl REAL DEFAULT 0.0,
    commission REAL DEFAULT 0.0,
    net_pnl REAL DEFAULT 0.0,
    status TEXT DEFAULT 'closed'
);

CREATE INDEX IF NOT EXISTS idx_matched_instrument ON matched_trades(instrument);
CREATE INDEX IF NOT EXISTS idx_matched_close_date ON matched_trades(close_date);

CREATE TABLE IF NOT EXISTS trade_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matched_trade_id INTEGER,
    instrument TEXT,
    is_option INTEGER DEFAULT 0,
    open_date TEXT,
    close_date TEXT,
    open_volume INTEGER,
    open_direction TEXT,
    money_pnl REAL DEFAULT 0.0,
    premium_pnl REAL DEFAULT 0.0,
    commission REAL DEFAULT 0.0,
    net_pnl REAL DEFAULT 0.0,
    pnl_ratio REAL,
    holding_days INTEGER,
    underlying TEXT,
    expiry TEXT,
    option_type TEXT,
    strike REAL,
    delta REAL,
    gamma REAL,
    vega REAL,
    theta REAL,
    strategy_type TEXT,
    strategy_id TEXT,
    close_year INTEGER,
    close_month INTEGER,
    close_quarter INTEGER
);

CREATE TABLE IF NOT EXISTS positions_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT,
    year INTEGER,
    month INTEGER,
    trade_date TEXT,
    instrument TEXT NOT NULL,
    exchange TEXT,
    product TEXT,
    long_position INTEGER DEFAULT 0,
    short_position INTEGER DEFAULT 0,
    prev_settlement REAL,
    settlement_price REAL,
    accumulated_pnl REAL DEFAULT 0.0,
    margin_occupied REAL DEFAULT 0.0,
    float_pl REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pos_summary_instrument ON positions_summary(instrument);
CREATE INDEX IF NOT EXISTS idx_pos_summary_date ON positions_summary(trade_date);

CREATE TABLE IF NOT EXISTS account_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT,
    year INTEGER,
    month INTEGER,
    start_date TEXT,
    end_date TEXT,
    balance_b_f REAL DEFAULT 0.0,
    balance_c_f REAL DEFAULT 0.0,
    deposit_withdrawal REAL DEFAULT 0.0,
    total_pnl REAL DEFAULT 0.0,
    accumulated_pnl REAL DEFAULT 0.0,
    exercise_pnl REAL DEFAULT 0.0,
    commission REAL DEFAULT 0.0,
    client_equity REAL DEFAULT 0.0,
    margin_occupied REAL DEFAULT 0.0,
    fund_available REAL DEFAULT 0.0,
    risk_degree REAL DEFAULT 0.0,
    margin_call REAL DEFAULT 0.0,
    premium_received REAL DEFAULT 0.0,
    premium_paid REAL DEFAULT 0.0,
    market_value_long REAL DEFAULT 0.0,
    market_value_short REAL DEFAULT 0.0,
    market_value_equity REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_acct_summary_account ON account_summary(account_id);
CREATE INDEX IF NOT EXISTS idx_acct_summary_period ON account_summary(year, month);

CREATE TABLE IF NOT EXISTS account_cashflow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    type TEXT NOT NULL,                -- deposit, withdrawal, trading_pnl, commission
    amount REAL NOT NULL,
    balance REAL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS trade_comparison_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date DATE,
    instrument TEXT,
    exchange TEXT,
    product TEXT,
    is_option INTEGER DEFAULT 0,
    open_trade_id INTEGER,
    open_date TEXT,
    open_price REAL,
    open_volume INTEGER,
    open_direction TEXT,
    open_premium REAL,
    actual_close_date TEXT,
    actual_close_price REAL,
    actual_close_volume INTEGER,
    actual_money_pnl REAL,
    actual_premium_pnl REAL,
    actual_net_pnl REAL,
    virtual_close_price REAL,
    virtual_money_pnl REAL,
    virtual_premium_pnl REAL,
    virtual_net_pnl REAL,
    pnl_difference REAL,
    pnl_difference_ratio REAL
);

CREATE TABLE IF NOT EXISTS cffex_daily_settlement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    instrument TEXT NOT NULL,
    product TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    settle REAL,
    prev_settle REAL,
    volume INTEGER,
    turnover REAL,
    open_interest REAL,
    delta REAL,
    source TEXT DEFAULT 'cffex',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cffex_settlement_date ON cffex_daily_settlement(trade_date);

CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    type TEXT,                         -- discretionary, systematic, hybrid
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS strategy_performance_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER,
    strategy_name TEXT,
    period_start TEXT,
    period_end TEXT,
    total_trades INTEGER,
    win_trades INTEGER,
    loss_trades INTEGER,
    win_rate REAL,
    total_pnl REAL DEFAULT 0.0,
    avg_pnl REAL DEFAULT 0.0,
    max_drawdown REAL DEFAULT 0.0,
    sharpe_ratio REAL,
    profit_factor REAL,
    avg_holding_days REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS strategy_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER,
    date TEXT,
    total_equity REAL DEFAULT 0.0,
    daily_pnl REAL DEFAULT 0.0,
    daily_return REAL DEFAULT 0.0,
    cumulative_return REAL DEFAULT 0.0,
    drawdown REAL DEFAULT 0.0,
    sharpe_ratio REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT,
    start_date TEXT,
    end_date TEXT,
    initial_capital REAL,
    final_equity REAL,
    total_return REAL,
    annual_return REAL,
    max_drawdown REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    calmar_ratio REAL,
    total_trades INTEGER,
    win_rate REAL,
    profit_factor REAL,
    params TEXT,                       -- JSON string of parameters
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS option_sim_strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    underlying TEXT,
    initial_capital REAL DEFAULT 1000000,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS option_sim_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER,
    instrument TEXT,
    direction TEXT,
    volume INTEGER,
    entry_price REAL,
    exit_price REAL,
    entry_date TEXT,
    exit_date TEXT,
    pnl REAL DEFAULT 0.0,
    commission REAL DEFAULT 0.0,
    status TEXT DEFAULT 'closed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS option_sim_iv_series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER,
    trade_date TEXT NOT NULL,
    iv_value REAL,
    iv_percentile REAL,
    iv_rank REAL,
    hv_20 REAL,
    hv_60 REAL,
    iv_hv_spread REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_iv_series_date ON option_sim_iv_series(trade_date);

CREATE TABLE IF NOT EXISTS paper_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    initial_capital REAL DEFAULT 1000000,
    current_equity REAL DEFAULT 1000000,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_position (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    instrument TEXT NOT NULL,
    direction TEXT,
    volume INTEGER DEFAULT 0,
    avg_price REAL,
    current_price REAL,
    unrealized_pnl REAL DEFAULT 0.0,
    margin_used REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_trade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    instrument TEXT,
    direction TEXT,
    volume INTEGER,
    price REAL,
    commission REAL DEFAULT 0.0,
    trade_date TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS paper_order (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    instrument TEXT,
    direction TEXT,
    volume INTEGER,
    price REAL,
    order_type TEXT DEFAULT 'limit',
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    report_type TEXT,
    content TEXT,                      -- JSON or HTML
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER
);

CREATE TABLE IF NOT EXISTS report_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    template_type TEXT,
    content TEXT,                      -- HTML/Markdown template
    variables TEXT,                    -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS risk_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS risk_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_type TEXT NOT NULL,
    level TEXT,                        -- normal, warning, critical
    detail TEXT,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 期货账户配置（数据维护系统扩展）
CREATE TABLE IF NOT EXISTS futures_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name VARCHAR(100) NOT NULL,
    account_number VARCHAR(50) UNIQUE,
    futures_company VARCHAR(100),                -- 中信期货、永安期货
    exchanges_supported TEXT,                    -- JSON: ["CFFEX", "SHFE"]
    tracking_start_date DATE,                    -- 开始跟踪日期
    cfmmc_username VARCHAR(100),                 -- 监控中心用户名（加密存储）
    cfmmc_password_encrypted TEXT,               -- AES-256加密后的密码
    is_active BOOLEAN DEFAULT 1,
    last_statement_date DATE,
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 账单状态表（补充现有bills表）
CREATE TABLE IF NOT EXISTS statement_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES futures_accounts(id),
    statement_date DATE NOT NULL,
    upload_status VARCHAR(20) DEFAULT 'missing', -- missing, uploaded, parsing, parsed, error
    parse_status VARCHAR(20),                    -- success, partial, failed
    data_quality_score DECIMAL(5,2),             -- 0-100
    balance_check_passed BOOLEAN,                -- 资金平衡校验
    error_count INTEGER DEFAULT 0,
    file_path TEXT,
    uploaded_at TIMESTAMP,
    parsed_at TIMESTAMP,
    UNIQUE(account_id, statement_date)
);

CREATE INDEX IF NOT EXISTS idx_statement_status_date ON statement_status(statement_date);
