# tz-data 文档索引

> 版本：v0.7.0 | 最后更新：2026-05-15

tz-data 是中国期货/期权市场统一数据平台，负责从交易所（CFFEX/SHFE/DCE/CZCE/INE）和数据源（Tushare/CFMMC/AkShare）下载、解析、存储并提供 REST API 和 Python SDK 查询接口。

## 文档目录

| # | 文档 | 说明 |
|---|------|------|
| 1 | [快速入门](01-getting-started.md) | 安装、环境配置、快速启动 |
| 2 | [系统架构](02-architecture.md) | 整体架构、数据库、数据流、技术栈 |
| 3 | [API 接口文档](03-api-reference.md) | 所有 REST API 端点（含参数和返回示例） |
| 4 | [CLI 使用指南](04-cli-guide.md) | 命令行工具（下载/查询/调度/同步/匹配） |
| 5 | [Python SDK](05-python-sdk.md) | TzDataClient 和维护模块 Python API |
| 6 | [数据维护与同步](06-data-maintenance.md) | 目录管理、同步引擎、质量评估、健康快照 |
| 7 | [账单与交易管理](07-bill-management.md) | CFMMC 下载、账单解析、开平匹配、盈亏计算 |
| 8 | [交易日历与合约管理](08-trade-calendar.md) | 交易日历、主力合约、交易时间模板 |
| 9 | [MO 期权数据同步](09-mo-data-sync.md) | MO IV/标的/分钟/合约同步与质量检查 |
| 10 | [Celery 任务调度](10-celery-tasks.md) | Celery 配置、Beat 调度表、任务模块 |
| 11 | [前端页面指南](11-frontend.md) | Vue3 前端、菜单结构、页面功能 |
| 12 | [数据库表结构](12-database-schema.md) | 3 库总览、表结构、字段说明 |
| 13 | [部署与运维](13-deployment.md) | 启动脚本、备份、日志、FAQ |

## 相关项目

- **tz2.0** (`C:\myspace\tz2.0`) — 上层交易分析平台，通过 Python import 和直接读取 SQLite 文件依赖 tz-data
- **tz-ai** (`C:\tz-ai`) — AI 交易分析平台，同样依赖 tz-data 提供的数据和 API
