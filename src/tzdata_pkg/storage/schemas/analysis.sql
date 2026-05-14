-- tzdata_analysis.db: Institution features, signals, regimes, Tushare data
-- Consolidates institution.db + tushare.db + trading.db (analysis tables)

CREATE TABLE IF NOT EXISTS institution_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    member_name TEXT NOT NULL UNIQUE,
    member_code TEXT,
    category TEXT,                     -- futures_company, bank, securities, other
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS institution_name_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    exchange TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(raw_name, exchange)
);

CREATE TABLE IF NOT EXISTS institution_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_name TEXT NOT NULL,
    member_code TEXT,
    category TEXT,
    total_long INTEGER DEFAULT 0,
    total_short INTEGER DEFAULT 0,
    total_net INTEGER GENERATED ALWAYS AS (total_long - total_short) STORED,
    first_appearance TEXT,
    last_appearance TEXT,
    avg_daily_volume REAL,
    bias_direction TEXT,               -- long_bias, short_bias, neutral
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inst_profile_name ON institution_profiles(member_name);

CREATE TABLE IF NOT EXISTS institution_daily_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    member_name TEXT NOT NULL,
    contract_code TEXT,
    exchange TEXT,
    long_volume INTEGER DEFAULT 0,
    short_volume INTEGER DEFAULT 0,
    net_volume INTEGER GENERATED ALWAYS AS (long_volume - short_volume) STORED,
    long_change INTEGER,
    short_change INTEGER,
    net_change INTEGER,
    member_rank_long INTEGER,
    member_rank_short INTEGER,
    total_market_long INTEGER,
    total_market_short INTEGER,
    member_long_pct REAL,              -- member_long / total_market_long
    member_short_pct REAL,
    concentration_score REAL,          -- how concentrated vs diversified
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inst_daily_date ON institution_daily_features(trade_date);
CREATE INDEX IF NOT EXISTS idx_inst_daily_member ON institution_daily_features(member_name);

CREATE TABLE IF NOT EXISTS feature_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    contract_code TEXT,
    exchange TEXT,
    top_long_member TEXT,
    top_short_member TEXT,
    top_long_volume INTEGER,
    top_short_volume INTEGER,
    net_institutional_flow INTEGER,
    long_institutional_pct REAL,
    short_institutional_pct REAL,
    sentiment_score REAL,              -- composite sentiment -1 to 1
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feature_daily_date ON feature_daily(trade_date);

CREATE TABLE IF NOT EXISTS cffex_holdings_continuous (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    contract_code TEXT NOT NULL,
    product TEXT,
    total_long INTEGER,
    total_short INTEGER,
    total_net INTEGER GENERATED ALWAYS AS (total_long - total_short) STORED,
    total_volume INTEGER,
    oi_long INTEGER,
    oi_short INTEGER,
    oi_ratio REAL,                     -- long_oi / short_oi
    smart_money_long INTEGER,
    smart_money_short INTEGER,
    retail_long INTEGER,
    retail_short INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_holdings_continuous_date ON cffex_holdings_continuous(trade_date);
CREATE INDEX IF NOT EXISTS idx_holdings_continuous_contract ON cffex_holdings_continuous(contract_code);

CREATE TABLE IF NOT EXISTS option_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    contract_code TEXT NOT NULL,
    underlying TEXT,
    expiry TEXT,
    strike REAL,
    option_type TEXT,                  -- C or P
    iv REAL,
    iv_percentile REAL,
    iv_rank REAL,
    delta REAL,
    gamma REAL,
    theta REAL,
    vega REAL,
    rho REAL,
    hv_5 REAL,
    hv_10 REAL,
    hv_20 REAL,
    iv_hv_spread_20 REAL,
    volume INTEGER,
    open_interest INTEGER,
    volume_oi_ratio REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_option_features_date ON option_features(trade_date);
CREATE INDEX IF NOT EXISTS idx_option_features_contract ON option_features(contract_code);

CREATE TABLE IF NOT EXISTS trading_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_date TEXT NOT NULL,
    product TEXT,
    exchange TEXT,
    signal_type TEXT NOT NULL,         -- entry_long, entry_short, exit, reduce
    strength REAL,                     -- 0-1 confidence
    source TEXT,                       -- institution_flow, iv_analysis, technical
    detail TEXT,                       -- JSON
    triggered BOOLEAN DEFAULT 0,
    triggered_date TEXT,
    triggered_pnl REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signals_date ON trading_signals(signal_date);
CREATE INDEX IF NOT EXISTS idx_signals_type ON trading_signals(signal_type);

CREATE TABLE IF NOT EXISTS signal_triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER,
    trigger_date TEXT NOT NULL,
    entry_price REAL,
    exit_price REAL,
    holding_days INTEGER,
    pnl REAL DEFAULT 0.0,
    status TEXT DEFAULT 'open',
    FOREIGN KEY (signal_id) REFERENCES trading_signals(id)
);

CREATE TABLE IF NOT EXISTS market_regime (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    regime_type TEXT NOT NULL,         -- trending_up, trending_down, range, volatile
    contract_code TEXT,
    trend_strength REAL,               -- 0-1
    volatility_level REAL,             -- low, medium, high (numeric)
    volume_trend REAL,                 -- increasing, decreasing
    iv_regime TEXT,                    -- low_iv, high_iv, rising_iv, falling_iv
    regime_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_market_regime_date ON market_regime(trade_date);

CREATE TABLE IF NOT EXISTS institution_lead_lag (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    leading_member TEXT,
    lagging_members TEXT,              -- JSON array
    correlation REAL,
    lag_days INTEGER,
    signal_direction TEXT,             -- bullish, bearish
    accuracy REAL,                     -- historical accuracy
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_validation_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    validation_date TEXT,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    threshold REAL,
    passed BOOLEAN,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tushare_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    pre_close REAL,
    change REAL,
    pct_change REAL,
    volume REAL,
    amount REAL,
    settle REAL,
    oi REAL,
    oi_change REAL,
    source TEXT DEFAULT 'tushare',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_tushare_daily_date ON tushare_daily(trade_date);

CREATE TABLE IF NOT EXISTS tushare_minute (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    trade_time TEXT NOT NULL,          -- HH:MM:SS
    freq TEXT NOT NULL,                -- 1min, 5min, etc.
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    source TEXT DEFAULT 'tushare',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ts_code, trade_date, trade_time, freq)
);

CREATE TABLE IF NOT EXISTS tushare_option (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    pre_settle REAL,
    settle REAL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    oi REAL,
    delta REAL,
    gamma REAL,
    theta REAL,
    vega REAL,
    iv REAL,
    source TEXT DEFAULT 'tushare',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_tushare_option_date ON tushare_option(trade_date);

CREATE TABLE IF NOT EXISTS download_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,              -- tushare, cfmmc, etc.
    data_type TEXT NOT NULL,
    product TEXT,
    records_downloaded INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT,
    duration_seconds REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds REAL,
    output TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS analysis_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key TEXT NOT NULL UNIQUE,
    cache_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
