# 数据维护与同步

> 版本：v0.7.0 | 最后更新：2026-05-17

## 系统架构

tz-data v0.5.0+ 引入了完整的数据维护与同步系统，包含以下核心模块：

- **数据目录管理** — 统一管理需要跟踪的数据项
- **同步引擎** — 支持增量/全量同步、断点续传
- **质量评估** — 多维度数据质量评分（完整性/准确性/一致性）
- **健康快照** — 综合监控指标的快速查询
- **任务队列** — Celery + Redis 分布式任务调度

## 数据目录管理

### 创建目录

```python
from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

catalog_id = CatalogManager.create_catalog(
    catalog_name="中金所-IM-日线",
    exchange_code="CFFEX",
    product_code="IM",
    data_type="daily",
    frequency="1d",
    data_source="tushare",
    sync_mode="incremental"
)
```

### 查询目录

```python
# 列出所有启用目录
catalogs = CatalogManager.list_catalogs(is_enabled=True)

# 按交易所/产品筛选
catalogs = CatalogManager.list_catalogs(exchange_code="CFFEX", product_code="MO")
```

### 更新目录

通过 API：
```
PUT /api/maintenance/catalogs/{id}
Body: { "sync_mode": "full", "is_enabled": true, ... }
```

## 同步引擎

### 同步模式

| 模式 | 说明 |
|------|------|
| `incremental` | 从上次同步日期开始，只下载新数据 |
| `full` | 全量同步，清空现有数据后重新下载 |

### 触发同步

**方式 1: Celery 任务（推荐）**
```python
from tzdata_pkg.scheduler.tasks.sync_tasks import sync_catalog_task
task = sync_catalog_task.delay(catalog_id=1, mode='incremental')
```

**方式 2: 直接调用 SyncEngine**
```python
from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine

engine = SyncEngine(catalog_id=1, mode='incremental')
result = engine.execute()
```

**方式 3: CLI**
```bash
python -m tzdata_pkg.cli.sync_catalogs sync --id 1 --mode incremental
```

### 断点续传

同步引擎记录 `sync_task` 表中的进度，支持中断后从断点继续。

### 同步状态查询

```
GET /api/maintenance/sync/status
```

返回：
```json
{
  "success": true,
  "data": {
    "task_id": "...",
    "status": "success",
    "catalog_id": 1,
    "mode": "incremental",
    "records_fetched": 150,
    "started_at": "...",
    "completed_at": "..."
  }
}
```

## 数据质量评估

### 完整性检查

```python
from tzdata_pkg.maintenance.monitoring.completeness_checker import CompletenessChecker

result = CompletenessChecker.check_catalog_completeness(catalog_id=1)
print(f"Expected days: {result['expected_days']}")
print(f"Actual days: {result['actual_days']}")
print(f"Completeness: {result['completeness_pct']}%")
print(f"Missing dates: {result['missing_dates'][:5]}")
```

### 质量评估

```python
from tzdata_pkg.maintenance.monitoring.quality_evaluator import QualityEvaluator

quality = QualityEvaluator.evaluate_catalog_quality(catalog_id=1)
print(f"Total score: {quality['total_score']}")
print(f"Completeness: {quality['scores']['completeness']}")
print(f"Accuracy: {quality['scores']['accuracy']}")
print(f"Consistency: {quality['scores']['consistency']}")
```

### 差异对比

```python
from tzdata_pkg.maintenance.monitoring.diff_engine import DiffEngine

result = DiffEngine.compare_data_sources(
    contract_code="IM2506",
    source_a="tushare",
    source_b="cffex",
    start_date="2025-01-01",
    end_date="2025-05-01"
)
```

## 健康快照

### 生成快照

```python
from tzdata_pkg.maintenance.monitoring.health_snapshot import HealthSnapshotGenerator

snapshot = HealthSnapshotGenerator.generate_snapshot()
```

### 查询快照

```
GET /api/maintenance/health/snapshot       # 最新快照
GET /api/maintenance/health-snapshots      # 历史列表
GET /api/maintenance/health/diff           # 两次快照差异
```

## Celery 定时同步任务

系统通过 Celery Beat 自动执行每日维护任务：

| 任务 | 时间 | 说明 |
|------|------|------|
| `mo-minute-sync` | 15:30 (交易日) | MO 期权分钟数据同步 |
| `mo-iv-sync` | 16:00 (交易日) | MO IV 数据同步 |
| `mo-underlying-sync` | 16:30 (交易日) | 标的日线数据同步 |
| `mo-position-sync` | 17:00 (交易日) | MO Top20 持仓同步 |
| `mo-market-env` | 17:30 (交易日) | MO 市场环境分析 |
| `mo-quality-check` | 18:00 (每日) | MO 数据质量检查 |
| `daily-incremental-sync` | 18:00 (每日) | 增量同步所有启用目录 |
| `daily-status-refresh` | 18:30 (每日) | 刷新数据状态 |
| `daily-completeness-check` | 19:00 (每日) | 数据完整性检查 |

查看完整调度表：[Celery 任务调度](10-celery-tasks.md)

## 异常值检测

系统每日 21:30 自动执行异常值检测，覆盖以下规则：

| 规则 | 检测条件 | 返回类型 |
|------|---------|---------|
| 价格突跃 | 相邻交易日涨跌幅 > 20% | `price_spike` |
| 成交量异常 | 当日 volume > 30 日均值 × 3 | `volume_anomaly` |
| 零价格 | close=0 但 volume>0 | `zero_price` |
| 持仓突变 | 总持仓日环比变化 > 50% | `position_spike` |
| IV 异常 | IV 日环比变化 > 0.3 | `iv_anomaly` |

```python
from tzdata_pkg.maintenance.monitoring.anomaly_detector import AnomalyDetector

detector = AnomalyDetector()
anomalies = detector.detect_all()
# [{type: 'price_spike', exchange: 'CFFEX', contract: 'MO2506', ...}, ...]
```

API 端点：
```
GET /api/maintenance/beat-tasks?days=7   # Beat 任务执行记录
```

## 前端操作

通过前端「数据维护」菜单可可视化操作：
- 数据维护看板 — 总览同步状态和质量评分
- 数据目录 — 创建/编辑/启用/禁用目录
- 同步任务 — 查看任务状态、手动触发

## 下一页

- [账单与交易管理](07-bill-management.md) — 账单解析和开平匹配
- [MO 期权数据同步](09-mo-data-sync.md) — MO 专项数据同步
