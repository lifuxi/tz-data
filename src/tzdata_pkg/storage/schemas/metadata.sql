-- tzdata_metadata: Metadata and task management for data maintenance system
-- PostgreSQL schema

-- 交易所配置
CREATE TABLE IF NOT EXISTS exchange_config (
    id SERIAL PRIMARY KEY,
    exchange_code VARCHAR(10) UNIQUE NOT NULL,  -- CFFEX, SHFE, DCE, CZCE, INE
    exchange_name VARCHAR(50) NOT NULL,
    trading_hours JSONB,                         -- {"morning": "09:00-11:30", "afternoon": "13:00-15:00"}
    timezone VARCHAR(20) DEFAULT 'Asia/Shanghai',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 品种配置
CREATE TABLE IF NOT EXISTS product_config (
    id SERIAL PRIMARY KEY,
    exchange_code VARCHAR(10) REFERENCES exchange_config(exchange_code),
    product_code VARCHAR(20) NOT NULL,           -- IM, IF, IC, IH, MO, HO
    product_name VARCHAR(50) NOT NULL,
    product_type VARCHAR(20),                    -- index_future, commodity_future, option
    is_tracked BOOLEAN DEFAULT TRUE,             -- 是否跟踪
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange_code, product_code)
);

-- 合约信息
CREATE TABLE IF NOT EXISTS contract_info (
    id SERIAL PRIMARY KEY,
    contract_code VARCHAR(30) UNIQUE NOT NULL,   -- IM2506, MO2506-C-8500
    exchange_code VARCHAR(10) REFERENCES exchange_config(exchange_code),
    product_code VARCHAR(20),
    contract_type VARCHAR(20),                   -- futures, option_call, option_put
    underlying_contract VARCHAR(30),
    strike_price DECIMAL(18,4),
    listing_date DATE,
    expiry_date DATE,
    delisting_date DATE,
    multiplier DECIMAL(18,4),
    tick_size DECIMAL(18,4),
    status VARCHAR(20) DEFAULT 'active',         -- active, expired, suspended
    is_tracked BOOLEAN DEFAULT FALSE,            -- 用户手动设置跟踪
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_contract_product ON contract_info(product_code);
CREATE INDEX idx_contract_expiry ON contract_info(expiry_date);

-- 数据目录（用户需要跟踪的数据项）
CREATE TABLE IF NOT EXISTS data_catalog (
    id SERIAL PRIMARY KEY,
    catalog_name VARCHAR(100) NOT NULL,          -- "中金所-IM-日线"
    exchange_code VARCHAR(10) REFERENCES exchange_config(exchange_code),
    product_code VARCHAR(20),
    contract_code VARCHAR(30),                   -- 可选，为空表示该品种所有合约
    data_type VARCHAR(30) NOT NULL,              -- daily, minute, top20_holdings, contract_info
    frequency VARCHAR(10),                       -- 1min, 5min, daily（仅分钟线需要）
    data_source VARCHAR(30),                     -- tushare, cffex_official, shfe_official
    is_enabled BOOLEAN DEFAULT TRUE,
    sync_mode VARCHAR(20) DEFAULT 'incremental', -- incremental, full
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange_code, product_code, contract_code, data_type, frequency)
);

CREATE INDEX idx_catalog_enabled ON data_catalog(is_enabled);

-- 本地数据状态快照
CREATE TABLE IF NOT EXISTS data_status_local (
    id SERIAL PRIMARY KEY,
    catalog_id INTEGER REFERENCES data_catalog(id),
    latest_date DATE,                            -- 本地最新日期
    earliest_date DATE,                          -- 本地最早日期
    total_records INTEGER,                       -- 总记录数
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(catalog_id)
);

-- 远程数据状态快照（通过数据源查询或交易日历推断）
CREATE TABLE IF NOT EXISTS data_status_remote (
    id SERIAL PRIMARY KEY,
    catalog_id INTEGER REFERENCES data_catalog(id),
    latest_date DATE,                            -- 远程最新日期
    total_available_days INTEGER,                -- 应有交易日总数
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(catalog_id)
);

-- 数据健康快照（综合状态，供前端快速展示）
CREATE TABLE IF NOT EXISTS data_health_snapshot (
    id SERIAL PRIMARY KEY,
    catalog_id INTEGER REFERENCES data_catalog(id),
    snapshot_date DATE DEFAULT CURRENT_DATE,
    missing_days INTEGER,                        -- 缺失天数
    missing_dates JSONB,                         -- ["2026-04-29", "2026-04-30"]
    data_quality_score DECIMAL(5,2),             -- 0-100分
    completeness_pct DECIMAL(5,2),               -- 完整度百分比
    consistency_status VARCHAR(20),              -- consistent, inconsistent, unknown
    last_sync_status VARCHAR(20),                -- success, failed, pending
    last_sync_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_health_snapshot_date ON data_health_snapshot(snapshot_date);

-- 同步任务记录
CREATE TABLE IF NOT EXISTS sync_task (
    id SERIAL PRIMARY KEY,
    task_uuid UUID UNIQUE NOT NULL,
    catalog_id INTEGER REFERENCES data_catalog(id),
    task_type VARCHAR(30) NOT NULL,              -- incremental_sync, full_sync, statement_parse
    status VARCHAR(20) DEFAULT 'pending',        -- pending, running, success, failed, cancelled
    priority INTEGER DEFAULT 5,                  -- 1-10，数字越小优先级越高
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    progress_pct DECIMAL(5,2),                   -- 进度百分比
    records_fetched INTEGER,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    checkpoint_data JSONB,                       -- 断点续传信息 {"last_date": "2026-04-28"}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_status ON sync_task(status);
CREATE INDEX idx_task_created ON sync_task(created_at);

-- 任务日志
CREATE TABLE IF NOT EXISTS sync_task_log (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES sync_task(id),
    log_level VARCHAR(10),                       -- INFO, WARN, ERROR
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_log_task ON sync_task_log(task_id);

-- 数据差异对比日志（多数据源交叉验证）
CREATE TABLE IF NOT EXISTS data_diff_log (
    id SERIAL PRIMARY KEY,
    catalog_id INTEGER REFERENCES data_catalog(id),
    trade_date DATE NOT NULL,
    source_a VARCHAR(30),                        -- tushare
    source_b VARCHAR(30),                        -- cffex_official
    field_name VARCHAR(30),                      -- close, volume
    value_a DECIMAL(18,4),
    value_b DECIMAL(18,4),
    deviation_pct DECIMAL(8,4),                  -- 偏差百分比
    threshold_pct DECIMAL(8,4) DEFAULT 0.5,      -- 告警阈值
    is_alert BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_diff_log_date ON data_diff_log(trade_date);

-- 账单解析错误记录
CREATE TABLE IF NOT EXISTS statement_parse_error (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER,                             -- 关联bills表
    error_type VARCHAR(30),                      -- format_error, balance_mismatch, missing_field
    error_row INTEGER,
    error_message TEXT,
    raw_line TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
