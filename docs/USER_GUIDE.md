# tz-data 用户手册

> 版本：0.5.0 | 数据维护与同步系统 | 最后更新：2026-05-13

## 目录

1. [快速入门](#1-快速入门)
2. [CLI 命令使用指南](#2-cli-命令使用指南)
3. [Python SDK 使用指南](#3-python-sdk-使用指南)
4. [数据查询示例](#4-数据查询示例)
5. [账单管理](#5-账单管理)
6. [数据维护与同步](#6-数据维护与同步)
7. [监控告警系统](#7-监控告警系统)
8. [前端页面使用](#8-前端页面使用)
9. [常见问题](#9-常见问题)

---

## 1. 快速入门

### 1.1 安装

```bash
# 从源码安装（推荐开发使用）
cd C:\myspace\tz-data
pip install -e ".[dev]"

# 或直接安装依赖后使用
pip install -e .
```

### 1.2 环境要求

**必需组件**:
- Python 3.11+
- Redis（Celery 任务队列，Windows 上可用 Memurai 或 WSL Redis）
- SQLite（内置，无需安装）

**可选组件**:
- PostgreSQL（生产环境元数据存储，开发用 SQLite 即可）
- QuestDB（时序数据存储，可选）

### 1.3 环境变量

tz-data 需要以下环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TZ_DATA_DIR` | 数据目录路径 | `C:\myspace\tz-data\data` |
| `TUSHARE_TOKEN` | Tushare API Token | 无（未设置则跳过 Tushare 下载） |
| `CFMMC_COOKIES_DIR` | CFMMC Cookie 目录 | `C:\myspace\tz-data\data\cfmmc\cookies\` |

在 Windows PowerShell 中设置：

```powershell
$env:TZ_DATA_DIR = "C:\myspace\tz-data\data"
$env:TUSHARE_TOKEN = "your_tushare_token_here"
```

### 1.4 验证安装

```bash
# 查看版本
tzdata --version

# 查看数据状态
tzdata status

# 数据质量检查
tzdata validate
```

---

## 6. 数据维护与同步 ⭐ 新增

### 6.1 系统架构

tz-data v0.5.0 引入了完整的数据维护与同步系统，包含以下核心模块：

- **数据目录管理** - 统一管理需要跟踪的数据项
- **同步引擎** - 支持增量/全量同步、断点续传
- **质量评估** - 多维度数据质量评分（完整性/准确性/一致性）
- **健康快照** - 综合监控指标的快速查询
- **任务队列** - Celery + Redis 分布式任务调度

### 6.2 启动基础设施

```bash
# Redis（Celery 任务队列）
# Windows 推荐: Memurai (Redis Windows 兼容版) 或 WSL Redis
# 或使用 Docker:
docker run -d -p 6379:6379 --name redis redis

# QuestDB（可选，时序数据存储）
docker run -d -p 8812:8812 --name questdb questdb/questdb
```

> **注意**：元数据存储使用 SQLite（`tzdata_market.db`），无需安装 PostgreSQL。生产环境可切换到 PostgreSQL。

### 6.3 初始化数据库

```bash
# PostgreSQL 元数据表
psql -U postgres -h localhost -f src/tzdata_pkg/storage/schemas/metadata.sql

# QuestDB 时序数据表
curl -G --data-urlencode "query=$(cat src/tzdata_pkg/storage/schemas/questdb.sql)" \
  http://localhost:8812/exec
```

### 6.4 启动 Celery Worker

```bash
cd src
celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info
```

### 6.5 数据目录管理

#### 创建数据目录

```python
from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

# 创建中金所 IM 日线数据目录
catalog_id = CatalogManager.create_catalog(
    catalog_name="中金所-IM-日线",
    exchange_code="CFFEX",
    product_code="IM",
    data_type="daily",
    frequency="1d",
    data_source="tushare",
    sync_mode="incremental"  # incremental 或 full
)
print(f"Created catalog with ID: {catalog_id}")
```

#### 列出数据目录

```python
# 列出所有启用的目录
catalogs = CatalogManager.list_catalogs(is_enabled=True)

for cat in catalogs:
    print(f"{cat['catalog_name']}: {cat['exchange_code']}-{cat['product_code']}")
```

### 6.6 触发数据同步

#### 方式 1: 通过 Celery 任务（推荐）

```python
from tzdata_pkg.scheduler.tasks.sync_tasks import sync_catalog_task

# 异步触发同步任务
task = sync_catalog_task.delay(
    catalog_id=1,
    mode='incremental'  # 'incremental' 或 'full'
)

# 检查任务状态
print(f"Task ID: {task.id}")
print(f"Status: {task.status}")
```

#### 方式 2: 直接调用 SyncEngine

```python
from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine

engine = SyncEngine(
    catalog_id=1,
    mode='incremental',
    task_id=None
)

result = engine.execute()

print(f"Success: {result.success}")
print(f"Records fetched: {result.records_fetched}")
print(f"Progress: {result.progress_pct}%")
```

### 6.7 数据质量检查

#### 完整性检查

```python
from tzdata_pkg.maintenance.monitoring.completeness_checker import CompletenessChecker

# 检查某个目录的完整性
result = CompletenessChecker.check_catalog_completeness(catalog_id=1)

print(f"Expected days: {result['expected_days']}")
print(f"Actual days: {result['actual_days']}")
print(f"Completeness: {result['completeness_pct']}%")
print(f"Missing dates: {result['missing_dates'][:5]}")  # 前 5 个缺失日期
```

#### 质量评估

```python
from tzdata_pkg.maintenance.monitoring.quality_evaluator import QualityEvaluator

# 评估数据质量
quality = QualityEvaluator.evaluate_catalog_quality(catalog_id=1)

print(f"Total score: {quality['total_score']}")
print(f"Quality level: {quality['quality_level']}")
print(f"Completeness: {quality['scores']['completeness']}")
print(f"Accuracy: {quality['scores']['accuracy']}")
print(f"Consistency: {quality['scores']['consistency']}")

# 告警信息
for alert in quality['alerts']:
    print(f"⚠️ {alert}")
```

#### 差异对比

```python
from tzdata_pkg.maintenance.monitoring.diff_engine import DiffEngine

# 对比两个数据源
result = DiffEngine.compare_data_sources(
    contract_code="IM2506",
    source_a="tushare",
    source_b="cffex",
    start_date="2025-01-01",
    end_date="2025-05-01"
)

print(f"Total records A: {result['count_a']}")
print(f"Total records B: {result['count_b']}")
print(f"Differences found: {len(result['differences'])}")

for diff in result['differences'][:5]:
    print(f"  {diff['date']}: close_a={diff['value_a']}, close_b={diff['value_b']}, diff={diff['difference']}")
```

### 6.8 健康快照

```python
from tzdata_pkg.maintenance.monitoring.health_snapshot import HealthSnapshotGenerator

# 生成健康快照
snapshot = HealthSnapshotGenerator.generate_snapshot()

print(f"Generated at: {snapshot['generated_at']}")
print(f"Total catalogs: {snapshot['summary']['total_catalogs']}")
print(f"Synced today: {snapshot['summary']['synced_today']}")
print(f"Avg quality score: {snapshot['summary']['avg_quality_score']}")

# 按交易所汇总
for exchange, stats in snapshot['by_exchange'].items():
    print(f"{exchange}: {stats['catalog_count']} catalogs, avg quality {stats['avg_quality']}")
```

### 6.9 Celery 定时任务

系统通过 Celery Beat 自动执行每日维护任务：

| 任务 | 时间 | 说明 |
|------|------|------|
| `daily-incremental-sync` | 18:00 | 增量同步所有启用目录 |
| `daily-status-refresh` | 18:30 | 刷新远程数据状态 |
| `daily-completeness-check` | 19:00 | 数据完整性检查 |
| `daily-bill-missing-check` | 20:00 | 检查缺失账单 |

启动 Celery Beat：

```bash
celery -A tzdata_pkg.scheduler.celery_app beat --loglevel=info
```

---

## 7. 监控告警系统

### 7.1 统一日志系统

```python
from tzdata_pkg.core.monitoring import get_logger

logger = get_logger('my_module')

# 不同级别的日志（彩色输出）
logger.debug("调试信息")      # 青色
logger.info("普通信息")       # 绿色
logger.warning("警告信息")    # 黄色
logger.error("错误信息")      # 红色
logger.critical("严重错误")   # 粗体红色
```

日志会自动输出到：
- 控制台（彩色）
- `logs/app.log`（文本格式）
- `logs/app.json.log`（JSON 格式，便于分析）

### 7.2 异常处理装饰器

```python
from tzdata_pkg.core.monitoring import handle_exceptions

@handle_exceptions('sync_module')
def sync_data():
    # 如果发生异常，会自动记录日志并发送告警
    ...
```

### 7.3 多渠道告警

#### 配置告警渠道

```python
from tzdata_pkg.core.monitoring import (
    get_alert_manager,
    dingtalk_webhook_handler,
    wechat_webhook_handler,
    email_handler
)

alert_manager = get_alert_manager()

# 钉钉机器人
alert_manager.register_handler(
    dingtalk_webhook_handler("https://oapi.dingtalk.com/robot/send?access_token=xxx")
)

# 企业微信
alert_manager.register_handler(
    wechat_webhook_handler("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx")
)

# 邮件通知
smtp_config = {
    'host': 'smtp.example.com',
    'port': 587,
    'username': 'user@example.com',
    'password': 'password',
    'from_addr': 'alerts@example.com',
    'to_addrs': ['admin@example.com'],
    'use_tls': True
}
alert_manager.register_handler(email_handler(smtp_config))
```

#### 发送告警

```python
alert_manager.send_alert(
    title="数据同步失败",
    message="IM2506 日线同步超时",
    level="error",  # info/warning/error/critical
    category="sync"
)
```

### 7.4 指标收集

```python
from tzdata_pkg.core.monitoring import get_metrics_collector

collector = get_metrics_collector()

# Counter（计数器）
collector.increment_counter('api_requests')
collector.increment_counter('api_requests', value=5)
print(collector.get_counter('api_requests'))  # 6.0

# Gauge（仪表盘）
collector.set_gauge('cpu_usage', 75.5)
print(collector.get_gauge('cpu_usage'))  # 75.5

# Histogram（直方图）
for response_time in [50, 120, 80, 200, 150]:
    collector.observe_histogram('response_time', response_time)

stats = collector.get_histogram_stats('response_time')
print(f"P50: {stats['p50']}ms, P95: {stats['p95']}ms, P99: {stats['p99']}ms")

# Timer（计时器）
with collector.timer('database_query'):
    db.execute(query)  # 自动记录执行时间

timer_stats = collector.get_histogram_stats('database_query')
print(f"Avg query time: {timer_stats['avg']*1000:.2f}ms")
```

### 7.5 告警规则引擎

```python
from tzdata_pkg.core.monitoring import AlertRule

collector = get_metrics_collector()
rule_engine = collector.rule_engine

# 添加 CPU 高负载告警规则
high_cpu_rule = AlertRule(
    name="high_cpu_usage",
    metric_name="cpu_usage",
    condition=">",
    threshold=80.0,
    duration_seconds=300,      # 必须持续 5 分钟
    cooldown_seconds=600,      # 10 分钟冷却期
    level="warning"
)
rule_engine.add_rule(high_cpu_rule)

# 添加内存临界告警（立即触发）
critical_memory_rule = AlertRule(
    name="critical_memory",
    metric_name="memory_usage",
    condition=">",
    threshold=90.0,
    duration_seconds=0,        # 立即触发
    cooldown_seconds=300,
    level="critical"
)
rule_engine.add_rule(critical_memory_rule)

# 记录指标，自动评估规则
collector.set_gauge('cpu_usage', 85.0)
collector.set_gauge('memory_usage', 95.0)  # 触发告警！
```

支持的规则条件：`>`, `<`, `>=`, `<=`, `==`, `!=`

### 7.6 测试监控系统

```bash
python tests/test_monitoring.py
```

这会运行 7 个集成测试，验证所有监控功能。

---

## 2. CLI 命令使用指南

### 2.1 下载行情数据

#### CFFEX（中金所）

```bash
# 下载 MO 品种日线（全量）
tzdata download cffex --product MO --data-type daily

# 下载指定日期范围
tzdata download cffex --product MO --from 2025-01-01 --to 2025-05-01

# 增量下载（从上次已知日期开始）
tzdata download cffex --product MO --incremental

# 下载持仓排名
tzdata download cffex --product MO --data-type position --from 2025-01-01 --to 2025-05-01
```

支持的产品代码：`MO`, `IM`, `IC`, `IF`, `IH`, `IO`, `HO`

#### SHFE（上期所）

```bash
# 下载 AU 品种日线（全量）
tzdata download shfe --product AU

# 增量下载
tzdata download shfe --product AU --incremental
```

支持的产品代码：`AU`, `AG`, `CU`, `AL`, `ZN` 等上期所品种

#### Tushare

```bash
# 下载日线
tzdata download tushare --type daily --underlying MO --from 2025-01-01 --to 2025-05-01

# 下载分钟K线
tzdata download tushare --type minute --underlying MO --from 2025-01-01 --to 2025-05-01

# 下载期权数据（希腊值、IV）
tzdata download tushare --type option --underlying MO --from 2025-01-01 --to 2025-05-01
```

#### CFMMC（中国期货市场监控中心）

```bash
# 自动下载（使用存储的 Cookie）
tzdata download cfmmc --auto

# 手动指定日期范围
tzdata download cfmmc --from 2025-01-01 --to 2025-05-01
```

### 2.2 查询数据

```bash
# 查询行情
tzdata query quotes --exchange CFFEX --contract MO2505

# 查询持仓排名
tzdata query positions --contract MO2505 --date 2025-05-01

# 查询账单
tzdata query bills --account-id ACC001

# 查询盈亏汇总
tzdata query pnl --account-id ACC001 --from 2025-01-01 --to 2025-05-01
```

### 2.3 数据库迁移

```bash
# 预览（不执行，仅显示会迁移什么）
tzdata migrate --dry-run

# 执行迁移
tzdata migrate

# 验证迁移结果（比较源/目标行数）
tzdata migrate --verify
```

### 2.4 调度器

```bash
# 启动调度器（阻塞模式，前台运行）
tzdata schedule start

# 后台模式运行
tzdata schedule start --background

# 立即运行某个任务
tzdata schedule run cffex_daily

# 查看任务列表
tzdata schedule list
```

### 2.5 API 服务

```bash
# 启动 API 服务（默认 0.0.0.0:8100）
tzdata serve

# 指定端口
tzdata serve --port 8200

# 开发模式（自动重载）
tzdata serve --reload
```

启动后访问 `http://localhost:8100/docs` 查看 Swagger 文档。

### 2.6 状态与验证

```bash
# 查看所有数据库表行数
tzdata status

# 数据质量检查
tzdata validate
```

---

## 3. Python SDK 使用指南

### 3.1 基本使用

```python
from tzdata_pkg.query import TzDataClient

# 方式一：上下文管理器（推荐）
with TzDataClient() as client:
    quotes = client.quotes(exchange="CFFEX", contract="MO2505")

# 方式二：手动管理
client = TzDataClient()
try:
    quotes = client.quotes(exchange="CFFEX", contract="MO2505")
finally:
    client.close()
```

### 3.2 行情查询

```python
# 查询单个合约
quotes = client.quotes(exchange="CFFEX", contract="MO2505")

# 查询日期范围
quotes = client.quotes(
    exchange="CFFEX",
    contract="MO2505",
    start_date="2025-01-01",
    end_date="2025-05-01",
)

# 查询所有合约
quotes = client.quotes()

# 按交易所过滤
quotes = client.quotes(exchange="SHFE")
```

### 3.3 持仓查询

```python
# 查询某合约某日持仓
positions = client.positions(contract="MO2505", trade_date="2025-05-01")

# 查询合约所有持仓历史
positions = client.positions(contract="MO2505")
```

### 3.4 账单查询

```python
# 查询账单
bills = client.bills(account_id="ACC001")

# 查询盈亏汇总
pnl = client.pnl_summary(
    account_id="ACC001",
    start_date="2025-01-01",
    end_date="2025-05-01",
)
```

### 3.5 分析数据查询

```python
# 查询交易信号
signals = client.signals(signal_type="trend")

# 查询市场状态
regime = client.market_regime(trade_date="2025-05-01")

# 查询机构特征
features = client.institution_features(product="MO")

# 查询期权特征
option_feat = client.option_features(product="MO")

# 查询系统状态
status = client.status()
```

---

## 4. 数据查询示例

### 4.1 获取 MO 品种最新行情

```python
from tzdata_pkg.query import TzDataClient

with TzDataClient() as client:
    # 获取 MO 品种所有合约的最新行情
    quotes = client.quotes(exchange="CFFEX")
    mo_quotes = [q for q in quotes if q.get("contract_code", "").startswith("MO")]
    mo_quotes.sort(key=lambda x: x.get("trade_date", ""), reverse=True)

    # 取最新日期
    latest_date = mo_quotes[0]["trade_date"] if mo_quotes else None
    latest = [q for q in mo_quotes if q.get("trade_date") == latest_date]

    for q in latest:
        print(f"{q['contract_code']} | O={q['open']} C={q['close']} V={q['volume']}")
```

### 4.2 获取持仓排名 Top 20

```python
with TzDataClient() as client:
    positions = client.positions(contract="MO2505", trade_date="2025-05-01")
    # 按多仓排序
    long_sorted = sorted(positions, key=lambda x: x.get("long_volume", 0), reverse=True)
    for p in long_sorted[:20]:
        print(f"{p['member_name']}: 多={p['long_volume']} 空={p['short_volume']}")
```

### 4.3 计算账户总盈亏

```python
with TzDataClient() as client:
    pnl = client.pnl_summary(account_id="ACC001")
    print(f"总盈亏: {pnl.get('total_pnl')}")
    print(f"胜率: {pnl.get('win_rate')}")
    print(f"交易数: {pnl.get('total_trades')}")
```

### 4.4 通过 API 查询（HTTP）

```bash
# 行情查询
curl "http://localhost:8100/api/v1/market/quotes?exchange=CFFEX&contract=MO2505"

# 持仓排名
curl "http://localhost:8100/api/v1/positions/MO"

# 账单列表
curl "http://localhost:8100/api/v1/bills?account_id=ACC001"

# 系统状态
curl "http://localhost:8100/api/v1/admin/status"
```

---

## 5. 账单管理

### 5.1 账单下载流程

1. 确保 CFMMC Cookie 已存储在 `data/cfmmc/cookies/` 目录
2. 运行自动下载：`tzdata download cfmmc --auto`
3. 账单会自动解析并存入 `tzdata_trading.db`

### 5.2 账单数据结构

| 表 | 说明 | 行数 |
|----|------|------|
| `trades` | 交易明细 | 13,534 |
| `matched_trades` | 开-平仓配对 | 9,861 |
| `trade_performance` | 交易表现分析 | 9,861 |
| `cffex_daily_settlement` | 中金所结算数据 | 888,944 |
| `strategy_performance_summary` | 策略表现汇总 | 286 |
| `account_summary` | 账户月度汇总 | 17 |

### 5.3 查询账单

```python
with TzDataClient() as client:
    # 查询账单
    bills = client.bills(account_id="ACC001")

    # 查询交易记录
    trades = client.trades(
        account_id="ACC001",
        start_date="2025-01-01",
        end_date="2025-05-01",
    )
```

---

## 8. 前端页面使用

### 8.1 启动前端

```bash
cd C:\myspace\tz-data\frontend
npm install      # 首次需要
npm run dev      # 启动开发服务器，端口 3000
```

### 8.2 菜单结构

前端侧边栏菜单按功能分为 4 组：

| 分组 | 页面 | 说明 |
|------|------|------|
| **数据维护** | 数据维护看板 | 总览同步状态、质量评分 |
| | 数据目录 | 管理跟踪的数据项 |
| | 同步任务 | 查看/触发同步任务 |
| | 健康快照 | 历史健康数据 |
| **基础数据** | 交易所管理 | 交易所配置 |
| | 品种管理 | 品种配置 |
| | 合约管理 | 合约信息维护 |
| | 交易日历 | 节假日管理 |
| **账单与账户** | 账户管理 | 期货账户 + CFMMC 凭证 |
| | 账单管理 | 账单上传/解析/导入 |
| **系统** | 数据源配置 | 数据源 + 日历 + 凭证统一管理 |
| | 告警历史 | 系统告警记录 |

### 8.3 数据维护看板

- 显示所有数据目录的同步状态
- 平均质量评分、有问题目录数量
- 一键生成健康快照

### 8.4 数据目录

- 创建目录：选择交易所 × 品种 × 数据类型 × 数据源
- 同步模式：incremental（增量）或 full（全量）
- 按交易所、产品筛选

### 8.5 同步任务

- 查看任务状态：pending / running / success / failed
- 手动触发同步
- 查看进度和错误信息

### 8.6 账户与账单

- 添加期货账户，配置 CFMMC 登录凭证（AES-256 加密存储）
- 上传账单文件（.txt 格式）
- 查看解析状态：uploaded / parsing / parsed / error
- 余额平衡校验（复式记账方程）
- 滑点对账（账单价格 vs 市场价格）

### 8.7 数据源配置

统一管理入口，包含 3 个 Tab：
- **数据源管理**：查看 tushare/cffex/shfe/wind 状态，测试连接
- **交易日历**：初始化日历、添加节假日
- **账户凭证**：管理各账户的 CFMMC 凭据

---

## 9. 常见问题

### Q1: 下载失败 "product must be specified"

**原因**：CFFEX 下载器要求显式指定产品代码。

**解决**：添加 `--product` 参数，如 `--product MO`。

### Q2: Tushare 下载报错 "token not set"

**原因**：未设置 `TUSHARE_TOKEN` 环境变量。

**解决**：
```powershell
$env:TUSHARE_TOKEN = "your_token_here"
# 或永久设置（写入环境变量）
```

### Q3: Celery Worker 无法连接 Redis

**原因**：Redis 服务未启动或端口不正确。

**解决**：
```bash
# 检查 Redis 是否运行
docker ps | grep redis

# 启动 Redis
docker run -d -p 6379:6379 redis

# 测试连接
redis-cli ping  # 应返回 PONG
```

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

前端修改 `frontend/vite.config.js` 中的 port 配置。

### Q7: 同步任务卡住不动？

**可能原因**：
1. 网络问题导致 API 请求超时
2. API 限流（系统自带 token bucket 限流器）
3. 数据库连接池耗尽

**解决**：查看前端「同步任务」页面的错误信息，或检查 Celery Worker 日志。

### Q8: Celery Worker 在 Windows 上启动失败？

Windows 上必须使用 `--pool=gevent` 参数：

```bash
celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info --pool=gevent
```

默认的 `prefork` pool 在 Windows 上不可用。

### Q9: CFMMC 无法自动下载？

Cookie 可能已过期。手动登录 https://investors.cfmmc.com/，导出 Cookie 到 `data/cfmmc/cookies/` 目录。或通过前端「账户管理」页面更新 CFMMC 凭据（用户名/密码，AES-256 加密存储）。

### Q10: 账单解析失败？

确保上传的是 CFMMC 标准格式的 `.txt` 文件。解析失败的文件可在前端「账单管理」页面查看错误信息，修正后可重新上传。
