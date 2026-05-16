# 快速入门

> 版本：v0.7.0 | 最后更新：2026-05-15

## 项目简介

tz-data 是中国期货/期权市场统一数据平台，负责从交易所（CFFEX/SHFE/DCE/CZCE/INE）和数据源（Tushare/CFMMC/AkShare）下载、解析、存储行情和交易数据，并提供 REST API 和 Python SDK 查询接口。

**为谁服务**：
- **tz2.0** — 上层交易分析平台，通过 Python import 和直接读取 SQLite 文件依赖 tz-data
- **tz-ai** — AI 交易分析平台，同样依赖 tz-data 提供的数据和 API

**与下游项目的关系**：
- tz-data 是纯数据层，独立运行（后端 8000 / 前端 3000）
- tz2.0 和 tz-ai **不通过 HTTP 调用** tz-data API，而是直接 `import tzdata_pkg` 或读取 SQLite 文件

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 必需 |
| Node.js | 18+ | 前端构建（可选） |
| Redis | 6+ | Celery 任务队列，Windows 推荐 Memurai |
| SQLite | 3.x | 内置，无需安装 |
| Git | 2.x | 版本控制 |

**可选组件**：
- PostgreSQL — 生产环境元数据存储（开发用 SQLite 即可）
- QuestDB — 时序数据存储（端口 9000/8812）

## 安装

```bash
cd C:\myspace\tz-data

# 从源码安装（推荐开发使用）
pip install -e ".[dev]"

# 或仅安装运行依赖
pip install -e .
```

## 环境变量

核心环境变量在 `.env` 文件中配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TZ_DATA_DIR` | 数据目录路径 | `C:\myspace\tz-data\data` |
| `TUSHARE_TOKEN` | Tushare API Token | 无（未设置则跳过 Tushare 下载） |
| `CFMMC_COOKIES_DIR` | CFMMC Cookie 目录 | `C:\myspace\tz-data\data\cfmmc\cookies\` |
| `BACKEND_HOST` | 后端监听地址 | `0.0.0.0` |
| `BACKEND_PORT` | 后端端口 | `8000` |
| `CELERY_BROKER_URL` | Celery 消息代理 | `redis://localhost:6379/0` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `LOG_DIR` | 日志目录 | `C:\myspace\tz-data\logs` |

Windows PowerShell 中设置：
```powershell
$env:TUSHARE_TOKEN = "your_token_here"
```

## 快速启动

### 方式一：交互式菜单（推荐）

```cmd
quick-start.bat
```

按提示选择：启动全部服务 / 仅后端 / 仅前端 / 停止服务。

### 方式二：一键启动

```cmd
start.bat
```

自动启动 Celery Worker（gevent pool）+ FastAPI 后端。

### 方式三：分别启动

```cmd
# 启动 Celery Worker + FastAPI 后端
start-backend.bat

# 启动前端开发服务器（另一个终端）
start-frontend.bat
```

### 停止服务

```cmd
stop.bat
```

## 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 API | 8000 | FastAPI + Uvicorn |
| 前端 | 3000 | Vite 开发服务器 |
| Celery Worker | 系统分配 | `--pool=gevent` |
| Celery Flower | 5555 | 任务监控面板 |
| Redis | 6379 | Celery broker |

## 验证安装

```bash
# 查看版本
tzdata --version

# 查看数据状态（表行数统计）
tzdata status

# 数据质量检查
tzdata validate
```

## 数据库

启动后自动创建 3 个 SQLite 数据库（WAL 模式）：

| 数据库 | 内容 | 路径 |
|--------|------|------|
| `tzdata_market.db` | 行情、持仓、合约、元数据 | `data/tzdata_market.db` |
| `tzdata_trading.db` | 账单、交易、账户、策略 | `data/tzdata_trading.db` |
| `tzdata_analysis.db` | 机构特征、信号、期权特征 | `data/tzdata_analysis.db` |

## 下一步

- [系统架构](02-architecture.md) — 了解整体架构设计
- [API 接口文档](03-api-reference.md) — 查看所有 HTTP 接口
- [CLI 使用指南](04-cli-guide.md) — 学习命令行操作
- [Celery 任务调度](10-celery-tasks.md) — 了解定时任务配置
