-- tz-data Data Layer: New tables for bill fund flows, Greeks, index data, contracts
-- Idempotent: safe to run multiple times

-- 1. bill_fund_flows — 标准化资金流水表
-- 从账单 JSON 中解耦为独立行，支持高效查询和恒等式校验
CREATE TABLE IF NOT EXISTS bill_fund_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(id),
    trade_date TEXT NOT NULL,
    flow_type TEXT NOT NULL,       -- deposit/withdrawal/realized_pnl/unrealized_pnl/commission/premium_income/premium_expense/exercise_pnl/interest_income/interest_expense/other
    amount DECIMAL(20,4) NOT NULL, -- 正为收入，负为支出
    symbol TEXT,                   -- 关联合约（可空，出入金类为空）
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bff_bill_date ON bill_fund_flows(bill_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_bff_flow_type ON bill_fund_flows(flow_type, trade_date);

-- 2. option_greeks_daily — 期权希腊字母预计算表
-- 避免每次查询都重新计算 BS 模型
CREATE TABLE IF NOT EXISTS option_greeks_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    option_type TEXT,             -- CE/PE
    strike_price DECIMAL(20,4),
    expiry_date TEXT,
    underlying_price DECIMAL(20,4),  -- 标的收盘价
    iv DECIMAL(10,4),                -- 隐含波动率
    delta DECIMAL(20,4),
    gamma DECIMAL(20,4),
    vega DECIMAL(20,4),
    theta DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trade_date, symbol)
);

-- 3. daily_index_prices — 标的指数日线表
-- 提供基准对比（中证1000）和市场环境分析的数据源
CREATE TABLE IF NOT EXISTS daily_index_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_code TEXT NOT NULL,     -- 000852 = 中证1000, 000300 = 沪深300
    trade_date TEXT NOT NULL,
    open DECIMAL(20,4),
    high DECIMAL(20,4),
    low DECIMAL(20,4),
    close DECIMAL(20,4),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(index_code, trade_date)
);

-- 4. contract_expiry — 合约到期信息表
-- 支持持仓期限结构分析
CREATE TABLE IF NOT EXISTS contract_expiry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    exchange TEXT NOT NULL,
    product_type TEXT,            -- FUTURES/OPTION
    expiry_date TEXT NOT NULL,
    underlying_symbol TEXT,       -- 标的合约（期权用）
    strike_price DECIMAL(20,4),   -- 行权价（期权用）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
