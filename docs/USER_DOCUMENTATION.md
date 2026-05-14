# tz-data 用户文档

> 版本：0.6.0 | 最后更新：2026-05-14

---

## 1. 系统简介

tz-data 是**期货/期权数据统一管理平台**，为上层应用（tz2.0 交易系统、tz-ai 分析系统）提供标准化的数据服务。

### 核心能力

- **多源下载**：CFFEX、SHFE、Tushare、CFMMC 四大数据源
- **统一存储**：12 个分散数据库整合为 3 个统一 SQLite 库
- **账单解析**：自动解析 CFMMC 账单，提取交易明细、配对交易、策略分析
- **定时调度**：Celery Beat 每日自动下载最新数据，无需人工干预
- **质量监控**：数据完整性、准确性、一致性多维度评分
- **滑点对账**：账单执行价格 vs 市场价格（VWAP/结算价）
- **API 服务**：FastAPI 提供 RESTful 接口，支持 Python SDK 调用

---

## 2. 快速入门

### 2.1 安装

```bash
cd C:\myspace\tz-data
pip install -e .
```

### 2.2 环境变量

```powershell
$env:TZ_DATA_DIR = "C:\myspace\tz-data\data"
$env:TUSHARE_TOKEN = "your_tushare_token"      # Tushare 下载需要
$env:CFMMC_COOKIES_DIR = "C:\myspace\tz-data\data\cfmmc\cookies\"  # CFMMC 需要
```

### 2.3 验证安装

```bash
tzdata --version    # 显示 0.3.0
tzdata status       # 查看各表行数
tzdata validate     # 数据质量检查
```

### 2.4 启动服务

```bash
# 启动 API 服务（端口 8000）
tzdata serve --port 8000

# 开发模式（代码变更自动重启）
tzdata serve --reload
```

启动后访问 `http://localhost:8000/docs` 查看 Swagger API 文档。

---

## 3. 日常操作

### 3.1 下载数据

#### CFFEX（中金所）

```bash
# 下载 MO 品种日线
tzdata download cffex --product MO --incremental

# 下载指定日期范围
tzdata download cffex --product MO --from 2026-01-01 --to 2026-05-01

# 下载持仓排名
tzdata download cffex --product MO --data-type position --from 2026-01-01 --to 2026-05-01
```

支持品种：`MO`（中证 1000 股指期权）、`IM`（中证 1000 股指期货）、`IC`、`IF`、`IH`、`IO`、`HO`

#### SHFE（上期所）

```bash
tzdata download shfe --product AU --incremental
```

支持品种：`AU`（黄金）、`AG`（白银）、`CU`（铜）、`AL`（铝）、`ZN`（锌）等

#### Tushare

```bash
# 日线
tzdata download tushare --type daily --underlying MO --from 2026-01-01 --to 2026-05-01

# 分钟K线
tzdata download tushare --type minute --underlying MO --from 2026-01-01 --to 2026-05-01

# 期权（希腊值、IV）
tzdata download tushare --type option --underlying MO --from 2026-01-01 --to 2026-05-01
```

#### CFMMC（监控中心）

```bash
# 自动下载（使用存储的 Cookie）
tzdata download cfmmc --auto
```

### 3.2 查询数据

```bash
# 查询行情
tzdata query quotes --exchange CFFEX --contract MO2505

# 查询持仓
tzdata query positions --contract MO2505 --date 2026-05-01

# 查询账单
tzdata query bills --account-id ACC001

# 查询盈亏
tzdata query pnl --account-id ACC001 --from 2026-01-01 --to 2026-05-01
```

### 3.3 账单导入

```bash
# 批量导入账单文件
tzdata import-bills --dir C:\myspace\tz-data\data\bills\raw

# 预览模式（只解析不入库）
tzdata import-bills --dry-run
```

### 3.4 数据验证

```bash
# 账单对账（解析文件 vs 数据库）
tzdata verify bills

# 跨库一致性检查
tzdata verify cross-db

# 分析结果验证
tzdata verify analysis

# 全部检查
tzdata verify all
```

### 3.5 调度器

```bash
# 查看任务列表
tzdata schedule list

# 立即执行某个任务
tzdata schedule run cffex_daily

# 启动调度器（前台）
tzdata schedule start

# 仅执行特定任务
tzdata schedule start --jobs cffex_daily,shfe_daily
```

### 3.6 数据库迁移

```bash
# 预览迁移内容
tzdata migrate --dry-run

# 执行 12→3 迁移
tzdata migrate

# 验证迁移结果
tzdata migrate --verify
```

---

## 4. Python SDK

### 4.1 基本使用

```python
from tzdata_pkg.query import TzDataClient

with TzDataClient() as client:
    # 行情查询
    quotes = client.quotes(exchange="CFFEX", contract="MO2505")
    
    # 持仓查询
    positions = client.positions(contract="MO2505", trade_date="2026-05-01")
    
    # 账单查询
    bills = client.bills(account_id="ACC001")
    
    # 盈亏汇总
    pnl = client.pnl_summary(account_id="ACC001")
```

### 4.2 维护模块

```python
# 数据目录管理
from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

catalog_id = CatalogManager.create_catalog(
    catalog_name="中金所-IM-日线",
    exchange_code="CFFEX",
    product_code="IM",
    data_type="daily",
    data_source="tushare",
    sync_mode="incremental"
)

# 触发同步
from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine
engine = SyncEngine(catalog_id=1, mode='incremental')
result = engine.execute()

# 质量评估
from tzdata_pkg.maintenance.monitoring.quality_evaluator import QualityEvaluator
quality = QualityEvaluator.evaluate_catalog_quality(catalog_id=1)
print(f"质量评分: {quality['total_score']}")
```

---

## 5. 前端使用

### 5.1 启动前端

```bash
cd C:\myspace\tz-data\frontend
npm install      # 首次需要
npm run dev      # 启动开发服务器，端口 3000
```

### 5.2 页面功能

前端菜单按功能分为 4 组：

#### 数据维护
- **数据维护看板（/dashboard）**：总览所有数据目录的同步状态、平均质量评分、有问题的目录数量、一键生成健康快照
- **数据目录（/catalogs）**：查看/创建/编辑数据目录，每个目录定义：交易所 × 品种 × 数据类型 × 数据源，支持按交易所、产品筛选
- **同步任务（/sync-tasks）**：查看同步任务状态（pending/running/success/failed）、手动触发同步（全量/增量）、查看任务进度和错误信息
- **健康快照（/health-snapshots）**：历史健康快照列表、点击查看详情（缺失日期、质量评分、同步状态）、按目录对比数据质量变化

#### 基础数据
- **交易所管理（/exchanges）**：交易所配置、启用/禁用
- **品种管理（/products）**：品种配置、跟踪状态管理、合约乘数/最小变动价位/保证金率/期权类型
- **合约管理（/contracts）**：合约信息维护、上市/到期日期管理
- **交易日历（/trade-calendar）**：中国期货交易日历、按交易所查看交易/非交易日统计、添加非交易日、系统初始化
- **特殊日期（/special-dates）**：特殊日期覆盖管理、补市/休市标记、按交易所筛选
- **主力合约（/main-contracts）**：品种主力合约序列、持仓量驱动自动填充、手动设置主力合约
- **交易时间模板（/trading-hours）**：日盘/夜盘/集合竞价时段配置、按交易所筛选

#### 账单与账户
- **账户管理（/accounts）**：添加期货账户（账户名、账号、期货公司）、管理 CFMMC 凭据（用户名/密码，AES-256 加密存储）、查看最后同步时间
- **账单管理（/statements）**：上传账单文件、查看解析状态（uploaded/parsing/parsed/error）、余额平衡校验、滑点对账

#### 系统
- **数据源配置（/data-sources）**：统一管理入口（3 个 Tab）— 数据源管理、交易日历、账户凭证
- **告警历史（/alerts）**：查看所有告警（info/warning/error/critical）、按级别、类别筛选

---

## 6. 交易日历模块 v0.6.0

### 6.1 功能概览

v0.6.0 新增完整的交易日历管理能力：

| 能力 | 说明 |
|------|------|
| 交易日历 | 维护各交易所交易日历，支持节假日覆盖、非交易日标记 |
| 特殊日期覆盖 | 补市/休市覆盖，优先级高于常规日历 |
| 主力合约识别 | 持仓量驱动自动填充 + 手动设置主力合约序列 |
| 交易时间模板 | 定义日盘/夜盘/集合竞价时段 |
| 产品合约增强 | 合约乘数、最小变动价位、保证金率、期权类型 |
| 日期计算器 | 计算下一个/上一个交易日、月份首个/最后个交易日 |

### 6.2 初始化日历

```bash
PYTHONPATH=src python -m tzdata_pkg.cli.calendar_system_init
```

一键初始化 1990-2026 年交易日历和产品数据。

### 6.3 新增数据库表

| 表 | 所在库 | 说明 |
|----|--------|------|
| `main_contract_series` | market.db | 主力合约序列 |
| `special_dates` | market.db | 特殊日期覆盖 |
| `trading_hours_templates` | market.db | 交易时间模板 |

`product_config` 表增强：新增 `multiplier`、`price_tick`、`margin_rate`、`option_style` 字段。

---

## 7. 数据库结构

### 6.1 统一架构（3 库，SQLite）

| 数据库 | 用途 | 核心表 |
|--------|------|--------|
| `tzdata_market.db` | 行情、持仓、合约、元数据 | daily_quotes(967K), position_detail(639K) + 维护表 |
| `tzdata_trading.db` | 账单、交易、账户、策略 | cffex_daily_settlement(889K), trades(13.5K) + 维护表 |
| `tzdata_analysis.db` | 机构特征、信号 | feature_daily(5.5K) |

### 6.2 v0.5.0 新增维护表

| 表 | 所在库 | 说明 |
|----|--------|------|
| `exchange_config` | market.db | 交易所配置 |
| `product_config` | market.db | 品种配置 |
| `contract_info` | market.db | 合约维护信息 |
| `data_catalog` | market.db | 数据目录 |
| `data_status_local` | market.db | 本地数据状态 |
| `data_status_remote` | market.db | 远程数据状态 |
| `data_health_snapshot` | market.db | 健康快照 |
| `sync_task` | market.db | 同步任务（含断点续传） |
| `trade_calendar` | market.db | 中国交易日历（2025-2026 节假日） |
| `data_diff_log` | market.db | 跨数据源差异对比日志 |
| `futures_accounts` | trading.db | 期货账户（含加密凭证） |
| `statement_status` | trading.db | 账单状态跟踪 |
| `bills` | trading.db | 账单主表 |
| `bill_raw_sections` | trading.db | 账单原始内容 |

---

## 7. 常见问题

### Q1: 如何查看数据是否最新？

```bash
tzdata status
```
查看各表的最新行数，对比上一次记录。

### Q2: Tushare 下载失败？

确认已设置 `TUSHARE_TOKEN` 环境变量，且账户积分足够（部分接口需 2000+ 积分）。

### Q3: CFMMC 无法自动下载？

Cookie 可能已过期。手动登录 https://investors.cfmmc.com/，导出 Cookie 到 `data/cfmmc/cookies/` 目录。或通过前端「账户管理」页面更新 CFMMC 凭据。

### Q4: 数据库锁定？

SQLite 不支持多进程同时写入。Celery 任务已通过并发控制器（全局信号量 + 目录锁）确保不会并发写入同一目录。

### Q5: 如何备份数据？

```powershell
$backup_dir = "C:\myspace\tz-data\backups\$(Get-Date -Format 'yyyyMMdd')"
New-Item -ItemType Directory -Path $backup_dir -Force
Copy-Item data\tzdata_*.db $backup_dir\
```

### Q6: 端口被占用？

tz-data 默认使用端口 8000（后端）和 3000（前端）。如被占用，启动时指定其他端口：

```bash
tzdata serve --port 8100
```

---

## 8. 与 tz2.0 的关系

tz-data 作为**数据层**为 tz2.0 提供数据服务：

| 依赖方式 | 说明 |
|----------|------|
| Python import | tz2.0 直接 `import tzdata_pkg` 使用 SDK |
| SQLite 文件 | tz2.0 直接读取 `tzdata_market.db`、`tzdata_trading.db` 等 |
| API（可选） | 通过 FastAPI HTTP 接口查询 |

**端口关系**：

| 服务 | 端口 |
|------|------|
| tz-data 后端 | 8000 |
| tz-data 前端 | 3000 |
| tz2.0 后端 | 8200 |
| tz2.0 前端 | 3200 |
