-- QuestDB schema for time-series market data
-- Optimized for high-performance time-series queries
-- Tables created via HTTP exec endpoint on QuestDB startup

-- 日线行情 (daily quotes)
CREATE TABLE IF NOT EXISTS daily_quotes (
    ts TIMESTAMP,                                -- 交易日 00:00 UTC
    exchange SYMBOL,                             -- CFFEX, SHFE, etc.
    contract_code SYMBOL,
    product_code SYMBOL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    settle DOUBLE,
    prev_settle DOUBLE,
    volume LONG,
    turnover DOUBLE,
    open_interest LONG,
    daily_change DOUBLE,
    daily_change_pct DOUBLE,
    amplitude DOUBLE,
    source SYMBOL                                -- exchange, tushare, akshare
) TIMESTAMP(ts) PARTITION BY YEAR;

-- 指数分钟线
CREATE TABLE IF NOT EXISTS index_minute (
    ts TIMESTAMP,                                -- 时间戳（主键）
    exchange SYMBOL,                             -- CFFEX
    contract_code SYMBOL,
    product_code SYMBOL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume LONG,
    turnover DOUBLE,
    open_interest LONG,
    vwap DOUBLE,
    source SYMBOL
) TIMESTAMP(ts) PARTITION BY DAY;

-- 期货分钟线
CREATE TABLE IF NOT EXISTS future_minute (
    ts TIMESTAMP,
    exchange SYMBOL,
    contract_code SYMBOL,
    product_code SYMBOL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume LONG,
    turnover DOUBLE,
    open_interest LONG,
    source SYMBOL
) TIMESTAMP(ts) PARTITION BY DAY;

-- 期权分钟线（含隐含波动率）
CREATE TABLE IF NOT EXISTS option_minute (
    ts TIMESTAMP,
    exchange SYMBOL,
    contract_code SYMBOL,
    underlying SYMBOL,
    strike_price DOUBLE,
    option_type SYMBOL,                          -- CALL, PUT
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume LONG,
    implied_volatility DOUBLE,
    source SYMBOL
) TIMESTAMP(ts) PARTITION BY DAY;

-- 机构持仓前20名
CREATE TABLE IF NOT EXISTS top20_holdings (
    ts TIMESTAMP,
    exchange SYMBOL,
    contract_code SYMBOL,
    product_code SYMBOL,
    member_name SYMBOL,
    rank LONG,
    long_volume LONG,
    short_volume LONG,
    long_change LONG,
    short_change LONG
) TIMESTAMP(ts) PARTITION BY DAY;
