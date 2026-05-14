# tz-data 工程进展报告

> 报告日期：2026-05-12 | 当前版本：v0.3.0（代码）/ v0.5.0（文档标注）

---

## 1. 项目定位

tz-data 是**中国期货/期权市场数据基础设施**，为上层交易系统（tz2.0）和分析系统（tz-ai）提供统一、可靠的数据服务。

**核心价值**：
- 整合 4 大数据源（CFFEX/SHFE/Tushare/CFMMC），避免上层系统各自对接
- 将 12 个分散数据库统一为 3 个标准库，简化数据管理
- 提供自动化下载、解析、监控全流程

---

## 2. 已完成模块

### 2.1 数据下载层 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| CFFEX 下载 | `download/cffex/unified_downloader.py` | ✅ | 统一下载器，支持日线/持仓 |
| CFFEX URL 构建 | `download/cffex/url_builder.py` | ✅ | 动态构建 CFFEX CSV URL |
| CFFEX CSV 解析 | `download/cffex/csv_parser.py` | ✅ | 解析交易所 CSV 格式 |
| SHFE 下载 | `download/shfe/daily_downloader.py` | ✅ | 通过 AkShare 获取 |
| Tushare 下载 | `download/tushare/daily_downloader.py` | ✅ | 日线/分钟线/期权 |
| CFMMC 下载 | `download/cfmmc/downloader.py` | ✅ | Selenium 自动登录下载 |

### 2.2 数据存储层 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| SQLite 连接池 | `storage/db_registry.py` | ✅ | 统一管理 3 个 SQLite 库 |
| Market 存储 | `storage/market_store.py` | ✅ | 行情、持仓数据写入 |
| Trading 存储 | `storage/trading_store.py` | ✅ | 账单、交易数据写入 |
| Analysis 存储 | `storage/analysis_store.py` | ✅ | 分析特征数据写入 |
| QuestDB 存储 | `storage/questdb_store.py` | ✅ | 时序数据（条件导入） |
| Schema SQL | `storage/schemas/*.sql` | ✅ | 5 个 SQL 建表脚本 |

### 2.3 账单解析 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 账单解析器 | `parser/bill_parser.py` | ✅ | 解析 CFMMC 账单格式 |
| 数据模型 | `parser/models.py` | ✅ | 账单数据结构 |
| 批量导入 | `cli/bill_import.py` | ✅ | 批量导入 + 干跑模式 |
| 凭据保险箱 | `maintenance/statements/credential_vault.py` | ✅ | AES 加密存储 |
| 账户管理 | `maintenance/statements/account_manager.py` | ✅ | CRUD + 加密密码 |

### 2.4 数据查询 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| Python SDK | `query/client.py` | ✅ | TzDataClient 统一查询接口 |
| 行情查询 | `query/market.py` | ✅ | 支持交易所/合约/日期过滤 |
| 交易查询 | `query/trading.py` | ✅ | 账单/交易/盈亏查询 |
| 分析查询 | `query/analysis.py` | ✅ | 信号/市场状态/特征查询 |

### 2.5 API 服务 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| FastAPI 服务 | `api/server.py` | ✅ | 统一路由注册 |
| 行情路由 | `api/routes/market.py` | ✅ | 行情查询 API |
| 持仓路由 | `api/routes/positions.py` | ✅ | 持仓排名 API |
| 交易路由 | `api/routes/trading.py` | ✅ | 账单/交易 API |
| 分析路由 | `api/routes/analysis.py` | ✅ | 分析数据 API |
| 管理路由 | `api/routes/admin.py` | ✅ | 健康检查/状态 |
| 维护路由 | `api/routes/maintenance.py` | ✅ | 数据维护全套 API |

### 2.6 调度与任务 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| APScheduler | `scheduler/scheduler.py` | ✅ | 6 个定时任务 |
| Celery App | `scheduler/celery_app.py` | ✅ | 分布式任务队列 |
| 同步任务 | `scheduler/tasks/sync_tasks.py` | ✅ | Celery 同步任务 |
| 检查任务 | `scheduler/tasks/check_tasks.py` | ✅ | 每日健康检查 |
| 账单任务 | `scheduler/tasks/statement_tasks.py` | ✅ | 账单解析任务 |

### 2.7 数据维护系统 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 目录管理 | `maintenance/metadata/catalog_manager.py` | ✅ | 数据目录 CRUD |
| 同步引擎 | `maintenance/sync/sync_engine.py` | ✅ | 增量/全量同步 |
| 断点管理 | `maintenance/sync/checkpoint_manager.py` | ✅ | 断点续传 |
| 数据源管理 | `maintenance/sources/source_manager.py` | ✅ | 多数据源适配 |
| Tushare 源 | `maintenance/sources/tushare_source.py` | ✅ | Tushare 数据源实现 |
| 完整性检查 | `maintenance/monitoring/completeness_checker.py` | ✅ | 交易日完整性 |
| 质量评估 | `maintenance/monitoring/quality_evaluator.py` | ✅ | 多维度评分 |
| 差异引擎 | `maintenance/monitoring/diff_engine.py` | ✅ | 多源交叉验证 |
| 健康快照 | `maintenance/monitoring/health_snapshot.py` | ✅ | 综合监控指标 |

### 2.8 监控与告警 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 统一日志 | `core/monitoring.py` | ✅ | 彩色日志 + JSON 格式 |
| 异常处理 | `core/monitoring.py` | ✅ | 装饰器自动记录 |
| 告警管理 | `core/monitoring.py` | ✅ | 多渠道告警（钉钉/企微/邮件） |
| 指标收集 | `core/monitoring.py` | ✅ | Counter/Gauge/Histogram |
| 告警规则 | `core/monitoring.py` | ✅ | 阈值 + 冷却期 |

### 2.9 数据验证 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 账单对账 | `verify/bill_reconcile.py` | ✅ | 文件 vs 数据库 |
| 跨库检查 | `verify/cross_db_check.py` | ✅ | 跨库一致性 |
| 分析验证 | `verify/analysis_verify.py` | ✅ | 分析结果验证 |

### 2.10 数据库迁移 ✅

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 12→3 迁移 | `migration/migrate_12_to_3.py` | ✅ | 核心数据已迁移 |
| 迁移模型 | `migration/models.py` | ✅ | 迁移报告数据结构 |

### 2.11 CLI 命令 ✅

| 命令 | 状态 | 说明 |
|------|------|------|
| `tzdata download` | ✅ | 4 大数据源下载 |
| `tzdata query` | ✅ | 行情/持仓/账单/盈亏 |
| `tzdata status` | ✅ | 数据状态 |
| `tzdata validate` | ✅ | 质量检查 |
| `tzdata schedule` | ✅ | 调度器管理 |
| `tzdata migrate` | ✅ | 数据库迁移 |
| `tzdata import-bills` | ✅ | 账单批量导入 |
| `tzdata verify` | ✅ | 数据验证（4 个子命令） |
| `tzdata serve` | ✅ | 启动 API 服务 |

### 2.12 前端 ✅

| 页面 | 路由 | 状态 |
|------|------|------|
| 数据维护看板 | `/dashboard` | ✅ |
| 数据目录 | `/catalogs` | ✅ |
| 同步任务 | `/sync-tasks` | ✅ |
| 健康快照 | `/health-snapshots` | ✅ |
| 账户管理 | `/accounts` | ✅ |
| 账单管理 | `/statements` | ✅ |
| 告警历史 | `/alerts` | ✅ |

---

## 3. 部分完成 / 进行中

### 3.1 数据库迁移（部分完成）

| 表 | 状态 | 说明 |
|----|------|------|
| 核心行情/交易/账单 | ✅ 已迁移 | daily_quotes, position_detail, trades 等 |
| institution_daily_features | ❌ 未迁移 | Schema 差异，需专用脚本 |
| trading_signals | ❌ 未迁移 | Schema 差异 |
| market_regime | ❌ 未迁移 | Schema 差异 |
| option_features | ❌ 未迁移 | Schema 差异 |
| institution_master | ❌ 未迁移 | Schema 差异 |

### 3.2 Tushare 数据入库（部分完成）

| 表 | 状态 | 说明 |
|----|------|------|
| tushare_daily | ❌ 空表 | 下载器已实现，数据未入库 |
| tushare_minute | ❌ 空表 | 同上 |
| tushare_option | ❌ 空表 | 同上 |

### 3.3 Celery 分布式任务（部分完成）

| 组件 | 状态 | 说明 |
|------|------|------|
| Celery App | ✅ | 已配置 |
| 任务定义 | ✅ | 同步/检查/账单任务 |
| Worker 运行 | ⚠️ | Windows 需 `--pool=gevent`，需安装 Redis |

---

## 4. 未实现 / 规划中

### 4.1 数据质量提升

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 自动化数据验证流水线 | 中 | 每次下载后自动运行完整性/一致性检查 |
| 异常数据标记 | 低 | 自动标记异常值（如价格跳变超过阈值） |
| 数据修复工具 | 低 | 手动修复/重跑缺失数据 |

### 4.2 性能优化

| 功能 | 优先级 | 说明 |
|------|--------|------|
| SQLite WAL 模式优化 | 低 | 当前可能未启用 WAL |
| 批量写入优化 | 低 | 大批量下载时的写入性能 |
| 查询缓存 | 低 | 频繁查询结果的缓存 |

### 4.3 安全性

| 功能 | 优先级 | 说明 |
|------|--------|------|
| API 认证/授权 | 中 | 当前 API 无鉴权 |
| 密码加密审计 | 高 | CFMMC 密码 AES 加密，需定期轮换密钥 |
| 审计日志 | 中 | 记录所有数据变更操作 |

---

## 5. 数据量统计

### 5.1 总体

| 指标 | 值 |
|------|-----|
| 数据库文件数 | 16 个（3 个统一库 + 12 个旧库 + 1 个市场库） |
| 总数据量 | ~460 MB |
| 总表行数 | ~2.54M |
| 账单文件数 | 37 个 |
| 覆盖品种 | CFFEX: MO/IM/IC/IF/IH/IO/HO, SHFE: AU/AG/CU/AL/ZN |
| 时间跨度 | 2024-01 ~ 2026-05 |

### 5.2 各表行数 Top 10

| 表 | 行数 | 数据库 |
|----|------|--------|
| daily_quotes | ~967K | market |
| cffex_daily_settlement | ~889K | trading |
| position_detail | ~639K | market |
| option_sim_iv_series | ~30K | trading |
| jq_options_data | ~30K | trading |
| trades | ~13.5K | trading |
| matched_trades | ~9.9K | trading |
| trade_performance | ~9.9K | trading |
| feature_daily | ~5.5K | analysis |
| jq_futures_data | ~3K | trading |

---

## 6. 文档清单

| 文档 | 路径 | 状态 |
|------|------|------|
| 数据库 Schema | `docs/DATABASE_SCHEMA.md` | ✅ 完整（1107 行） |
| 运维手册 | `docs/OPERATIONS.md` | ✅ 完整（625 行） |
| 用户指南 | `docs/USER_GUIDE.md` | ✅ 完整（944 行） |
| 数据报告 | `docs/DATA_REPORT.md` | ✅ 新增 |
| 用户文档 | `docs/USER_DOCUMENTATION.md` | ✅ 新增 |
| 工程进展 | `docs/PROGRESS_REPORT.md` | ✅ 新增 |

---

## 7. 双工程协同

tz-data 和 tz2.0 在同一台机器运行：

| 服务 | 端口 | 项目 |
|------|------|------|
| tz-data 后端 | 8000 | C:\myspace\tz-data |
| tz-data 前端 | 3000 | C:\myspace\tz-data\frontend |
| tz2.0 后端 | 8200 | C:\myspace\tz2.0 |
| tz2.0 前端 | 3200 | C:\myspace\tz2.0\frontend |

**依赖关系**：tz2.0 通过 Python import (`tzdata_pkg`) 和 SQLite 文件直读依赖 tz-data，不需要 HTTP 调用 tz-data API。

---

## 8. 风险与建议

| 风险 | 影响 | 建议 |
|------|------|------|
| PostgreSQL 未运行 | 数据维护功能不可用 | 在 Windows 上安装 PostgreSQL 或改用 SQLite 替代元数据 |
| Redis 未运行 | Celery 任务不可用 | 安装 Memurai（Redis Windows 兼容版） |
| 部分分析表未迁移 | analysis.db 数据不完整 | 编写专用迁移脚本 |
| API 无鉴权 | 安全风险 | 添加 JWT 或 API Key 认证 |
| 无自动化备份 | 数据丢失风险 | 设置每日 PowerShell 备份脚本 + 定时任务 |

---

## 9. 下一步建议

1. **完成剩余迁移**：编写 `institution_daily_features`、`trading_signals` 等表的专用迁移脚本
2. **基础设施到位**：安装 PostgreSQL + Redis/Memurai，使数据维护系统完整运行
3. **API 鉴权**：为 FastAPI 添加 API Key 或 JWT 认证
4. **自动备份**：设置 Windows 计划任务每日备份 SQLite 数据库
5. **Tushare 数据入库**：确认 Tushare token 有效后，跑一次全量同步
