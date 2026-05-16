# Python SDK 使用指南

> 版本：v0.7.0 | 最后更新：2026-05-15

## TzDataClient 基本使用

```python
from tzdata_pkg.query import TzDataClient

# 方式一：上下文管理器（推荐，自动管理连接）
with TzDataClient() as client:
    quotes = client.quotes(exchange="CFFEX", contract="MO2505")

# 方式二：手动管理
client = TzDataClient()
try:
    quotes = client.quotes(exchange="CFFEX", contract="MO2505")
finally:
    client.close()
```

## 行情查询

```python
# 查询单个合约
quotes = client.quotes(exchange="CFFEX", contract="MO2505")

# 日期范围查询
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

## 持仓查询

```python
# 查询某合约某日持仓
positions = client.positions(contract="MO2505", trade_date="2025-05-01")

# 查询合约所有持仓历史
positions = client.positions(contract="MO2505")
```

## 账单与交易

```python
# 查询账单
bills = client.bills(account_id="ACC001")

# 查询交易记录
trades = client.trades(
    account_id="ACC001",
    start_date="2025-01-01",
    end_date="2025-05-01",
)

# 查询盈亏汇总
pnl = client.pnl_summary(
    account_id="ACC001",
    start_date="2025-01-01",
    end_date="2025-05-01",
)
```

## 分析数据

```python
# 交易信号
signals = client.signals(signal_type="trend")

# 市场状态
regime = client.market_regime(trade_date="2025-05-01")

# 机构特征
features = client.institution_features(product="MO")

# 期权特征
option_feat = client.option_features(product="MO")

# 系统状态
status = client.status()
```

## 维护模块 Python API

### 数据目录

```python
from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

# 创建目录
catalog_id = CatalogManager.create_catalog(
    catalog_name="中金所-IM-日线",
    exchange_code="CFFEX",
    product_code="IM",
    data_type="daily",
    frequency="1d",
    data_source="tushare",
    sync_mode="incremental"
)

# 列出目录
catalogs = CatalogManager.list_catalogs(is_enabled=True)
```

### 同步引擎

```python
from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine

engine = SyncEngine(catalog_id=1, mode='incremental')
result = engine.execute()

print(f"Success: {result.success}")
print(f"Records fetched: {result.records_fetched}")
```

### Celery 任务

```python
from tzdata_pkg.scheduler.tasks.sync_tasks import sync_catalog_task

task = sync_catalog_task.delay(catalog_id=1, mode='incremental')
print(f"Task ID: {task.id}, Status: {task.status}")
```

### 质量评估

```python
from tzdata_pkg.maintenance.monitoring.quality_evaluator import QualityEvaluator

quality = QualityEvaluator.evaluate_catalog_quality(catalog_id=1)
print(f"Total score: {quality['total_score']}")
print(f"Quality level: {quality['quality_level']}")
```

### 健康快照

```python
from tzdata_pkg.maintenance.monitoring.health_snapshot import HealthSnapshotGenerator

snapshot = HealthSnapshotGenerator.generate_snapshot()
print(f"Total catalogs: {snapshot['summary']['total_catalogs']}")
print(f"Avg quality: {snapshot['summary']['avg_quality_score']}")
```

### 交易日历

```python
from tzdata_pkg.maintenance.metadata.trade_calendar_manager import TradeCalendarManager
from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator

# 查询是否交易日
DateCalculator.is_trading_day("CFFEX", "2026-05-14")

# 获取下一个交易日
DateCalculator.get_next_trading_day("CFFEX", "2026-05-14")

# 两个日期间交易日数
DateCalculator.get_trading_days_count("CFFEX", "2026-01-01", "2026-05-14")
```

### 主力合约

```python
from tzdata_pkg.maintenance.metadata.main_contract import MainContractManager

# 自动填充（基于持仓量）
MainContractManager.auto_populate(product_code="MO", start_date="2026-01-01", end_date="2026-05-14")

# 手动设置
MainContractManager.set_main_contract("MO", "2026-03-15", "MO2506", "手动设置")

# 查询序列
series = MainContractManager.get_series("MO", start_date="2026-01-01", end_date="2026-05-14")
```

### 交易时间

```python
from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager

TradingHoursManager.create_template(
    template_name="CFFEX-股指",
    exchange_code="CFFEX",
    product_type="futures",
    normal_schedule=[("09:30", "11:30"), ("13:00", "15:00")],
    auction_schedule=[("09:25", "09:30")]
)
```

## 下一页

- [数据维护与同步](06-data-maintenance.md) — 深入了解维护模块
- [账单与交易管理](07-bill-management.md) — 账单解析和开平匹配
