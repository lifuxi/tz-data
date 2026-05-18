# 系统架构

> 版本：v0.8.0 | 最后更新：2026-05-18

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据源层 (Sources)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │ CFFEX    │ │ SHFE     │ │ Tushare  │ │ CFMMC    │ │AkShare ││
│  │(爬虫)    │ │(爬虫)    │ │(API)     │ │(Selenium)│ │(API)   ││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘│
└───────┼─────────────┼─────────────┼─────────────┼──────────┼─────┘
        │             │             │             │          │
┌───────▼─────────────▼─────────────▼─────────────▼──────────▼─────┐
│                     下载器层 (Downloaders)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │cffex/    │ │shfe/     │ │tushare/  │ │cfmmc/    │            │
│  │unified   │ │akshare   │ │client    │ │scraper   │            │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘            │
└───────┼─────────────┼─────────────┼─────────────┼────────────────┘
        │             │             │             │
┌───────▼─────────────▼─────────────▼─────────────▼────────────────┐
│                     存储层 (Storage)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │market_store  │  │trading_store │  │analysis_store        │   │
│  │SQLite+QuestDB│  │SQLite Pool   │  │SQLite Pool           │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
└─────────┼─────────────────┼─────────────────────┼───────────────┘
          │                 │                     │
┌─────────▼─────────────────▼─────────────────────▼───────────────┐
│                  数据库层 (SQLite + QuestDB)                      │
│  ┌───────────────────┐ ┌──────────────────┐ ┌────────────────┐ │
│  │tzdata_market.db   │ │tzdata_trading.db │ │   QuestDB      │ │
│  │~20 表, ~1.6M 行   │ │~30 表, ~923K 行  │ │ future_minute  │ │
│  └───────────────────┘ └──────────────────┘ │ daily_quotes   │ │
│                                              └────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
          │                 │                     │
┌─────────▼─────────────────▼─────────────────────▼───────────────┐
│                    服务层 (Services)                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │FastAPI (8000)    │  │Celery Worker     │  │Python SDK     │ │
│  │REST API + Swagger│  │Beat 定时任务     │  │TzDataClient   │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                    前端层 (Vue3 / 3000)                           │
│  Element Plus + ECharts + Vue Router + Pinia                    │
└─────────────────────────────────────────────────────────────────┘
```

## 数据库架构

### 3 库总览

| 数据库 | 用途 | 核心表数 | 典型数据量 |
|--------|------|---------|-----------|
| `tzdata_market.db` | 行情、持仓、合约、元数据 | ~20 | ~1.6M 行 |
| `tzdata_trading.db` | 账单、交易、账户、策略 | ~30 | ~923K 行 |
| `tzdata_analysis.db` | 机构特征、信号、期权特征 | ~18 | ~5.6K 行 |

### 统一 vs 遗留

自 v0.3.0 起，tz-data 将原本分散的 12 个 SQLite 数据库整合为 3 个统一数据库。迁移路径：

```
遗留 12 库                          统一 3 库
──────────                         ──────────
cffex.db ────────────────────┐
cffex_minute_data.db ────────┤──→ tzdata_market.db
shfe.db ─────────────────────┘

bills.db ────────────────────┐
option_sim.db ───────────────┤──→ tzdata_trading.db

institution.db ──────────────┐
tushare.db ──────────────────┤──→ tzdata_analysis.db
trading.db (分析部分) ────────┘
```

### 核心表统计

| 数据库 | 表名 | 行数 | 说明 |
|--------|------|------|------|
| Market | `daily_quotes` | ~967K | 统一日线行情 |
| Market | `position_detail` | ~639K | CFFEX 机构持仓 |
| Market | `contracts` | ~106 | 合约定义 |
| Trading | `cffex_daily_settlement` | ~889K | 中金所结算价 |
| Trading | `trades` | ~13.5K | 交易明细 |
| Trading | `matched_trades` | ~9.9K | 开平配对 |
| Trading | `trade_performance` | ~9.9K | 交易绩效 |
| Analysis | `feature_daily` | ~5.5K | 日度综合特征 |
| Analysis | `option_sim_iv_series` | ~30K | 期权 IV 序列 |

## 数据流

### 行情数据流

```
交易所网站 (CFFEX/SHFE)
  → 爬虫下载 HTML/CSV
  → 解析器提取行情数据
  → SQLite 存储 (daily_quotes/position_detail)
  → API/SDK 查询
```

### Tushare 数据流

```
Tushare API (opt_mins/opt_daily/fut_mins)
  → TushareClient 调用
  → 下载器 (MOMinuteDownloader 等)
  → SQLite 存储 (mo_minute_quotes 等)
  → API/SDK 查询
```

### 账单数据流

```
CFMMC 网站 (Selenium 自动登录)
  → 下载 HTML 账单
  → CFMMCParser 解析
  → 写入 trades 表
  → TradeMatcher FIFO 开平匹配
  → matched_trades + trade_performance
```

## 技术栈

### 后端

| 组件 | 版本/库 | 用途 |
|------|---------|------|
| Python | 3.11+ | 运行环境 |
| FastAPI + Uvicorn | — | REST API 服务 |
| Celery + Redis | — | 分布式任务队列 |
| APScheduler | — | 下载任务调度 |
| SQLite | WAL 模式 | 主数据库 |
| QuestDB | 9.3.5 | 时序数据库（可选） |
| requests/httpx | — | HTTP 请求 |
| pandas/numpy | — | 数据处理 |
| BeautifulSoup4 | — | HTML 解析 |
| Selenium | — | CFMMC 自动下载 |
| Tushare | — | 金融数据 API |
| AkShare | — | 开源金融数据 |
| Click | — | CLI 框架 |

### 前端

| 组件 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4 | 前端框架 |
| Vite | 5 | 构建工具 |
| Element Plus | 2.5 | UI 组件库 |
| Vue Router | 4 | 路由 |
| Pinia | 2 | 状态管理 |
| ECharts | 5 | 图表 |
| Axios | 1.6 | HTTP 客户端 |
| dayjs | 1.11 | 日期处理 |

## 模块划分

```
src/tzdata_pkg/
├── api/              # FastAPI 路由（8 个路由模块）
│   ├── server.py     # 应用入口
│   └── routes/
│       ├── market.py         # /api/v1/market/*
│       ├── positions.py      # /api/v1/positions/*
│       ├── trading.py        # /api/v1/bills, /trades, /pnl
│       ├── analysis.py       # /api/v1/signals, /regime
│       ├── admin.py          # /api/v1/admin/*
│       ├── maintenance.py    # /api/maintenance/* (~60 端点)
│       ├── data_layer.py     # /api/v1/bills/*/fund-flows 等
│       ├── realtime_market.py  # 实时行情 API
│       └── v2.py             # /api/v2/* （含多周期频率查询）
├── core/             # 基础设施
│   ├── db.py         # SQLite 连接池
│   ├── exceptions.py # 自定义异常
│   ├── constants.py  # 交易所代码、品种定义
│   └── monitoring.py # 告警管理
├── storage/          # 存储层
│   ├── db_registry.py      # 数据库注册与连接（含 QuestDB）
│   ├── market_store.py     # 市场数据 CRUD
│   ├── questdb_store.py    # QuestDB 时序存储
│   ├── trading_store.py    # 交易数据 CRUD
│   ├── analysis_store.py   # 分析数据 CRUD
│   └── schemas/            # SQL 建表脚本
├── download/         # 下载器
│   ├── cffex/        # CFFEX 日线/持仓
│   ├── shfe/         # SHFE 日线
│   ├── tushare/      # Tushare API（含 MO 分钟）
│   ├── cfmmc/        # CFMMC 账单下载
│   └── akshare/      # AkShare 数据
├── query/            # Python SDK
│   ├── client.py     # TzDataClient 主入口
│   ├── market.py     # 行情查询
│   ├── trading.py    # 交易查询
│   └── analysis.py   # 分析查询
├── scheduler/        # 任务调度
│   ├── celery_app.py # Celery 应用 + Beat 配置
│   └── tasks/        # 任务模块（10+ 文件）
├── maintenance/      # 维护系统
│   ├── metadata/     # 目录/合约/日历/主力合约管理
│   ├── monitoring/   # 健康快照/质量评估
│   ├── statements/   # 账单解析/开平匹配
│   ├── sources/      # 数据源管理
│   ├── sync/         # 同步控制
│   └── analysis/     # 行情分析（重采样、机构、市场状态、信号）
├── parser/           # 账单 HTML 解析
├── verify/           # 数据校验
├── migration/        # 12→3 库迁移工具
├── market/           # 行情模块（事件日志、质量校验、状态服务）
├── analysis/         # 分析模块（HV 计算、IV 基准下载）
├── models/           # 数据模型（交易模型、版本模型）
├── cli/              # CLI 脚本
└── config.py         # 配置管理
```

## 端口分配

| 服务 | 端口 | 启动方式 |
|------|------|----------|
| 后端 API | 8000 | `uvicorn tzdata_pkg.api.server:app --port 8000` |
| 前端 | 3000 | `npm run dev` (frontend 目录) |
| Celery Worker | 系统分配 | `celery -A tzdata_pkg.scheduler.celery_app worker --pool=gevent` |
| Celery Flower | 5555 | `celery -A tzdata_pkg.scheduler.celery_app flower --port=5555` |
| Redis | 6379 | 外部服务（Memurai/WSL Redis） |
| QuestDB | 9000/8812 | 外部服务（可选） |

> **Windows 注意**：Celery worker 必须使用 `--pool=gevent` 参数，不支持默认 `prefork` 池。

## 下一步

- [API 接口文档](03-api-reference.md) — 查看所有 HTTP 接口
- [数据维护与同步](06-data-maintenance.md) — 了解目录管理和同步引擎
- [Celery 任务调度](10-celery-tasks.md) — 了解定时任务配置
- [数据库表结构](12-database-schema.md) — 查看完整表结构
