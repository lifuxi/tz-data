-- tzdata_market.db: Market data (quotes, positions, contracts)
-- Consolidates cffex.db, shfe.db, cffex_minute_data.db, market_data.db, market_quotes.db

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,            -- CFFEX, SHFE, DCE, CZCE, INE
    variety TEXT NOT NULL,             -- IM, MO, AU, AG, etc.
    contract_code TEXT NOT NULL UNIQUE, -- IM2505, MO2505-C-8500
    contract_type TEXT NOT NULL,       -- futures, option_call, option_put
    underlying TEXT,                   -- underlying contract/variety
    strike_price REAL,                 -- for options
    expiry_date TEXT,                  -- YYYY-MM-DD or YYYYMMDD
    multiplier REAL,                   -- contract multiplier
    tick_size REAL,                    -- minimum price change
    lot_size INTEGER DEFAULT 1,        -- trading unit (lots)
    currency TEXT DEFAULT 'CNY',
    status TEXT DEFAULT 'active',      -- active, expired, suspended
    listing_date TEXT,
    delisting_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contracts_exchange ON contracts(exchange);
CREATE INDEX IF NOT EXISTS idx_contracts_variety ON contracts(variety);
CREATE INDEX IF NOT EXISTS idx_contracts_type ON contracts(contract_type);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);

CREATE TABLE IF NOT EXISTS daily_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    contract_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,          -- YYYY-MM-DD
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    settle REAL,                       -- settlement price
    prev_settle REAL,
    volume INTEGER,                    -- trading volume
    turnover REAL,                     -- trading amount
    open_interest INTEGER,             -- open interest
    daily_change REAL,
    daily_change_pct REAL,
    amplitude REAL,                    -- (high-low)/prev_settle
    source TEXT DEFAULT 'exchange',    -- exchange, tushare, akshare
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, contract_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_quotes_date ON daily_quotes(trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_quotes_contract ON daily_quotes(contract_code);
CREATE INDEX IF NOT EXISTS idx_daily_quotes_exchange_date ON daily_quotes(exchange, trade_date);

CREATE TABLE IF NOT EXISTS minute_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    contract_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    trade_time TEXT NOT NULL,          -- HH:MM:SS
    frequency TEXT NOT NULL,           -- 1min, 5min, 15min, 30min, 60min
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    turnover REAL,
    open_interest INTEGER,
    vwap REAL,
    source TEXT DEFAULT 'tushare',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, contract_code, trade_date, trade_time, frequency)
);

CREATE INDEX IF NOT EXISTS idx_minute_quotes_datetime ON minute_quotes(trade_date, trade_time);
CREATE INDEX IF NOT EXISTS idx_minute_quotes_contract ON minute_quotes(contract_code);

CREATE TABLE IF NOT EXISTS settlement_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    contract_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    settle_price REAL NOT NULL,
    volume_weighted REAL,
    source TEXT DEFAULT 'exchange',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, contract_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_settlement_prices_date ON settlement_prices(trade_date);

CREATE TABLE IF NOT EXISTS position_detail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    contract_code TEXT NOT NULL,
    product TEXT,
    member_name TEXT NOT NULL,
    rank INTEGER,
    long_volume INTEGER DEFAULT 0,
    short_volume INTEGER DEFAULT 0,
    long_change INTEGER,
    short_change INTEGER,
    net_position INTEGER GENERATED ALWAYS AS (long_volume - short_volume) STORED,
    source TEXT DEFAULT 'exchange',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, trade_date, contract_code, member_name)
);

CREATE INDEX IF NOT EXISTS idx_position_detail_date ON position_detail(trade_date);
CREATE INDEX IF NOT EXISTS idx_position_detail_contract ON position_detail(contract_code);
CREATE INDEX IF NOT EXISTS idx_position_detail_member ON position_detail(member_name);

CREATE TABLE IF NOT EXISTS download_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    data_type TEXT NOT NULL,
    product TEXT,
    start_date TEXT,
    end_date TEXT,
    records_downloaded INTEGER DEFAULT 0,
    status TEXT NOT NULL,              -- success, failed, partial
    error_message TEXT,
    duration_seconds REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_download_log_exchange_type ON download_log(exchange, data_type);
CREATE INDEX IF NOT EXISTS idx_download_log_status ON download_log(status);

CREATE TABLE IF NOT EXISTS download_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    data_type TEXT NOT NULL,
    product TEXT,
    last_date TEXT,                    -- last successfully downloaded date
    total_records INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, data_type, product)
);

CREATE TABLE IF NOT EXISTS download_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    data_type TEXT NOT NULL,
    product TEXT,
    url TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_checksums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    data_type TEXT NOT NULL,
    product TEXT,
    trade_date TEXT NOT NULL,
    file_name TEXT,
    checksum TEXT NOT NULL,
    file_size INTEGER,
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, data_type, product, trade_date)
);

CREATE TABLE IF NOT EXISTS data_quality_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    check_type TEXT NOT NULL,          -- row_count, null_check, range_check, dup_check
    status TEXT NOT NULL,              -- pass, fail
    detail TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quality_checks_table ON data_quality_checks(table_name);

-- ============================================
-- Metadata: Exchange, Product, Contract (for maintenance system)
-- ============================================

-- 交易所配置
CREATE TABLE IF NOT EXISTS exchange_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange_code TEXT NOT NULL UNIQUE,  -- CFFEX, SHFE, DCE, CZCE, INE
    exchange_name TEXT NOT NULL,
    trading_hours TEXT,                   -- JSON: {"morning": "09:00-11:30", "afternoon": "13:00-15:00"}
    timezone TEXT DEFAULT 'Asia/Shanghai',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exchange_active ON exchange_config(is_active);

-- 品种配置
CREATE TABLE IF NOT EXISTS product_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange_code TEXT NOT NULL,         -- REFERENCES exchange_config(exchange_code)
    product_code TEXT NOT NULL,           -- IM, IF, IC, IH, MO, HO, AU, AG
    product_name TEXT NOT NULL,
    product_type TEXT,                    -- index_future, commodity_future, option
    multiplier REAL,                      -- 合约乘数 (e.g. 100 for MO)
    price_tick REAL,                      -- 最小变动价位 (e.g. 0.2)
    margin_rate REAL,                     -- 保证金率 (e.g. 0.12)
    option_style TEXT,                    -- European / American (for options)
    is_tracked INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange_code, product_code)
);

CREATE INDEX IF NOT EXISTS idx_product_exchange ON product_config(exchange_code);

-- 合约信息 (已有 contracts 表，此表用于维护系统跟踪的合约)
CREATE TABLE IF NOT EXISTS contract_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_code TEXT NOT NULL UNIQUE,   -- IM2506, MO2506-C-8500
    exchange_code TEXT,
    product_code TEXT,
    contract_type TEXT,                   -- futures, option_call, option_put
    underlying_contract TEXT,
    strike_price REAL,
    listing_date TEXT,                    -- YYYY-MM-DD
    last_trade_date TEXT,                 -- YYYY-MM-DD (最后交易日)
    delivery_date TEXT,                   -- YYYY-MM-DD (交割日)
    expiry_date TEXT,                     -- YYYY-MM-DD
    delisting_date TEXT,                  -- YYYY-MM-DD
    multiplier REAL,
    tick_size REAL,
    status TEXT DEFAULT 'active',         -- active, expired, suspended
    is_tracked INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contract_info_product ON contract_info(product_code);
CREATE INDEX IF NOT EXISTS idx_contract_info_expiry ON contract_info(expiry_date);
CREATE INDEX IF NOT EXISTS idx_contract_info_tracked ON contract_info(is_tracked);

-- ============================================
-- Trade Calendar (Chinese futures exchanges)
-- ============================================

CREATE TABLE IF NOT EXISTS trade_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,             -- YYYY-MM-DD
    exchange_code TEXT NOT NULL DEFAULT 'ALL',  -- ALL 或特定交易所
    product_code TEXT NOT NULL DEFAULT '',      -- 产品代码（空表示交易所级）
    is_holiday INTEGER DEFAULT 0,         -- 1=节假日/非交易日
    holiday_name TEXT,                    -- 节假日名称
    day_of_week INTEGER DEFAULT 0,        -- 星期几 (1=Mon..7=Sun)
    is_weekend INTEGER DEFAULT 0,         -- 是否为周末
    is_workday INTEGER DEFAULT 0,         -- 是否为调休工作日
    special_flag TEXT DEFAULT '',         -- 特殊标志
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trade_date, exchange_code, product_code)
);

CREATE INDEX IF NOT EXISTS idx_calendar_date ON trade_calendar(trade_date);
CREATE INDEX IF NOT EXISTS idx_calendar_exchange ON trade_calendar(exchange_code);
CREATE INDEX IF NOT EXISTS idx_calendar_product ON trade_calendar(product_code);

-- ============================================
-- Special Date Override (overrides auto-generated calendar)
-- ============================================

CREATE TABLE IF NOT EXISTS special_date_override (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    override_type TEXT NOT NULL,           -- holiday, workday, half_day
    reason TEXT,
    operator TEXT DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_special_date_exchange ON special_date_override(exchange_code);
CREATE INDEX IF NOT EXISTS idx_special_date_date ON special_date_override(trade_date);

-- Product listing dates (when each product became available)
CREATE TABLE IF NOT EXISTS product_listing_dates (
    product_code TEXT PRIMARY KEY,
    product_name TEXT,
    exchange_code TEXT,
    listing_date TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Data Catalog (for maintenance system)
-- ============================================

CREATE TABLE IF NOT EXISTS data_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_name TEXT NOT NULL,          -- "中金所-IM-日线"
    exchange_code TEXT NOT NULL,         -- CFFEX, SHFE, DCE, CZCE, INE
    product_code TEXT,                   -- IM, MO, AU, AG
    contract_code TEXT,                  -- 可选，为空表示该品种所有合约
    data_type TEXT NOT NULL,             -- daily, minute, top20_holdings, contract_info
    frequency TEXT,                      -- 1min, 5min, daily（仅分钟线需要）
    data_source TEXT,                    -- tushare, cffex_official, shfe_official
    is_enabled INTEGER DEFAULT 1,        -- 1=enabled, 0=disabled
    sync_mode TEXT DEFAULT 'incremental', -- incremental, full
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange_code, product_code, contract_code, data_type, frequency)
);

CREATE INDEX IF NOT EXISTS idx_catalog_enabled ON data_catalog(is_enabled);
CREATE INDEX IF NOT EXISTS idx_catalog_exchange ON data_catalog(exchange_code);
CREATE INDEX IF NOT EXISTS idx_catalog_product ON data_catalog(product_code);

-- ============================================
-- Data Status (for sync engine)
-- ============================================

-- 本地数据状态（记录每个 catalog 的同步状态）
CREATE TABLE IF NOT EXISTS data_status_local (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id INTEGER REFERENCES data_catalog(id),
    latest_date TEXT,                    -- 本地最新日期 (YYYY-MM-DD)
    earliest_date TEXT,                  -- 本地最早日期 (YYYY-MM-DD)
    total_records INTEGER DEFAULT 0,     -- 总记录数
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(catalog_id)
);

CREATE INDEX IF NOT EXISTS idx_status_local_catalog ON data_status_local(catalog_id);

-- 远程数据状态快照（通过数据源查询或交易日历推断）
CREATE TABLE IF NOT EXISTS data_status_remote (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id INTEGER REFERENCES data_catalog(id),
    latest_date TEXT,                    -- 远程最新日期 (YYYY-MM-DD)
    total_available_days INTEGER,        -- 应有交易日总数
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(catalog_id)
);

CREATE INDEX IF NOT EXISTS idx_status_remote_catalog ON data_status_remote(catalog_id);

-- ============================================
-- Sync Task (for checkpoint management)
-- ============================================

CREATE TABLE IF NOT EXISTS sync_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id INTEGER REFERENCES data_catalog(id),
    task_name TEXT,                      -- 任务名称
    status TEXT DEFAULT 'pending',       -- pending, running, completed, failed
    checkpoint_data TEXT,                -- JSON 格式的断点数据
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sync_task_catalog ON sync_task(catalog_id);
CREATE INDEX IF NOT EXISTS idx_sync_task_status ON sync_task(status);

-- ============================================
-- Data Health Snapshot (for monitoring)
-- ============================================

CREATE TABLE IF NOT EXISTS data_health_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id INTEGER REFERENCES data_catalog(id),
    snapshot_date TEXT NOT NULL,           -- YYYY-MM-DD
    missing_days INTEGER DEFAULT 0,        -- 缺失天数
    missing_dates TEXT,                    -- JSON 格式的缺失日期列表
    data_quality_score REAL DEFAULT 0.0,   -- 数据质量分数 (0-100)
    completeness_pct REAL DEFAULT 0.0,     -- 完整性百分比 (0-100)
    consistency_status TEXT DEFAULT 'unknown', -- consistent, minor_issues, inconsistent
    last_sync_status TEXT DEFAULT 'unknown',   -- completed, failed, running, never_synced
    last_sync_error TEXT,                  -- 最后一次同步错误信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(catalog_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_health_snapshot_catalog ON data_health_snapshot(catalog_id);
CREATE INDEX IF NOT EXISTS idx_health_snapshot_date ON data_health_snapshot(snapshot_date);

-- ============================================
-- Data Diff Log (for cross-source validation)
-- ============================================

CREATE TABLE IF NOT EXISTS data_diff_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id INTEGER REFERENCES data_catalog(id),
    trade_date TEXT NOT NULL,              -- YYYY-MM-DD
    source_a TEXT NOT NULL,                -- 数据源 A 名称
    source_b TEXT NOT NULL,                -- 数据源 B 名称
    field_name TEXT NOT NULL,              -- 比较字段名 (close, volume, etc.)
    value_a REAL,                          -- 数据源 A 的值
    value_b REAL,                          -- 数据源 B 的值
    deviation_pct REAL,                    -- 偏差百分比
    threshold_pct REAL DEFAULT 0.5,        -- 告警阈值
    is_alert INTEGER DEFAULT 0,            -- 1=触发告警, 0=正常
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_diff_log_catalog ON data_diff_log(catalog_id);
CREATE INDEX IF NOT EXISTS idx_diff_log_date ON data_diff_log(trade_date);
CREATE INDEX IF NOT EXISTS idx_diff_log_alert ON data_diff_log(is_alert);

-- ============================================
-- Main Contract Mapping (主力合约映射)
-- ============================================

CREATE TABLE IF NOT EXISTS main_contract_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    contract_code TEXT NOT NULL,
    method TEXT DEFAULT 'manual',           -- volume_oi, rule, manual
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_main_contract_product ON main_contract_map(product_code);
CREATE INDEX IF NOT EXISTS idx_main_contract_date ON main_contract_map(trade_date);

-- ============================================
-- Trading Hours Template (交易时间模板)
-- ============================================

CREATE TABLE IF NOT EXISTS trading_hours_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id TEXT NOT NULL UNIQUE,       -- e.g. "cffex_index_futures"
    template_name TEXT NOT NULL,            -- "中金所股指期货"
    exchange_code TEXT NOT NULL,
    product_type TEXT NOT NULL,             -- index_future, index_option, commodity_future
    normal_schedule TEXT NOT NULL,           -- JSON: [{"start":"09:30","end":"11:30"},{"start":"13:00","end":"15:00"}]
    night_schedule TEXT,                    -- JSON for night session (e.g. SHFE night)
    pre_open TEXT,                          -- JSON: {"start":"09:25","end":"09:30"} (集合竞价)
    pre_close TEXT,                         -- JSON: {"start":"14:57","end":"15:00"} (收盘集合竞价)
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trading_hours_exchange ON trading_hours_template(exchange_code);

-- ============================================
-- Product Trading Hours (per-product override)
-- ============================================

CREATE TABLE IF NOT EXISTS product_trading_hours (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange_code TEXT NOT NULL,
    product_code TEXT NOT NULL,
    template_id TEXT REFERENCES trading_hours_template(template_id),
    effective_date TEXT,                    -- 生效日期 (NULL=立即生效)
    schedule_override TEXT,                 -- JSON override (NULL=使用模板)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange_code, product_code, effective_date)
);

-- ============================================
-- System Config (API tokens, shared settings)
-- ============================================

CREATE TABLE IF NOT EXISTS system_config (
    config_key TEXT PRIMARY KEY,            -- e.g. 'tushare.token', 'wind.username'
    config_value TEXT,                      -- JSON-compatible value
    config_type TEXT DEFAULT 'secret',      -- secret, text, number, json
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_config_type ON system_config(config_type);

-- ============================================
-- Sync Audit Log (structured sync operation records)
-- ============================================

CREATE TABLE IF NOT EXISTS sync_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,                          -- Celery task ID
    task_name TEXT NOT NULL,               -- e.g. 'mo-iv-sync', 'mo-underlying-sync'
    sync_mode TEXT NOT NULL,               -- calendar-driven, full, incremental
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    success INTEGER DEFAULT 0,             -- 1=success, 0=failure
    records_fetched INTEGER DEFAULT 0,
    error_message TEXT,
    exchange TEXT,                         -- CFFEX, SHFE, etc.
    product TEXT,                          -- MO, HO, IO, etc.
    trade_date TEXT,                       -- Target trading date
    duration_seconds REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_task ON sync_audit_log(task_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_date ON sync_audit_log(trade_date);
CREATE INDEX IF NOT EXISTS idx_audit_log_success ON sync_audit_log(success);
