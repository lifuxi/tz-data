# tz-data 数据库与表结构文档

> 数据目录：`C:\myspace\tz-data\data\`，通过 `TZ_DATA_DIR` 环境变量配置。
> 所有数据库均为 SQLite 格式。
> 最后更新：2026-05-13

---

## 统一数据库架构（v0.5.0+）

自 v0.3.0 起，tz-data 将 12 个分散的数据库整合为 3 个统一 SQLite 数据库。v0.5.0 新增维护管理系统（数据目录、同步引擎、交易日历、账户凭证等）。

### 数据库总览

| 数据库文件 | 用途 | 核心表数 | 说明 |
|-----------|------|---------|------|
| `tzdata_market.db` | 行情、持仓、合约、元数据 | ~20 | 整合自 cffex.db + shfe.db + 新增维护表 |
| `tzdata_trading.db` | 账单、交易、账户、策略 | ~30 | 整合自 bills.db + 新增维护表 |
| `tzdata_analysis.db` | 机构特征、信号 | ~18 | 整合自 institution.db + tushare.db |

---

## tzdata_market.db — 市场数据库

整合自 `cffex.db`、`shfe.db`、`cffex_minute_data.db`，并新增维护管理表。

### 核心数据表

| 表名 | 行数 | 说明 |
|------|------|------|
| `daily_quotes` | ~967K | 统一日线行情（CFFEX + SHFE） |
| `position_detail` | ~639K | 机构持仓排名 |
| `contracts` | 106 | 合约基本信息 |
| `minute_quotes` | 720 | 分钟K线（样本） |
| `cffex_daily_settlement` | ~889K | 中金所每日结算价 |
| `settlement_prices` | - | 结算价（预留） |
| `download_log` | - | 下载日志 |
| `download_progress` | - | 下载进度 |
| `download_failures` | - | 下载失败记录 |
| `file_checksums` | - | 文件校验 |
| `data_quality_checks` | - | 数据质量检查 |

### 维护管理表（v0.5.0 新增）

| 表名 | 说明 |
|------|------|
| `exchange_config` | 交易所配置（CFFEX/SHFE/DCE/CZCE/INE） |
| `product_config` | 品种配置（交易所 × 品种） |
| `contract_info` | 合约维护信息（跟踪状态、上市/到期日期） |
| `data_catalog` | 数据目录（用户跟踪的数据项） |
| `data_status_local` | 本地数据状态（每个 catalog 最新同步日期） |
| `data_status_remote` | 远程数据状态快照 |
| `data_health_snapshot` | 数据健康快照（质量评分、完整性） |
| `sync_task` | 同步任务记录（含断点续传） |
| `trade_calendar` | 中国期货交易日历（2025-2026 节假日） |
| `data_diff_log` | 跨数据源差异对比日志 |

### `daily_quotes` 统一行情表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| exchange | TEXT | CFFEX, SHFE, DCE, CZCE, INE |
| contract_code | TEXT | 合约代码 |
| trade_date | TEXT | YYYY-MM-DD |
| open/high/low/close | REAL | 价格 |
| settle/prev_settle | REAL | 结算价/昨结算 |
| volume | INTEGER | 成交量 |
| turnover | REAL | 成交额 |
| open_interest | INTEGER | 持仓量 |
| daily_change/daily_change_pct | REAL | 涨跌/涨跌幅 |
| amplitude | REAL | 振幅 |
| source | TEXT | exchange, tushare, akshare |

### `position_detail` 机构持仓表

| 字段 | 类型 | 说明 |
|------|------|------|
| exchange/trade_date/contract_code | TEXT | 交易所/日期/合约 |
| member_name | TEXT | 会员名称（期货公司） |
| long_volume/short_volume | INTEGER | 多/空持仓 |
| long_change/short_change | INTEGER | 多/空变化 |
| net_position | INTEGER | 净持仓（计算列） |
| rank | INTEGER | 排名 |

### `trade_calendar` 交易日历表

| 字段 | 类型 | 说明 |
|------|------|------|
| trade_date | TEXT | YYYY-MM-DD, UNIQUE |
| exchange_code | TEXT | ALL 或具体交易所 |
| is_holiday | INTEGER | 1=节假日/非交易日 |
| holiday_name | TEXT | 节假日名称 |

#### `daily_quotes` 统一行情表

| 目标字段 | CFFEX 源字段 | SHFE 源字段 | 说明 |
|---------|-------------|-------------|------|
| exchange | (固定 'CFFEX') | (固定 'SHFE') | 交易所代码 |
| contract_code | instrument_id | instrument_id | 合约代码 |
| trade_date | trade_date | trade_date | 交易日期 |
| open | open_price | open_price | 开盘价 |
| high | high_price | high_price | 最高价 |
| low | low_price | low_price | 最低价 |
| close | close_price | close_price | 收盘价 |
| settle | settlement_price | settlement_price | 结算价 |
| prev_settle | pre_settle | pre_settlement | 昨结算 |
| volume | volume | volume | 成交量 |
| turnover | turnover | turnover | 成交额 |
| open_interest | open_interest | open_interest | 持仓量 |
| daily_change | change | change | 涨跌 |
| daily_change_pct | change_pct | change_pct | 涨跌幅 |
| source | 'exchange' | 'exchange' | 数据源 |

**产品分布**：IO (388K), MO (230K), HO (176K), AG (53K), AU (23K), AL (12K), IF/IH/IC (各11K) 等

### tzdata_trading.db — 交易数据库

整合自 `bills.db`、`option_sim.db`，并新增维护管理表。

| 表名 | 行数 | 说明 |
|------|------|------|
| `cffex_daily_settlement` | ~889K | 中金所每日结算 |
| `trades` | ~13.5K | 交易明细（从账单解析） |
| `matched_trades` | ~9.9K | 开-平仓配对 |
| `trade_performance` | ~9.9K | 交易表现分析（含希腊值） |
| `strategy_performance_summary` | 286 | 策略维度汇总 |
| `strategy_summary` | 54 | 策略快照 |
| `positions_summary` | 88 | 持仓汇总 |
| `account_summary` | 17 | 账户月度汇总 |
| `option_sim_iv_series` | ~30K | 期权隐含波动率序列 |
| `jq_futures_data` | ~3K | JoinMin 期货数据 |
| `jq_options_data` | ~30K | JoinMin 期权数据 |
| `bills` | - | 账单主表（解析后的账单记录） |
| `bill_raw_sections` | - | 账单原始内容 |
| `futures_accounts` | - | 期货账户配置（含 CFMMC 加密凭证） |
| `statement_status` | - | 账单状态跟踪（上传/解析/导入状态） |
| `account_cashflow` | - | 账户现金流 |
| `trade_comparison_analysis` | - | 实际 vs 虚拟平仓对比 |
| `strategies` | - | 策略定义 |
| `backtest_results` | - | 回测结果 |
| `option_sim_strategies` | - | 期权策略定义 |
| `option_sim_trades` | - | 期权模拟交易 |
| `paper_accounts` | - | 模拟账户 |
| `paper_position` | - | 模拟持仓 |
| `paper_trade` | - | 模拟交易记录 |
| `paper_order` | - | 模拟订单 |
| `reports` | 6 | 报告中心 |
| `report_templates` | 3 | 报告模板 |
| `risk_config` | 8 | 风控配置 |
| `risk_history` | - | 风控历史 |

### tzdata_analysis.db — 分析数据库

整合自 `institution.db`、`tushare.db`、`trading.db`（分析相关表）。

| 表名 | 行数 | 说明 |
|------|------|------|
| `feature_daily` | ~5.5K | 日度综合特征（品种级别，机构持仓衍生） |
| `model_validation_records` | 141 | 模型验证记录（AUC） |
| `institution_daily_features` | - | 机构日度特征（Schema 差异，需手动迁移） |
| `institution_master` | - | 机构主表（Schema 差异，需手动迁移） |
| `trading_signals` | - | 交易信号（Schema 差异，需手动迁移） |
| `market_regime` | - | 市场状态（Schema 差异，需手动迁移） |
| `option_features` | - | 期权特征（Schema 差异，需手动迁移） |
| `tushare_daily` | - | Tushare 日线（预留） |
| `tushare_minute` | - | Tushare 分钟线（预留） |
| `tushare_option` | - | Tushare 期权（预留） |

### 维护元数据（PostgreSQL，可选）

生产环境使用 PostgreSQL 存储维护元数据，SQLite 开发环境下直接读写 `tzdata_market.db`。

| 表名 | 说明 |
|------|------|
| `exchange_config` | 交易所配置 |
| `product_config` | 品种配置 |
| `contract_info` | 合约信息 |
| `data_catalog` | 数据目录 |
| `data_status_local` | 本地数据状态 |
| `data_status_remote` | 远程数据状态 |
| `data_health_snapshot` | 健康快照 |
| `sync_task` | 同步任务（含断点续传） |
| `sync_task_log` | 同步任务日志 |
| `data_diff_log` | 数据差异对比日志 |
| `statement_parse_error` | 账单解析错误记录 |

### 迁移说明

- **自动迁移**：行情、持仓、交易账单等核心数据已自动迁移完成
- **手动迁移**：部分机构分析表因源/目标 Schema 差异较大，需要编写专用迁移脚本
- **列名映射**：迁移过程中自动映射了列名（如 `instrument_id` → `contract_code`，`open_price` → `open` 等）
- **交易所代码**：从 CFFEX 来源的数据自动填充 `exchange='CFFEX'`，SHFE 来源填充 `exchange='SHFE'`

---

## 遗留数据库文档（供参考）

> 以下为 12 个旧数据库的文档，保留用于参考和手动迁移。

## 数据库总览

| 数据库文件 | 大小 | 用途 | 表数 |
|-----------|------|------|------|
| `bills.db` | 211 MB | 账单数据、交易记录、策略分析、模拟交易 | 55 |
| `cffex.db` | 301 MB | 中金所行情数据、持仓数据、用户与策略 | 28 |
| `cffex_holdings.db` | 4 KB | 中金所持仓（空库，已迁移至 cffex.db） | 0 |
| `cffex_minute_data.db` | 180 KB | 中金所分钟级行情 | 1 |
| `cffex_trading.db` | 132 KB | 中金所交易模拟（策略/订单/回测） | 6 |
| `institution.db` | 31 MB | 机构持仓分析、特征工程、交易信号 | 13 |
| `market_data.db` | 4 KB | 空库（预留） | 0 |
| `market_quotes.db` | 4 KB | 空库（预留） | 0 |
| `option_sim.db` | 4 KB | 期权模拟回测（空库，表在 bills.db 中） | 0 |
| `shfe.db` | 23 MB | 上期所行情数据（日K + 分钟 + 期权） | 5 |
| `trading.db` | 96 KB | 通用交易基础设施（合约/行情/日志） | 9 |
| `tushare.db` | 4 KB | 空库（预留，Tushare 数据未迁移） | 0 |

---

## 一、bills.db（账单数据库）

> 最大数据库，存储期货账单解析结果、交易记录、持仓汇总、策略表现、期权模拟等。

### 1.1 账户资金类

#### `account_cashflow` — 账户现金流记录
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | 自增主键 |
| time | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 时间戳 |
| type | TEXT | NOT NULL | 类型：deposit/withdrawal/trading_pnl/commission |
| amount | REAL | NOT NULL | 金额 |
| balance | REAL | | 余额 |
| description | TEXT | | 描述 |

**数据量**: 0 行

#### `account_summary` — 账户月度汇总
| 字段 | 类型 | 说明 |、
|------|------|------|
| id | INTEGER | PK |
| account_id | TEXT | 账户ID |
| year | INTEGER | 年份 |
| month | INTEGER | 月份 |
| start_date / end_date | TEXT | 起止日期 |
| balance_b_f | REAL | 期初余额 |
| balance_c_f | REAL | 期末余额 |
| deposit_withdrawal | REAL | 出入金 |
| total_pnl | REAL | 总盈亏 |
| accumulated_pnl | REAL | 累计盈亏 |
| exercise_pnl | REAL | 行权盈亏 |
| commission | REAL | 手续费 |
| client_equity | REAL | 客户权益 |
| margin_occupied | REAL | 占用保证金 |
| fund_available | REAL | 可用资金 |
| risk_degree | REAL | 风险度 |
| margin_call | REAL | 追加保证金 |
| premium_received / premium_paid | REAL | 权利金收/付 |
| market_value_long / short / equity | REAL | 市值（多/空/权益） |
| created_at | TIMESTAMP | 创建时间 |

**数据量**: 17 行

### 1.2 交易记录类

#### `trades` — 交易明细（核心表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| account_id | TEXT | 账户ID |
| year / month | INTEGER | 年/月 |
| trade_date | TEXT | 交易日期 |
| exchange | TEXT | 交易所 |
| product | TEXT | 品种 |
| instrument | TEXT | 合约代码 |
| direction | TEXT | 方向（买/卖） |
| offset_flag | TEXT | 开平标志 |
| volume | INTEGER | 手数 |
| price | REAL | 价格 |
| turnover | REAL | 成交额 |
| commission | REAL | 手续费 |
| total_pnl | REAL | 总盈亏 |
| premium | REAL | 权利金 |
| trade_id | TEXT | 交易编号 |
| position_type | TEXT | 持仓类型 |
| created_at | TIMESTAMP | 创建时间 |

**数据量**: 13,534 行

#### `trades_backup_20260331` — 交易备份（2026-03-31）
**数据量**: 4,598 行，字段同 `trades`

#### `matched_trades` — 配对交易（开仓-平仓配对）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| instrument / exchange / product | TEXT | 合约/交易所/品种 |
| is_option | INTEGER | 是否期权 |
| open_trade_id / open_date / open_price / open_volume | - | 开仓信息 |
| open_premium / open_direction | - | 开仓权利金/方向 |
| close_trade_id / close_date / close_price / close_volume | - | 平仓信息 |
| close_premium | REAL | 平仓权利金 |
| holding_days | INTEGER | 持仓天数 |
| price_pnl / premium_pnl / money_pnl | REAL | 价差盈亏/权利金盈亏/金额盈亏 |
| commission / net_pnl | REAL | 手续费/净盈亏 |
| status | TEXT | 状态 |

**数据量**: 9,861 行

#### `trade_performance` — 交易表现分析
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| matched_trade_id | INTEGER | 关联配对交易 |
| instrument | TEXT | 合约 |
| is_option | INTEGER | 是否期权 |
| open_date / close_date | TEXT | 开/平仓日期 |
| open_volume | INTEGER | 开仓手数 |
| open_direction | TEXT | 开仓方向 |
| money_pnl / premium_pnl / commission / net_pnl | REAL | 各类盈亏 |
| pnl_ratio | REAL | 盈亏比 |
| holding_days | INTEGER | 持仓天数 |
| underlying / expiry / option_type | TEXT | 标的/到期日/期权类型 |
| strike | REAL | 行权价 |
| delta / gamma / vega / theta | REAL | 希腊值 |
| strategy_type / strategy_id | - | 策略类型/ID |
| close_year / close_month / close_quarter | INTEGER | 平仓时间维度 |

**数据量**: 9,861 行

#### `trade_comparison_analysis` — 实际 vs 虚拟平仓对比
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| analysis_date | DATE | 分析日期 |
| instrument / exchange / product | TEXT | 合约信息 |
| is_option | INTEGER | 是否期权 |
| open_trade_id / open_date / open_price / open_volume | - | 开仓信息 |
| open_direction / open_premium | - | 方向/权利金 |
| actual_close_* | - | 实际平仓数据 |
| virtual_close_* | - | 虚拟（结算价）平仓数据 |
| actual_*_pnl / virtual_*_pnl | REAL | 实际/虚拟盈亏 |
| pnl_difference / pnl_difference_ratio | REAL | 差异/差异率 |
| holding_days | INTEGER | 持仓天数 |
| trade_type / comparison_result | TEXT | 类型/结果 |

**数据量**: 0 行

#### `trade_comparison_analysis_demo` — 对比分析演示数据
**数据量**: 1,783 行，为 `trade_comparison_analysis` 的子集字段

### 1.3 持仓类

#### `positions_summary` — 持仓汇总
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| account_id | TEXT | 账户ID |
| year / month | INTEGER | 年/月 |
| trade_date | TEXT | 交易日期 |
| exchange / product / instrument | TEXT | 合约信息 |
| long_position / avg_buy_price | - | 多头持仓/均价 |
| short_position / avg_sell_price | - | 空头持仓/均价 |
| prev_settlement / settlement_price | REAL | 昨结算/今结算 |
| accumulated_pnl | REAL | 累计盈亏 |
| margin_occupied | REAL | 占用保证金 |
| market_value_long / short | REAL | 多头/空头市值 |

**数据量**: 88 行

#### `positions_detail` / `position_detail` — 持仓明细
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| account_id | TEXT | 账户ID |
| year / month | INTEGER | 年/月 |
| trade_date | TEXT | 交易日期 |
| exchange / product / instrument | TEXT | 合约信息 |
| direction | TEXT | 方向 |
| position_type | TEXT | 持仓类型 |
| volume | INTEGER | 手数 |
| open_price / settlement_price / prev_settlement | REAL | 价格 |
| accumulated_pnl / mtm_pnl | REAL | 累计盈亏/逐日盈亏 |
| margin / market_value | REAL | 保证金/市值 |

**数据量**: `positions_detail` 873 行，`position_detail` 0 行

### 1.4 策略与回测类

#### `strategies` — 策略管理
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| name | TEXT | 策略名称 |
| grade | TEXT | 评级 |
| status | TEXT | 状态 |
| archived_at | TIMESTAMP | 归档时间 |
| description | TEXT | 描述 |

**数据量**: 3 行

#### `strategy_performance_summary` — 策略表现汇总
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| dimension_type / dimension_value | TEXT | 维度类型/值 |
| total_trades / winning_trades / losing_trades | INTEGER | 交易统计 |
| total_pnl / total_net_pnl | REAL | 总盈亏/净盈亏 |
| avg_pnl / avg_winning_pnl / avg_losing_pnl | REAL | 平均盈亏 |
| win_rate | REAL | 胜率 |
| profit_loss_ratio | REAL | 盈亏比 |
| avg_holding_days | REAL | 平均持仓天数 |

**数据量**: 286 行

#### `strategy_summary` — 策略快照
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| strategy_type / strategy_name | TEXT | 策略类型/名称 |
| underlying / expiry | TEXT | 标的/到期日 |
| legs_count | INTEGER | 腿数 |
| total_volume | INTEGER | 总手数 |
| net_premium | REAL | 净权利金 |
| risk_profile / description | TEXT | 风险特征/描述 |
| trade_ids | TEXT | 关联交易ID列表 |

**数据量**: 54 行

#### `strategy_grade_history` — 策略评级变更历史
**数据量**: 0 行

#### `strategy_archive_snapshot` — 策略归档快照
**数据量**: 0 行

#### `backtest_results` — 回测结果
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| strategy_name / underlying | TEXT | 策略名/标的 |
| parameters | TEXT | 参数（JSON） |
| start_date / end_date | DATE | 回测区间 |
| total_return / annual_return | REAL | 总收益/年化 |
| max_drawdown | REAL | 最大回撤 |
| sharpe_ratio | REAL | 夏普比率 |
| win_rate | REAL | 胜率 |
| total_trades | INTEGER | 总交易数 |
| net_pnl / commission | REAL | 净盈亏/手续费 |
| result_data | TEXT | 详细结果（JSON） |

**数据量**: 2 行

### 1.5 期权模拟类 (option_sim_*)

#### `option_sim_strategies` — 期权策略定义
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| name / strategy_type | VARCHAR | 策略名/类型 |
| underlying | VARCHAR | 标的 |
| legs_config | TEXT | 腿配置（JSON） |
| holding_period | VARCHAR | 持仓周期 |
| buy_price_rule / sell_price_rule | VARCHAR | 买卖价格规则 |
| strike_selection / strike_offset | - | 行权价选择/偏移 |
| quantity_config | TEXT | 数量配置 |
| fee_per_lot / slippage_ticks / impact_cost | - | 费用/滑点/冲击成本 |
| stop_loss_pct / take_profit_pct | REAL | 止损/止盈比例 |
| order_type | VARCHAR | 订单类型 |
| is_active | BOOLEAN | 是否启用 |

**数据量**: 2 行

#### `option_sim_backtests` — 期权回测任务
**数据量**: 0 行

#### `option_sim_trades` — 期权模拟交易
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| backtest_id | INTEGER | 回测ID |
| trade_date | DATE | 交易日期 |
| strategy_type / underlying | VARCHAR | 策略/标的 |
| symbol / expiry / option_type | VARCHAR | 合约信息 |
| direction | VARCHAR | 方向 |
| open_price / close_price | REAL | 开/平仓价格 |
| quantity | INTEGER | 数量 |
| pnl / pnl_pct | REAL | 盈亏/盈亏比 |
| delta / gamma / theta / vega | REAL | 希腊值 |
| exit_reason | VARCHAR | 退出原因 |

**数据量**: 0 行

#### `option_sim_iv_series` — 隐含波动率序列
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| underlying | VARCHAR | 标的 |
| trade_date / expiry | DATE | 日期/到期日 |
| strike | REAL | 行权价 |
| option_type | VARCHAR | 期权类型 |
| iv | REAL | 隐含波动率 |
| underlying_price | REAL | 标的价格 |
| source | VARCHAR | 数据源 |

**数据量**: 29,974 行

#### `option_sim_underlying_daily` — 期权标的日线
**数据量**: 0 行

#### `option_sim_market_env` — 期权市场环境分类
**数据量**: 0 行

#### `option_sim_optimization_tasks` — 参数优化任务
**数据量**: 0 行

#### `option_sim_reports` — 期权报告
**数据量**: 3 行

#### `option_sim_risk_rules` — 风控规则
**数据量**: 0 行

### 1.6 模拟交易类 (paper_* / sim_*)

#### `paper_accounts` — 模拟账户
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| name | TEXT | 账户名 |
| initial_capital / current_equity / cash | REAL | 初始资金/当前权益/现金 |

**数据量**: 1 行

#### `paper_orders` — 模拟订单
**数据量**: 0 行

#### `paper_positions` — 模拟持仓
**数据量**: 0 行

#### `paper_trades` — 模拟交易
**数据量**: 0 行

#### `paper_equity_curve` — 模拟权益曲线
**数据量**: 0 行

#### `sim_account` — 模拟账户（增强版）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| account_name | TEXT | 账户名 |
| initial_capital / current_equity | REAL | 资金 |
| available_cash / total_pnl / daily_pnl | REAL | 现金/盈亏 |
| margin_used / frozen_cash | REAL | 保证金 |
| total_assets / used_margin / available_margin | REAL | 资产/保证金 |
| maintenance_margin / liquidation_line | REAL | 维持保证金/强平线 |
| risk_level | REAL | 风险等级 |
| today_deposit_withdrawal | REAL | 今日出入金 |

**数据量**: 1 行

#### `sim_orders` — 模拟订单（增强版）
**数据量**: 0 行

#### `sim_positions` — 模拟持仓（增强版）
**数据量**: 0 行

### 1.7 中金所账单结算类

#### `cffex_daily_settlement` — 中金所每日结算数据
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| trade_date | TEXT | 交易日期 |
| instrument / product | TEXT | 合约/品种 |
| open_price / high_price / low_price | REAL | 价格 |
| close_price / settlement_price / prev_settlement | REAL | 收盘价/结算价/昨结算 |
| volume | INTEGER | 成交量 |
| turnover | REAL | 成交额 |
| open_interest | INTEGER | 持仓量 |
| change_open_interest | INTEGER | 持仓变化 |

**数据量**: 888,944 行

### 1.8 合约与工具类

#### `contracts` — 合约信息
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| contract_code | TEXT | 合约代码 |
| variety | TEXT | 品种 |
| exchange | TEXT | 交易所 |
| contract_type | TEXT | 合约类型 |
| multiplier | DECIMAL(10,2) | 合约乘数 |
| tick_size | DECIMAL(10,4) | 最小变动价位 |
| list_date / expire_date / last_trade_date | DATE | 上市/到期/最后交易日 |
| status | TEXT | 状态 |

**数据量**: 0 行

#### `instruments` — 金融工具
| 字段 | 类型 | 说明 |
|------|------|------|
| instrument_id | TEXT | PK |
| product_name | TEXT | 产品名称 |
| contract_type | TEXT | 合约类型 |
| contract_month | TEXT | 合约月份 |
| strike_price | DECIMAL(10,2) | 行权价 |
| call_or_put | TEXT | 认购/认沽 |
| listing_date / delisting_date | DATE | 上市/摘牌日 |
| status | TEXT | 状态 |

**数据量**: 0 行

#### `daily_quotes` — 日线行情
**数据量**: 0 行

#### `daily_equity_series` — 日权益序列
**数据量**: 0 行

### 1.9 报告与分析类

#### `reports` — 报告中心
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| title | TEXT | 标题 |
| report_type | TEXT | 报告类型 |
| status | TEXT | 状态 |
| config_json | TEXT | 配置（JSON） |
| file_path_html / file_path_pdf | TEXT | 文件路径 |
| file_size | INTEGER | 文件大小 |
| summary_json | TEXT | 摘要（JSON） |
| error_message | TEXT | 错误信息 |
| created_by | TEXT | 创建人 |

**数据量**: 6 行

#### `report_templates` — 报告模板
**数据量**: 3 行

#### `position_reports` — 持仓报告
**数据量**: 0 行

### 1.10 风控类

#### `risk_config` — 风控配置
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| key | TEXT | 配置键 |
| value | REAL | 配置值 |
| description | TEXT | 描述 |

**数据量**: 8 行

#### `risk_history` — 风控历史
**数据量**: 0 行

### 1.11 其他

#### `download_log` — 下载日志
**数据量**: 0 行

#### `analysis_cache` — 分析缓存
**数据量**: 0 行

#### `psychology_marks` — 心理标记
**数据量**: 0 行

#### `live_orders` — 实盘订单
**数据量**: 0 行

---

## 二、cffex.db（中金所数据库）

> 存储中金所（CFFEX）行情数据、持仓数据、用户与策略管理。

### 2.1 行情数据类

#### `daily_quotes` — 日线行情（核心表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| trade_date | DATE | 交易日期 |
| instrument_id | TEXT | 合约代码 |
| open_price / high_price / low_price | DECIMAL(15,4) | 开/高/低 |
| close_price | DECIMAL(15,4) | 收盘价 |
| settlement_price | DECIMAL(15,4) | 结算价 |
| volume | INTEGER | 成交量 |
| turnover | DECIMAL(20,2) | 成交额 |
| open_interest | INTEGER | 持仓量 |
| change / change_pct | - | 涨跌/涨跌幅 |
| adj_close | DECIMAL(15,4) | 复权收盘价 |

**数据量**: 860,226 行

#### `market_data_daily` — 日K线（简化版）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| datetime | TEXT | 日期时间 |
| contract_code | TEXT | 合约代码 |
| exchange / variety | TEXT | 交易所/品种 |
| open_price / high_price / low_price / close_price | REAL | 价格 |
| volume / open_interest / turnover | - | 成交量/持仓/成交额 |

**数据量**: 1,330 行

#### `market_data_1min / 5min / 15min / 30min / 60min` — 分钟K线
字段同 `market_data_daily`，增加 `datetime` 为分钟级精度。
**数据量**: 全部 0 行

#### `market_data_weekly / monthly` — 周K/月K
**数据量**: 全部 0 行

### 2.2 合约与工具

#### `contracts` — 合约信息
**数据量**: 106 行，字段同 bills.db 的 contracts

#### `instruments` — 金融工具
**数据量**: 10,178 行

### 2.3 持仓数据

#### `position_detail` — 持仓明细（机构持仓）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| trade_date | DATE | 交易日期 |
| instrument_id | TEXT | 合约代码 |
| member_name | TEXT | 会员名称（期货公司） |
| long_volume / short_volume | INTEGER | 多/空持仓 |
| long_change / short_change | INTEGER | 多/空变化 |

**数据量**: 639,319 行

### 2.4 策略与交易

#### `strategies` — 策略管理（增强版）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| name / description | TEXT | 名称/描述 |
| instrument | TEXT | 交易合约 |
| strategy_type | TEXT | 策略类型 |
| status | TEXT | 状态 |
| initial_capital | DECIMAL(15,2) | 初始资金 |
| max_position | INTEGER | 最大持仓 |
| stop_loss / take_profit | DECIMAL(5,4) | 止损/止盈 |
| code | TEXT | 策略代码 |
| config_json | TEXT | 配置（JSON） |
| total_pnl | DECIMAL(15,2) | 总盈亏 |
| win_rate | DECIMAL(5,2) | 胜率 |
| trade_count | INTEGER | 交易数 |
| max_drawdown | DECIMAL(10,4) | 最大回撤 |
| sharpe_ratio | DECIMAL(10,4) | 夏普比率 |
| last_run_at | TIMESTAMP | 最后运行时间 |

**数据量**: 2 行

#### `orders` — 订单
**数据量**: 0 行

#### `trades` — 交易记录
**数据量**: 0 行

#### `trading_positions` — 交易持仓
**数据量**: 0 行

#### `account_log` — 账户日志
**数据量**: 0 行

#### `signals` — 信号
**数据量**: 4 行

#### `backtests` — 回测任务
**数据量**: 0 行

### 2.5 用户管理

#### `users` — 用户表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| username | TEXT | 用户名 |
| email | TEXT | 邮箱 |
| password_hash | TEXT | 密码哈希 |
| role | TEXT | 角色 |
| is_active | BOOLEAN | 是否激活 |
| last_login | TIMESTAMP | 最后登录 |

**数据量**: 5 行

#### `user_sessions` — 用户会话
**数据量**: 0 行

#### `audit_log` / `audit_logs` — 审计日志
**数据量**: 0 行

### 2.6 配置与日志

#### `data_configs` — 数据配置
**数据量**: 24 行

#### `download_log` — 下载日志
**数据量**: 0 行

#### `task_execution_log` — 任务执行日志
**数据量**: 2 行

#### `data_quality_checks` — 数据质量检查
**数据量**: 0 行

#### `analysis_cache` — 分析缓存
**数据量**: 0 行

---

## 三、shfe.db（上期所数据库）

> 存储上期所（SHFE）行情数据，包括日线、分钟线和期权。

### 3.1 行情数据

#### `daily_quotes` — 日线行情
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| trade_date | DATE | 交易日期 |
| instrument_id | TEXT | 合约代码 |
| open_price / high_price / low_price | DECIMAL(15,4) | 价格 |
| close_price | DECIMAL(15,4) | 收盘价 |
| settlement_price | DECIMAL(15,4) | 结算价 |
| volume | INTEGER | 成交量 |
| turnover | DECIMAL(20,2) | 成交额 |
| open_interest | INTEGER | 持仓量 |
| change / change_pct | - | 涨跌/涨跌幅 |

**数据量**: 9,180 行

#### `shfe_minute_quotes` — 分钟行情
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| trade_date | DATE | 日期 |
| trade_time | TIME | 时间 |
| instrument_id | TEXT | 合约代码 |
| open_price / high_price / low_price / close_price | DECIMAL(15,4) | 价格 |
| volume / turnover / open_interest | - | 成交数据 |

**数据量**: 0 行

#### `shfe_option_quotes` — 期权行情
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| trade_date | DATE | 交易日期 |
| instrument_id | TEXT | 期权合约 |
| underlying | TEXT | 标的合约 |
| call_or_put | TEXT | 认购/认沽 |
| strike_price | DECIMAL(15,2) | 行权价 |
| expire_date | DATE | 到期日 |
| pre_settlement / settlement_price | DECIMAL(15,4) | 昨结算/今结算 |
| open_price / high_price / low_price / close_price | - | 价格 |
| volume / turnover / open_interest | - | 成交数据 |
| delta | DECIMAL(10,4) | Delta |
| implied_vol | DECIMAL(10,4) | 隐含波动率 |

**数据量**: 102,030 行

### 3.2 合约

#### `contracts` — 合约信息
**数据量**: 6 行

### 3.3 日志

#### `shfe_download_log` — 下载日志（SHFE 专用）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| download_date | DATE | 下载日期 |
| exchange | TEXT | 交易所 |
| instrument_id | TEXT | 合约 |
| data_type | TEXT | 数据类型 |
| status | TEXT | 状态 |
| error_message | TEXT | 错误信息 |
| record_count | INTEGER | 记录数 |
| source | TEXT | 数据源 |

**数据量**: 0 行

---

## 四、institution.db（机构持仓分析数据库）

> 存储机构（期货公司）持仓数据、特征工程、市场环境分类、交易信号等。

### 4.1 机构基础数据

#### `institution_master` — 机构主表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| canonical_name | TEXT | 标准名称 |
| institution_type | TEXT | 机构类型 |
| status | TEXT | 状态 |
| first_seen / last_seen | TEXT | 首次/最后出现日期 |

**数据量**: 340 行

#### `institution_name_mapping` — 机构名称映射
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| institution_id | INTEGER | 关联机构ID |
| alias_name | TEXT | 别名 |
| confidence | REAL | 匹配置信度 |
| source | TEXT | 来源 |
| verified | INTEGER | 是否已验证 |

**数据量**: 507 行

#### `institution_profiles` — 机构画像
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| institution_id | INTEGER | 机构ID |
| institution_name | TEXT | 机构名称 |
| product | TEXT | 品种 |
| trade_date | TEXT | 交易日期 |
| net_position | INTEGER | 净持仓 |
| total_volume | INTEGER | 总持仓量 |
| net_position_pref | REAL | 净持仓偏好 |
| trend_score | REAL | 趋势得分 |
| position_stability | REAL | 持仓稳定性 |
| n_day_win_rate | REAL | N日胜率 |
| concentration | REAL | 集中度 |
| behavior_synergy | REAL | 行为协同 |
| tags | TEXT | 标签 |
| smart_money | BOOLEAN | 是否聪明钱 |

**数据量**: 813 行

### 4.2 持仓时间序列

#### `cffex_holdings_continuous` — 中金所持仓连续序列
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| product | TEXT | 品种 |
| trade_date | TEXT | 交易日期 |
| contract | TEXT | 合约 |
| open / high / low / close | REAL | 价格 |
| settlement_price | REAL | 结算价 |
| volume | INTEGER | 成交量 |
| open_interest | INTEGER | 持仓量 |
| total_long / total_short | INTEGER | 总多/总空持仓 |
| net_position | INTEGER | 净持仓 |
| inst_count | INTEGER | 机构数量 |

**数据量**: 3,644 行

#### `institution_daily_features` — 机构日度特征
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| institution_id | INTEGER | 机构ID |
| product | TEXT | 品种 |
| trade_date | TEXT | 交易日期 |
| net_position | INTEGER | 净持仓 |
| long_volume / short_volume | INTEGER | 多/空持仓 |
| ewma_net_5 / ewma_net_20 | REAL | EWMA净持仓(5/20日) |
| ewma_change_10 | REAL | EWMA变化(10日) |
| trend_score / stability_score | REAL | 趋势/稳定性得分 |
| n_day_win_rate | REAL | N日胜率 |
| concentration | REAL | 集中度 |
| synergy | REAL | 协同度 |

**数据量**: 191,302 行

#### `feature_daily` — 日度综合特征（品种级别）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| product | TEXT | 品种 |
| trade_date | TEXT | 交易日期 |
| net_position | INTEGER | 净持仓 |
| net_ratio | REAL | 净持仓比率 |
| long_short_ratio | REAL | 多空比 |
| top5_net | INTEGER | 前5净持仓 |
| citic_net_change / yongan_net_change | INTEGER | 中信/永安净变化 |
| citic_vs_yongan | INTEGER | 中信vs永安 |
| smart_vs_contrarian | INTEGER | 聪明钱vs逆势者 |
| divergence_index | REAL | 分歧指数 |
| top5_consensus | REAL | 前5共识度 |
| net_percentile | REAL | 净持仓百分位 |
| is_crowded | INTEGER | 是否拥挤 |
| top3_long_conc / top3_short_conc | REAL | 前3多/空集中度 |
| net_change_ratio | REAL | 净变化比率 |

**数据量**: 5,498 行

### 4.3 信号与交易

#### `trading_signals` — 交易信号
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| signal_id | TEXT | 信号ID |
| name | TEXT | 信号名 |
| signal_type | TEXT | 信号类型 |
| product | TEXT | 品种 |
| direction | TEXT | 方向 |
| strength | REAL | 强度 |
| status | TEXT | 状态 |
| sharpe / max_drawdown / win_rate | - | 表现指标 |
| metadata_json | TEXT | 元数据（JSON） |

**数据量**: 25 行

#### `signal_triggers` — 信号触发记录
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| signal_id | TEXT | 信号ID |
| trade_date | TEXT | 交易日期 |
| direction | TEXT | 方向 |
| strength | REAL | 强度 |
| entry_price | REAL | 入场价格 |
| metadata_json | TEXT | 元数据 |

**数据量**: 23 行

### 4.4 市场环境与期权特征

#### `market_regime` — 市场状态分类
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| product | TEXT | 品种 |
| trade_date | TEXT | 交易日期 |
| regime | TEXT | 市场状态 |
| confidence | REAL | 置信度 |
| price / ma5 / ma20 / ma60 | REAL | 价格/均线 |
| volatility / atr / adx | REAL | 波动率/ATR/ADX |

**数据量**: 480 行

#### `option_features` — 期权特征
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| product | TEXT | 品种 |
| trade_date | TEXT | 交易日期 |
| pcr_volume / pcr_oi | REAL | 成交量/持仓量PCR |
| skew_value | REAL | 偏度值 |
| max_pain | REAL | 最大痛点 |
| max_pain_atm_dist | REAL | 最大痛点ATM距离 |
| total_call_oi / total_put_oi | INTEGER | 总认购/认沽持仓量 |
| total_call_volume / total_put_volume | INTEGER | 总认购/认沽成交量 |

**数据量**: 1,822 行

### 4.5 其他

#### `institution_lead_lag` — 机构领先滞后分析
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| leader / follower | TEXT | 领先/滞后机构 |
| product | TEXT | 品种 |
| lag_days | INTEGER | 滞后天数 |
| correlation / p_value | REAL | 相关系数/p值 |
| sample_size | INTEGER | 样本量 |
| leader_direction / follower_direction | TEXT | 方向 |
| metric | TEXT | 指标 |

**数据量**: 12 行

#### `model_validation_records` — 模型验证记录
| 字段 | 类型 | 说明 |
|------|------|------|
| product | TEXT | 品种 |
| trade_date | TEXT | 交易日期 |
| model_type | TEXT | 模型类型 |
| auc | REAL | AUC值 |

**数据量**: 141 行

#### `alert_log` — 告警日志
**数据量**: 29 行

---

## 五、cffex_minute_data.db（中金所分钟数据）

#### `minute_data` — 分钟K线
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | PK |
| datetime | TEXT | 日期时间 |
| date / time | TEXT | 日期/时间分离 |
| product | TEXT | 品种 |
| instrument | TEXT | 合约 |
| open / high / low / close | REAL | 价格 |
| volume | INTEGER | 成交量 |

**数据量**: 720 行

---

## 六、cffex_trading.db（中金所交易模拟）

> 精简版交易数据库，包含策略基础设施。

| 表名 | 数据量 | 说明 |
|------|--------|------|
| `strategies` | 0 | 策略定义（同 cffex.db 结构） |
| `orders` | 0 | 订单（同 cffex.db 结构） |
| `trades` | 0 | 交易记录 |
| `trading_positions` | 0 | 交易持仓 |
| `account_log` | 0 | 账户日志 |
| `backtests` | 0 | 回测任务 |

---

## 七、trading.db（通用交易数据库）

> 通用交易基础设施，支持多数据源。

| 表名 | 数据量 | 说明 |
|------|--------|------|
| `contracts` | 0 | 合约信息 |
| `daily_quotes` | 0 | 日线行情 |
| `instruments` | 0 | 金融工具 |
| `position_detail` | 0 | 持仓明细 |
| `download_log` | 0 | 下载日志 |
| `analysis_cache` | 0 | 分析缓存 |
| `task_execution_log` | 0 | 任务执行日志 |
| `user_activity_logs` | 60 | 用户活动日志 |
| `alembic_version` | 0 | Alembic 迁移版本 |

---

## 八、空库（预留）

| 数据库 | 说明 |
|--------|------|
| `cffex_holdings.db` | 已迁移至 cffex.db 的 position_detail 表 |
| `market_data.db` | 预留 |
| `market_quotes.db` | 预留 |
| `option_sim.db` | 期权模拟表实际在 bills.db 中 |
| `tushare.db` | Tushare 数据未迁移至此 |

---

## 索引汇总

### cffex.db 索引
- `idx_daily_quotes_date` on `daily_quotes(trade_date)`
- `idx_daily_quotes_instrument` on `daily_quotes(instrument_id)`
- `idx_daily_quotes_date_inst` on `daily_quotes(trade_date, instrument_id)`
- `idx_position_date` on `position_detail(trade_date)`
- `idx_position_instrument` on `position_detail(instrument_id)`
- `idx_contracts_variety` on `contracts(variety)`
- `idx_instruments_product` on `instruments(product_name)`

### shfe.db 索引
- `idx_shfe_daily_date` on `daily_quotes(trade_date)`
- `idx_shfe_daily_instrument` on `daily_quotes(instrument_id)`
- `idx_shfe_option_date` on `shfe_option_quotes(trade_date)`
- `idx_shfe_option_underlying` on `shfe_option_quotes(underlying)`
- `idx_shfe_minute_date` on `shfe_minute_quotes(trade_date)`

### institution.db 索引
- `idx_institution_daily_product_date` on `institution_daily_features(product, trade_date)`
- `idx_feature_daily_product_date` on `feature_daily(product, trade_date)`
- `idx_holdings_continuous_product_date` on `cffex_holdings_continuous(product, trade_date)`
- `idx_market_regime_product_date` on `market_regime(product, trade_date)`
- `idx_option_features_product_date` on `option_features(product, trade_date)`

### bills.db 索引
- `idx_trades_date` on `trades(trade_date)`
- `idx_trades_account` on `trades(account_id)`
- `idx_trades_product` on `trades(product)`
- `idx_matched_open_date` on `matched_trades(open_date)`
- `idx_matched_close_date` on `matched_trades(close_date)`
- `idx_positions_date` on `positions_detail(trade_date)`
- `idx_settlement_date` on `cffex_daily_settlement(trade_date)`
- `idx_settlement_instrument` on `cffex_daily_settlement(instrument)`
