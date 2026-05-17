# 数据库与数据资产全景

> 版本：v0.7.0 | 最后更新：2026-05-17

## 一、架构概览

tz-data 采用 **3 库分离 + 1 可选时序库** 架构，SQLite WAL 模式，数据目录：`data/`。

```
data/
├── tzdata_market.db      # 市场数据（30 表）
├── tzdata_trading.db     # 交易数据（31 表）
├── tzdata_analysis.db    # 分析数据（18 表）
└── bills.db              # 账单数据（CFMMC 原始账单，tz2.0 共享读取）
```

| 数据库 | 文件 | 表数 | Store 类 | 初始化 |
|--------|------|------|----------|--------|
| Market | `tzdata_market.db` | 30 | `MarketStore` | `market.sql` |
| Trading | `tzdata_trading.db` | 31 | `TradingStore` | `trading.sql` + `trading_data_layer.sql` |
| Analysis | `tzdata_analysis.db` | 18 | `AnalysisStore` | `analysis.sql` |
| QuestDB（可选） | 外部服务 | 4 | `QuestDBStore` | `questdb.sql` |

**合计：83 张表**，覆盖行情、合约、持仓、账单、交易、账户、策略、回测、模拟盘、风控、机构特征、信号、市场状态、Tushare 数据等 15 个业务域。

---

## 二、数据库明细

### 2.1 Market DB — `tzdata_market.db`（30 表）

**核心职责**：行情采集、合约管理、数据同步与质量监控。

#### 行情数据（5 表）

| 表 | 数据周期 | 数据来源 | 关键字段 |
|----|---------|---------|---------|
| `daily_quotes` | 日频 | CFFEX/SHFE/DCE/CZCE/Tushare/AkShare | exchange, contract_code, trade_date, OHLCV, settle, open_interest, source |
| `minute_quotes` | 分钟级（1/5/15/30/60min） | Tushare/MO 下载器 | exchange, contract_code, trade_time, frequency, OHLCV, vwap |
| `settlement_prices` | 日频 | 交易所官方 | exchange, contract_code, trade_date, settle_price |
| `mo_daily_iv_quotes` | 日频 | 自算（BS 模型） | trade_date, contract_code, iv, delta/gamma/theta/vega, option_price, underlying_price |
| `cffex_daily_settlement` | 日频 | CFFEX 官方 | trade_date, instrument, OHLCV, settle, delta |

#### 合约与产品配置（6 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `contracts` | 合约主表 | contract_code(UNIQUE), variety, contract_type, underlying, strike_price, expiry_date, multiplier, tick_size |
| `contract_info` | 跟踪合约 | contract_code, last_trade_date, delivery_date, is_tracked |
| `product_config` | 品种配置 | product_code, multiplier, price_tick, margin_rate, option_style, is_tracked |
| `exchange_config` | 交易所配置 | exchange_code, trading_hours(JSON), timezone, is_active |
| `main_contract_map` | 主力合约映射 | product_code, trade_date, contract_code, method(volume_oi/rule/manual) |
| `contract_expiry` | 到期日历 | symbol, expiry_date, underlying_symbol, strike_price |

#### 持仓排名（2 表）

| 表 | 数据周期 | 关键字段 |
|----|---------|---------|
| `position_detail` | 日频 | exchange, trade_date, contract_code, member_name, rank, long/short_volume, long/short_change, net_position(生成列) |
| `cffex_holdings_continuous` | 日频 | trade_date, contract_code, total_long/short, oi_ratio, smart_money_long/short, retail_long/short |

#### 交易日历（3 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `trade_calendar` | 交易日历 | trade_date, exchange_code, product_code, is_holiday, is_weekend, is_workday, special_flag |
| `special_date_override` | 日期覆盖 | exchange_code, trade_date, override_type(holiday/workday/half_day), reason, operator |
| `product_listing_dates` | 上市日期 | product_code, listing_date |

#### 交易时间模板（2 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `trading_hours_template` | 时间模板 | template_id, normal_schedule(JSON), night_schedule(JSON), pre_open(JSON) |
| `product_trading_hours` | 品种时间 | exchange_code, product_code, template_id, effective_date, schedule_override(JSON) |

#### 数据同步与目录（7 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `data_catalog` | 目录定义 | catalog_name, exchange_code, product_code, data_type, frequency, data_source, sync_mode, is_enabled |
| `data_status_local` | 本地状态 | catalog_id, earliest_date, latest_date, total_records |
| `data_status_remote` | 远端状态 | catalog_id, latest_date, total_available_days, last_checked |
| `sync_task` | 同步任务 | catalog_id, task_name, status(pending/running/completed/failed), checkpoint_data(JSON) |
| `sync_audit_log` | 同步审计 | task_id, sync_mode, records_fetched, duration_seconds, error_message |
| `download_log` | 下载日志 | exchange, data_type, product, records_downloaded, status, duration_seconds |
| `download_progress` | 下载断点 | exchange, data_type, product, last_date, total_records |

#### 监控与质量（4 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `data_health_snapshot` | 健康快照 | catalog_id, snapshot_date, missing_days, data_quality_score, completeness_pct, consistency_status |
| `data_diff_log` | 跨源差异 | catalog_id, trade_date, source_a, source_b, deviation_pct, is_alert |
| `data_quality_checks` | 质量检查 | table_name, check_type, status, detail |
| `download_failures` | 下载失败 | exchange, data_type, product, retry_count, max_retries, next_retry_at |

#### 系统与审计（3 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `system_config` | 系统配置 | config_key(PK), config_value, config_type(secret/text/number/json) |
| `file_checksums` | 文件校验 | exchange, data_type, product, trade_date, checksum, file_size |
| `beat_task_log` | Beat 执行日志 | task_name, scheduled_at, executed_at, status, duration_ms, error |
| `task_failure_log` | 任务失败 | task_name, error_type, error_message, failed_at, notified, retries |

---

### 2.2 Trading DB — `tzdata_trading.db`（31 表）

**核心职责**：账单解析、交易记录、持仓管理、账户快照、策略绩效、模拟盘、风控。

#### 账单与交易（5 表）

| 表 | 数据周期 | 关键字段 |
|----|---------|---------|
| `bills` | 按账单 | account_id, bill_date_start/end, balance_bf/cf, deposit_withdrawal, realized_pl, mtm_pl, commission, client_equity, fund_available |
| `bill_raw_sections` | 按账单 | bill_id(FK), section_type(summary/deposits/transactions/positions), raw_content |
| `bill_fund_flows` | 日频 | bill_id(FK), trade_date, flow_type(deposit/withdrawal/realized_pnl/commission), amount |
| `trades` | 逐笔 | account_id, trade_date, instrument, direction, offset_flag, volume, price, turnover, commission, total_pnl, premium |
| `matched_trades` | 逐笔（配对） | instrument, open_trade_id, close_trade_id, holding_days, price_pnl, money_pnl, net_pnl |

#### 交易绩效（2 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `trade_performance` | 绩效 | matched_trade_id, net_pnl, pnl_ratio, holding_days, strategy_type, delta/gamma/vega/theta |
| `trade_comparison_analysis` | 对比分析 | analysis_date, actual_close_price vs virtual_close_price, pnl_difference, pnl_difference_ratio |

#### 持仓与账户（4 表）

| 表 | 数据周期 | 关键字段 |
|----|---------|---------|
| `positions_summary` | 日频 | account_id, trade_date, instrument, long/short_position, settlement_price, accumulated_pnl, margin_occupied |
| `account_summary` | 月频 | account_id, year, month, balance_b_f/c_f, total_pnl, commission, client_equity, risk_degree, margin_call |
| `account_cashflow` | 事件驱动 | time, type(deposit/withdrawal/trading_pnl/commission), amount, balance |
| `futures_accounts` | 配置 | account_number(UNIQUE), futures_company, exchanges_supported(JSON), tracking_start_date |

#### 账单状态管理（2 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `statement_status` | 账单状态 | account_id, statement_date, upload_status, parse_status, data_quality_score, balance_check_passed |
| `statement_parse_error` | 解析错误 | account_id, statement_date, error_type, error_message |

#### 策略配置与绩效（4 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `strategies` | 策略定义 | name, type(discretionary/systematic/hybrid), status |
| `strategy_summary` | 日频绩效 | strategy_id, date, total_equity, daily_pnl, daily_return, cumulative_return, drawdown, sharpe_ratio |
| `strategy_performance_summary` | 期间汇总 | strategy_id, period_start/end, total_trades, win_rate, total_pnl, max_drawdown, sharpe_ratio, profit_factor |
| `backtest_results` | 回测 | strategy_name, initial_capital, final_equity, total_return, annual_return, max_drawdown, sharpe/sortino/calmar, params(JSON) |

#### 模拟盘（5 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `paper_accounts` | 模拟账户 | name, initial_capital, current_equity, status |
| `paper_position` | 模拟持仓 | account_id, instrument, direction, volume, avg_price, current_price, unrealized_pnl |
| `paper_trade` | 模拟交易 | account_id, instrument, direction, volume, price, commission, trade_date |
| `paper_order` | 模拟委托 | account_id, instrument, direction, volume, price, order_type, status |
| `option_sim_strategies` | 期权模拟策略 | name, underlying, initial_capital, status |
| `option_sim_trades` | 期权模拟交易 | strategy_id, instrument, direction, entry/exit_price, entry/exit_date, pnl |
| `option_sim_iv_series` | 期权模拟 IV 序列 | strategy_id, trade_date, iv_value, iv_percentile, iv_rank, hv_20/hv_60 |

#### 风控（2 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `risk_config` | 风控配置 | key(PK), value, description |
| `risk_history` | 风控事件 | risk_type, level(normal/warning/critical), detail, triggered_at |

#### 报表（2 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `reports` | 报表 | title, report_type, content(JSON/HTML), generated_at, created_by |
| `report_templates` | 报表模板 | name, template_type, content, variables(JSON) |

#### 市场参考数据（4 表）

| 表 | 数据周期 | 关键字段 |
|----|---------|---------|
| `daily_index_prices` | 日频 | index_code(000852/000300), trade_date, OHLCV |
| `option_greeks_daily` | 日频 | trade_date, symbol, option_type, strike_price, iv, delta/gamma/vega/theta |
| `contract_expiry` | 配置 | symbol, expiry_date, underlying_symbol, strike_price |
| `cffex_daily_settlement` | 日频 | trade_date, instrument, OHLCV, settle, delta |

---

### 2.3 Analysis DB — `tzdata_analysis.db`（18 表）

**核心职责**：机构特征工程、交易信号、市场状态分类、Tushare 原始数据、模型验证。

#### 机构分析（5 表）

| 表 | 数据周期 | 关键字段 |
|----|---------|---------|
| `institution_master` | 配置 | member_name(UNIQUE), exchange, member_code, category(futures_company/bank/securities) |
| `institution_name_mapping` | 配置 | raw_name, canonical_name, exchange, confidence |
| `institution_profiles` | 快照 | member_name, total_long/short, avg_daily_volume, bias_direction, first/last_appearance |
| `institution_daily_features` | 日频 | trade_date, member_name, contract_code, long/short_volume, member_rank, member_long/short_pct, concentration_score |
| `institution_lead_lag` | 日频 | trade_date, leading_member, lagging_members(JSON), correlation, lag_days, accuracy |

#### 市场信号与状态（3 表）

| 表 | 数据周期 | 关键字段 |
|----|---------|---------|
| `trading_signals` | 日频 | signal_date, product, signal_type(entry_long/entry_short/exit/reduce), strength(0-1), source, triggered |
| `signal_triggers` | 事件驱动 | signal_id(FK), trigger_date, entry/exit_price, holding_days, pnl, status |
| `market_regime` | 日频 | trade_date, regime_type(trending_up/trending_down/range/volatile), trend_strength, volatility_level, iv_regime |

#### 市场特征（2 表）

| 表 | 数据周期 | 关键字段 |
|----|---------|---------|
| `feature_daily` | 日频 | trade_date, contract_code, top_long/short_member, net_institutional_flow, sentiment_score(-1~1) |
| `option_features` | 日频 | trade_date, contract_code, iv, iv_percentile, iv_rank, delta/gamma/theta/vega/rho, hv_5/10/20, iv_hv_spread_20 |

#### Tushare 数据（3 表）

| 表 | 数据周期 | 关键字段 |
|----|---------|---------|
| `tushare_daily` | 日频 | ts_code, trade_date, OHLCV, settle, oi, oi_change |
| `tushare_minute` | 分钟级 | ts_code, trade_date, trade_time, freq, OHLCV, amount |
| `tushare_option` | 日频 | ts_code, trade_date, settle, OHLCV, oi, delta/gamma/theta/vega, iv |

#### 基础设施（3 表）

| 表 | 类型 | 关键字段 |
|----|------|---------|
| `download_log` | 审计 | source, data_type, product, records_downloaded, status, duration_seconds |
| `task_execution_log` | 审计 | task_name, status, start/end_time, duration_seconds, output, error_message |
| `analysis_cache` | 缓存 | cache_key(UNIQUE), cache_value, created_at, expires_at |

---

### 2.4 QuestDB（可选）— 4 表

当部署 QuestDB 外部时序数据库时启用，条件导入，不影响核心功能。

| 表 | 数据周期 | 分区 | 关键字段 |
|----|---------|------|---------|
| `index_minute` | 分钟级 | DAY | symbol, trade_time, OHLCV |
| `future_minute` | 分钟级 | DAY | symbol, trade_time, OHLCV, oi |
| `option_minute` | 分钟级 | DAY | symbol, trade_time, OHLCV, iv |
| `top20_holdings` | 日频 | DAY | trade_date, contract_code, member_name, long/short_volume |

---

### 2.5 独立文件 — `bills.db`

由 CFMMC 账单原始文件解析后写入，tz2.0 项目直接读取共享。表结构与 `tzdata_trading.db` 的 `bills`/`trades` 等一致。

---

## 三、数据周期与类型矩阵

### 3.1 按数据周期分类

| 周期 | 表数 | 典型表 |
|------|------|--------|
| **日频** | 35+ | daily_quotes, settlement_prices, position_detail, positions_summary, account_summary(月), daily_index_prices, trading_signals, market_regime, tushare_daily, institution_daily_features |
| **分钟级** | 5 | minute_quotes, tushare_minute, index_minute, future_minute, option_minute |
| **事件驱动** | 5 | account_cashflow, signal_triggers, risk_history, bill_fund_flows, matched_trades |
| **按账单** | 3 | bills, bill_raw_sections, statement_status |
| **配置/参考** | 25+ | contracts, product_config, exchange_config, trade_calendar, system_config, strategies, risk_config, paper_accounts |
| **审计/日志** | 8 | download_log, sync_audit_log, beat_task_log, task_failure_log, task_execution_log, data_quality_checks, download_failures, analysis_cache |
| **快照/聚合** | 6 | data_health_snapshot, institution_profiles, strategy_performance_summary, feature_daily, cffex_holdings_continuous, account_summary |

### 3.2 按业务域分类

| 业务域 | 数据库 | 表数 | 核心表 |
|--------|--------|------|--------|
| 行情数据 | Market + Analysis | 12 | daily_quotes, minute_quotes, settlement_prices, cffex_daily_settlement, tushare_daily/minute/option |
| 期权数据 | Market + Analysis + Trading | 8 | mo_daily_iv_quotes, option_greeks_daily, option_features, option_sim_iv_series, option_minute |
| 合约管理 | Market | 6 | contracts, contract_info, product_config, main_contract_map, contract_expiry, product_listing_dates |
| 持仓排名 | Market + Analysis | 4 | position_detail, cffex_holdings_continuous, institution_daily_features, top20_holdings |
| 账单管理 | Trading | 5 | bills, bill_raw_sections, bill_fund_flows, statement_status, statement_parse_error |
| 交易记录 | Trading | 4 | trades, matched_trades, trade_performance, trade_comparison_analysis |
| 账户管理 | Trading | 4 | positions_summary, account_summary, account_cashflow, futures_accounts |
| 策略绩效 | Trading | 4 | strategies, strategy_summary, strategy_performance_summary, backtest_results |
| 模拟盘 | Trading | 7 | paper_accounts, paper_position, paper_trade, paper_order, option_sim_strategies/trades/iv_series |
| 风控管理 | Trading | 2 | risk_config, risk_history |
| 机构分析 | Analysis | 5 | institution_master, institution_name_mapping, institution_profiles, institution_daily_features, institution_lead_lag |
| 交易信号 | Analysis | 3 | trading_signals, signal_triggers, market_regime |
| 数据同步 | Market | 7 | data_catalog, data_status_local/remote, sync_task, sync_audit_log, download_log/progress |
| 数据质量 | Market | 4 | data_health_snapshot, data_diff_log, data_quality_checks, download_failures |
| 系统配置 | Market + Trading | 4 | system_config, exchange_config, trading_hours_template, product_trading_hours |
| 审计日志 | Market + Analysis | 8 | download_log, sync_audit_log, beat_task_log, task_failure_log, task_execution_log, data_quality_checks, download_failures, analysis_cache |

---

## 四、数据流全景

```
数据源 ────────────────────────────────────────────────────────────────────▶ 数据存储 ───▶ 数据消费
                                                                             │
 CFFEX ────────┐                                                           │
 SHFE ─────────┤                                                           │
 DCE ──────────┤                                                           │
 CZCE ─────────┤    同步引擎 ──▶  market.db ◀──┐                          │
 AkShare ──────┤    (SyncEngine)   │ 行情      │  质量评估                  │
               │                   │ 合约      │  (CompletenessChecker)    │    REST API ───▶ 前端页面
 Tushare ──────┤ ──▶  data_catalog │ 持仓      │  (QualityEvaluator)       │    (50+ 端点)  │  DataDashboard
 CFMMC ────────┤                   │ 同步      │  (AnomalyDetector)        │               │  Dashboard
               │                   │ 审计      │                           │               │
               │                   └───────────┘                           │               │
               │                                                           │               │
               │    解析引擎 ──▶  trading.db ◀──┐                          │    Python SDK ─▶ tz2.0
               │    (BillParser)   │ 账单      │  FIFO 配对                │    (import)    │  tz-ai
               │                   │ 交易      │  (TradeMatcher)           │               │
               │                   │ 持仓      │  资金平衡校验              │               │
               │                   │ 账户      │  (BillBalanceVerifier)    │               │
               │                   │ 策略      │  滑点分析                  │               │
               │                   │ 回测      │  (BillMarketReconciler)   │               │
               │                   │ 模拟盘    │                           │               │
               │                   │ 风控      │                           │               │
               │                   └───────────┘                           │               │
               │                                                           │               │
               │    特征工程 ──▶  analysis.db ◀─┐                          │
               │    (Features)     │ 机构      │  市场状态分类              │
               │                   │ 信号      │  (compute_mo_market_env)  │
               │                   │ 状态      │  Greeks 预计算            │
               │                   │ Tushare   │  (compute_option_greeks)  │
               │                   └───────────┘                           │
               │                                                           │
               │    可选 ──────▶  QuestDB ◀────┐                           │
               │                   │ 分钟行情   │  高频时序查询             │
               │                   │ 持仓       │                           │
               │                   └───────────┘                           │
```

## 六、相关文档

- [数据报告全量清单](14-data-reports.md) — 16 类报告完整清单
- [部署与运维](13-deployment.md) — 启动脚本、备份、FAQ
