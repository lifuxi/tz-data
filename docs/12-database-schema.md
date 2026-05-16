# 数据库表结构

> 版本：v0.7.0 | 最后更新：2026-05-15

数据目录：`C:\myspace\tz-data\data\`，通过 `TZ_DATA_DIR` 环境变量配置。

## 统一数据库架构

自 v0.3.0 起，tz-data 将 12 个分散的数据库整合为 3 个统一 SQLite 数据库（WAL 模式）。

### 数据库总览

| 数据库文件 | 用途 | 核心表数 | 说明 |
|-----------|------|---------|------|
| `tzdata_market.db` | 行情、持仓、合约、元数据 | ~20 | 整合自 cffex.db + shfe.db |
| `tzdata_trading.db` | 账单、交易、账户、策略 | ~30 | 整合自 bills.db + option_sim.db |
| `tzdata_analysis.db` | 机构特征、信号 | ~18 | 整合自 institution.db + tushare.db |

---

## tzdata_market.db

### 核心数据表

| 表名 | 行数 | 说明 |
|------|------|------|
| `daily_quotes` | ~967K | 统一日线行情（CFFEX + SHFE） |
| `position_detail` | ~639K | 机构持仓排名 |
| `contracts` | ~106 | 合约基本信息 |
| `cffex_daily_settlement` | ~889K | 中金所每日结算价 |
| `mo_minute_quotes` | — | MO 期权分钟 K 线 |

### 行情表 `daily_quotes`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| exchange | TEXT | CFFEX/SHFE/DCE/CZCE/INE |
| contract_code | TEXT | 合约代码 |
| trade_date | TEXT | 交易日期 |
| open/high/low/close | REAL | 价格 |
| settle/prev_settle | REAL | 结算价/昨结算 |
| volume | INTEGER | 成交量 |
| turnover | REAL | 成交额 |
| open_interest | INTEGER | 持仓量 |
| daily_change/daily_change_pct | REAL | 涨跌/涨跌幅 |
| source | TEXT | exchange/tushare/akshare |

### 持仓表 `position_detail`

| 字段 | 类型 | 说明 |
|------|------|------|
| exchange/trade_date/contract_code | TEXT | 交易所/日期/合约 |
| member_name | TEXT | 会员名称 |
| long_volume/short_volume | INTEGER | 多/空持仓 |
| long_change/short_change | INTEGER | 多/空变化 |
| net_position | INTEGER | 净持仓 |
| rank | INTEGER | 排名 |

### 维护管理表

| 表名 | 说明 |
|------|------|
| `exchange_config` | 交易所配置 |
| `product_config` | 品种配置 |
| `contract_info` | 合约维护信息 |
| `data_catalog` | 数据目录 |
| `data_status_local` | 本地数据状态 |
| `data_status_remote` | 远程数据状态 |
| `data_health_snapshot` | 健康快照 |
| `sync_task` | 同步任务记录 |
| `trade_calendar` | 交易日历 |
| `special_dates` | 特殊日期覆盖 |
| `main_contracts` | 主力合约 |
| `trading_hours_templates` | 交易时间模板 |
| `trading_hours_sessions` | 时段详情 |

---

## tzdata_trading.db

### 核心数据表

| 表名 | 行数 | 说明 |
|------|------|------|
| `cffex_daily_settlement` | ~889K | 中金所每日结算 |
| `trades` | ~13.5K | 交易明细（账单解析） |
| `matched_trades` | ~9.9K | 开-平仓配对 |
| `trade_performance` | ~9.9K | 交易绩效分析 |
| `strategy_performance_summary` | 286 | 策略维度汇总 |
| `option_sim_iv_series` | ~30K | 期权 IV 序列 |

### 交易明细表 `trades`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| account_id | TEXT | 账户 ID |
| trade_date | TEXT | 交易日期 |
| exchange/product/instrument | TEXT | 交易所/品种/合约 |
| direction | TEXT | 方向（买/卖） |
| offset_flag | TEXT | 开平标志（open/close/平今/平昨） |
| volume | INTEGER | 手数 |
| price | REAL | 价格 |
| commission | REAL | 手续费 |
| premium | REAL | 权利金 |

### 配对交易表 `matched_trades`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| instrument/exchange/product | TEXT | 合约信息 |
| is_option | INTEGER | 是否期权 |
| open_trade_id/open_date/open_price/open_volume | — | 开仓信息 |
| open_direction/open_premium | — | 开仓方向/权利金 |
| close_trade_id/close_date/close_price/close_volume | — | 平仓信息 |
| close_premium | REAL | 平仓权利金 |
| holding_days | INTEGER | 持仓天数 |
| price_pnl/premium_pnl/money_pnl | REAL | 各类盈亏 |
| multiplier | INTEGER | 合约乘数 |
| commission/net_pnl | REAL | 手续费/净盈亏 |
| status | TEXT | 状态 |

### 绩效分析表 `trade_performance`

| 字段 | 类型 | 说明 |
|------|------|------|
| matched_trade_id | INTEGER | 关联配对交易 |
| instrument/is_option | TEXT/INT | 合约信息 |
| open_date/close_date | TEXT | 开/平仓日期 |
| open_volume/open_direction | — | 开仓手数/方向 |
| money_pnl/premium_pnl/commission/net_pnl | REAL | 盈亏 |
| pnl_ratio | REAL | 盈亏比 |
| holding_days | INTEGER | 持仓天数 |
| underlying/expiry/option_type/strike | — | 期权信息 |
| delta/gamma/vega/theta | REAL | 希腊值 |
| close_year/close_month/close_quarter | INT | 平仓时间维度 |

### 账户与账单

| 表名 | 说明 |
|------|------|
| `bills` | 账单主表 |
| `bill_raw_sections` | 账单原始内容 |
| `futures_accounts` | 期货账户配置 |
| `statement_status` | 账单状态跟踪 |
| `account_cashflow` | 账户现金流 |
| `account_summary` | 账户月度汇总 |
| `positions_summary` | 持仓汇总 |

### 策略与期权

| 表名 | 说明 |
|------|------|
| `strategies` | 策略定义 |
| `strategy_summary` | 策略快照 |
| `backtest_results` | 回测结果 |
| `option_sim_iv_series` | IV 序列 |
| `option_sim_underlying_daily` | 标的日线 |
| `mo_minute_quotes` | MO 分钟行情 |
| `mo_contract_master` | MO 合约主表 |
| `jq_futures_data` | JoinMin 期货数据 |
| `jq_options_data` | JoinMin 期权数据 |

---

## tzdata_analysis.db

### 核心表

| 表名 | 行数 | 说明 |
|------|------|------|
| `feature_daily` | ~5.5K | 日度综合特征 |
| `model_validation_records` | 141 | 模型验证记录 |
| `market_regime` | ~480 | 市场状态分类 |
| `option_features` | ~1,822 | 期权特征 |
| `trading_signals` | 25 | 交易信号 |

### 日度特征表 `feature_daily`

| 字段 | 类型 | 说明 |
|------|------|------|
| product/trade_date | TEXT | 品种/日期 |
| net_position/net_ratio | INT/REAL | 净持仓/比率 |
| long_short_ratio | REAL | 多空比 |
| top5_net | INTEGER | 前5净持仓 |
| citic_net_change/yongan_net_change | INT | 中信/永安净变化 |
| divergence_index | REAL | 分歧指数 |
| top5_consensus | REAL | 前5共识度 |
| is_crowded | INTEGER | 是否拥挤 |

## 索引

主要索引分布在日期、合约代码、产品字段上，优化按时间和合约的查询性能。

## 备份

直接复制 `.db` 文件即可备份。WAL 模式下同时备份 `.db`、`.db-wal`、`.db-shm` 三个文件。

## 下一页

- [部署与运维](13-deployment.md) — 启动脚本和 FAQ
