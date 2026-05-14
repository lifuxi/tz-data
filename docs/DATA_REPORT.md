# tz-data 数据报告

> 生成日期：2026-05-13 | 项目版本：v0.5.0

---

## 1. 项目概览

tz-data 是一个**中国期货/期权市场统一数据管理平台**，负责从多个数据源（CFFEX 中金所、SHFE 上期所、Tushare API、CFMMC 监控中心）自动下载、解析、存储和提供查询行情数据、持仓排名、账单交易等金融数据。

### 1.1 定位与架构

```
数据源（交易所/API） → 下载器（CFFEX/SHFE/Tushare/CFMMC） → 统一存储层（3 SQLite DBs）
                                                                          ↓
                                                  上层消费方（tz2.0 分析系统 / tz-ai 模型 / FastAPI / CLI）
```

### 1.2 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn (ASGI) |
| CLI | Click |
| 调度器 | Celery + Beat（分布式任务队列 + 定时调度） |
| 数据库 | SQLite（3 库，统一架构）/ PostgreSQL（可选，生产元数据） |
| 前端 | Vue 3 + Element Plus + Vite |
| 数据源 | CFFEX 官网、SHFE 官网、Tushare API、CFMMC（Playwright） |
| 语言 | Python 3.11+ / TypeScript |

---

## 2. 数据库现状

### 2.1 统一数据库（v0.3.0+）

| 数据库文件 | 大小 | 表数 | 核心表行数 |
|-----------|------|------|-----------|
| `tzdata_market.db` | ~339 MB | 10 | daily_quotes ~967K, position_detail ~639K |
| `tzdata_trading.db` | ~120 MB | 28 | cffex_daily_settlement ~889K, trades ~13.5K, matched_trades ~9.9K |
| `tzdata_analysis.db` | ~0.5 MB | 18 | feature_daily ~5.5K |
| **合计** | **~460 MB** | **56** | **~2.54M 行** |

### 2.2 遗留数据库（12 个旧库，部分已迁移）

| 数据库 | 大小 | 状态 | 说明 |
|--------|------|------|------|
| `bills.db` | 211 MB | 已迁移核心表 → trading.db | 55 表，账单/交易/策略核心数据源 |
| `cffex.db` | 301 MB | 已迁移核心表 → market.db | 28 表，中金所行情+持仓 |
| `shfe.db` | 23 MB | 已迁移 → market.db | 5 表，上期所行情 |
| `institution.db` | 31 MB | 部分迁移 → analysis.db | 13 表，机构持仓分析 |
| `cffex_minute_data.db` | 180 KB | 已迁移 → market.db | 720 行分钟K线 |
| 其他 7 个 | <10 MB | 空库/已合并 | cffex_holdings, market_data, market_quotes, option_sim, trading, tushare, cffex_trading |

### 2.3 核心数据表详情

#### 行情数据（market.db）

| 表 | 行数 | 时间范围 | 产品覆盖 |
|----|------|---------|---------|
| daily_quotes | ~967K | 2024-01 ~ 2026-05 | IO(388K), MO(230K), HO(176K), AG(53K), AU(23K), IF/IH/IC |
| position_detail | ~639K | 2024-01 ~ 2026-05 | CFFEX 全品种机构持仓排名 |
| minute_quotes | 720 | 样本数据 | CFFEX 分钟K线（少量） |
| contracts | 106 | - | 合约基本信息 |

#### 交易与账单（trading.db）

| 表 | 行数 | 说明 |
|----|------|------|
| cffex_daily_settlement | ~889K | 中金所每日结算价数据 |
| trades | ~13.5K | 实际交易明细（从账单解析） |
| matched_trades | ~9.9K | 开-平仓配对 |
| trade_performance | ~9.9K | 交易表现分析（含希腊值） |
| strategy_performance_summary | 286 | 策略维度汇总 |
| account_summary | 17 | 账户月度汇总 |
| option_sim_iv_series | ~30K | 期权隐含波动率序列 |
| jq_futures_data | ~3K | JoinMin 期货数据 |
| jq_options_data | ~30K | JoinMin 期权数据 |

#### 分析数据（analysis.db）

| 表 | 行数 | 说明 |
|----|------|------|
| feature_daily | ~5.5K | 日度综合特征（品种级别，机构持仓衍生） |
| model_validation_records | 141 | 模型验证记录（AUC） |

### 2.4 账单数据

| 指标 | 值 |
|------|-----|
| 账单原始文件 | 37 个（17 个月度文件 + 20 个日度文件） |
| 账户 | 321980 互联网金融部 |
| 时间范围 | 2025-01 ~ 2026-05（月度），2026-04-01 ~ 2026-04-30（日度） |
| 交易明细 | 13,534 条 |
| 配对交易 | 9,861 对 |

---

## 3. 数据源覆盖

| 数据源 | 类型 | 下载方式 | 频率 | 状态 |
|--------|------|---------|------|------|
| CFFEX 日线 | 行情/结算 | HTTP CSV 下载 | 日线 | ✅ 已实现 |
| CFFEX 持仓 | 机构排名 | HTTP CSV 下载 | 日线 | ✅ 已实现 |
| CFFEX MO 期权 | 期权行情 | HTTP CSV 下载 | 日线 | ✅ 已实现 |
| SHFE 日线 | 行情 | AkShare API | 日线 | ✅ 已实现 |
| SHFE 期权 | 期权行情 | AkShare API | 日线 | ✅ 已实现 |
| Tushare 日线 | 行情 | Tushare REST API | 日线 | ✅ 已实现 |
| Tushare 分钟K | 分钟线 | Tushare REST API | 分钟 | ✅ 已实现 |
| Tushare 期权 | 希腊值/IV | Tushare REST API | 日线 | ✅ 已实现 |
| CFMMC 账单 | 账户账单 | Selenium 自动化 | 月度 | ✅ 已实现 |

---

## 4. API 端点

### 4.1 行情查询 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/market/quotes` | GET | 行情查询（支持交易所/合约/日期过滤） |
| `/api/v1/positions/{product}` | GET | 持仓排名查询 |
| `/api/v1/bills` | GET | 账单列表 |
| `/api/v1/admin/health` | GET | 健康检查 |
| `/api/v1/admin/status` | GET | 系统状态 |

### 4.2 数据维护 API（/api/maintenance/）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/catalogs` | GET/POST | 数据目录管理 |
| `/catalogs/{id}` | GET/PUT | 目录详情/更新 |
| `/sync/trigger` | POST | 触发同步任务 |
| `/sync/tasks` | GET | 同步任务列表 |
| `/sync/task/{task_id}` | GET | 任务详情 |
| `/sync/status` | GET | 并发状态 |
| `/health/snapshot` | GET | 健康快照 |
| `/health/diff` | GET | 差异状态 |
| `/health-snapshots` | GET | 历史快照列表 |
| `/health-snapshots/latest` | GET | 最新聚合快照 |
| `/health-snapshots/generate` | POST | 生成全部快照 |
| `/quality/{catalog_id}` | GET | 数据质量评估 |
| `/accounts` | GET/POST | 期货账户管理 |
| `/exchanges` | GET/POST/PUT/DELETE | 交易所管理 |
| `/products` | GET/POST/PUT/DELETE | 品种管理 |
| `/contracts` | GET/POST/PUT/DELETE | 合约管理 |
| `/trade-calendar/init` | POST | 初始化交易日历 |
| `/trade-calendar/trading-days` | GET | 查询交易日范围 |
| `/trade-calendar/is-trading-day` | GET | 检查是否交易日 |
| `/trade-calendar/add-holiday` | POST | 添加节假日 |
| `/statements/verify-balance` | POST | 账单余额平衡校验 |
| `/statements/reconcile` | POST | 账单-市场滑点对账 |
| `/statements/reconcile/{account_id}` | GET | 从数据库对账 |
| `/credentials` | POST | 保存加密凭证 |
| `/alerts` | GET | 告警列表 |
| `/alerts/recent` | GET | 最近告警 |

---

## 5. 前端页面

| 页面 | 路由 | 分组 | 功能 |
|------|------|------|------|
| 数据维护看板 | `/dashboard` | 数据维护 | 总览：同步状态、质量评分、告警统计 |
| 数据目录 | `/catalogs` | 数据维护 | 管理需要跟踪的数据项（交易所×品种×数据类型） |
| 同步任务 | `/sync-tasks` | 数据维护 | 查看/触发数据同步任务 |
| 健康快照 | `/health-snapshots` | 数据维护 | 数据健康历史快照与对比 |
| 交易所管理 | `/exchanges` | 基础数据 | 交易所配置 |
| 品种管理 | `/products` | 基础数据 | 品种配置 |
| 合约管理 | `/contracts` | 基础数据 | 合约信息维护 |
| 交易日历 | `/trade-calendar` | 基础数据 | 节假日管理、交易日查询 |
| 账户管理 | `/accounts` | 账单与账户 | 期货账户配置（CFMMC 凭据管理） |
| 账单管理 | `/statements` | 账单与账户 | 账单上传、解析、余额校验、滑点对账 |
| 数据源配置 | `/data-sources` | 系统 | 数据源 + 交易日历 + 账户凭证统一管理 |
| 告警历史 | `/alerts` | 系统 | 系统告警与通知记录 |

---

## 6. 调度任务

通过 Celery Beat 自动执行：

| 任务名 | 时间 | 说明 |
|--------|------|------|
| `daily-incremental-sync` | 18:00 | 增量同步所有启用目录 |
| `daily-status-refresh` | 18:30 | 刷新远程数据状态 |
| `daily-completeness-check` | 19:00 | 数据完整性检查 |
| `daily-bill-missing-check` | 20:00 | 检查缺失账单 |

历史调度任务（APScheduler，已迁移至 Celery）：

| 任务名 | 时间 | 数据源 | 状态 |
|--------|------|--------|------|
| cffex_daily | 18:00 | CFFEX 日线 | ✅ 已迁移至 Celery |
| shfe_daily | 18:30 | SHFE 日线 | ✅ 已迁移至 Celery |
| cffex_position | 19:00 | CFFEX 持仓 | ✅ 已迁移至 Celery |
| cfmmc_bills | 20:00 | CFMMC 账单 | ✅ 已迁移至 Celery |
| tushare_daily | 22:00 | Tushare 日线 | ✅ 已迁移至 Celery |
| data_validate | 02:00 | 内部检查 | ✅ 已迁移至 Celery |

---

## 7. 已知限制

1. **部分机构分析表未迁移**：`institution_daily_features`、`trading_signals`、`market_regime`、`option_features` 等因 Schema 差异需手动迁移
2. **Tushare 数据未完全入库**：`tushare_daily`、`tushare_minute`、`tushare_option` 表为空（预留）
3. **分钟线数据极少**：仅 720 行样本数据
4. **DCE/CZCE 数据源未实现**：大商所、郑商所数据源为 placeholder，尚未实现
5. **跨数据源对比（DiffEngine）**：仅框架实现，value_a/value_b 始终为 None
6. **质量评估一致性检查**：`_check_consistency` 返回 100.0，尚未实现分钟-日线聚合逻辑

---

## 8. v0.5.0 新增功能

### 8.1 数据维护系统
- 数据目录管理（Catalog）
- 同步引擎（SyncEngine）：增量/全量同步、断点续传
- 质量评估（QualityEvaluator）：完整性/准确性/一致性多维度评分
- 健康快照（HealthSnapshot）：综合监控指标
- 并发控制：全局信号量 + 目录锁 + 数据源限流

### 8.2 账单管理增强
- CFMMC 账单自动抓取（Playwright 浏览器自动化）
- 账单余额平衡校验（复式记账方程）
- 滑点对账（账单价格 vs 市场价格）
- 凭证加密存储（AES-256/Fernet）
- 缺失账单每日检查

### 8.3 交易日历
- 中国期货交易所交易日历（2025-2026 节假日）
- 交易日查询、节假日管理

### 8.4 新增数据源
- CFFEX 官方数据源（中金所官网）
- SHFE 官方数据源（上期所官网）
