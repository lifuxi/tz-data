# IV 数据层需求 — tz-data 工程

> 版本：v1.0
> 生成日期：2026-05-17
> 目标工程：`C:\myspace\tz-data`

---

## 一、现有基础

tz-data 已有以下 IV 相关能力：
- `src/tzdata_pkg/download/tushare/mo_iv_downloader.py` — MO IV 下载器
- `src/tzdata_pkg/download/tushare/option_downloader.py` — 通用期权下载器
- `mo_iv_snapshot` 数据表（通过 `opt_daily` 接口采集）
- `src/tzdata_pkg/core/bs_model.py` — Black-Scholes 模型
- `src/tzdata_pkg/storage/schemas/trading.sql` — MO 相关表定义

---

## 二、数据库 Schema 变更

### 2.1 扩展 `mo_iv_snapshot` 表 → 重命名为 `iv_snapshot`

```sql
-- 重命名（或新建迁移）
ALTER TABLE mo_iv_snapshot RENAME TO iv_snapshot;

-- 新增 variety 字段
ALTER TABLE iv_snapshot ADD COLUMN variety VARCHAR(4) NOT NULL DEFAULT 'MO';

-- 新增唯一索引
CREATE UNIQUE INDEX idx_iv_snapshot_unique ON iv_snapshot(
    trade_date, variety, contract_code
);

-- 新增查询索引
CREATE INDEX idx_iv_snapshot_query ON iv_snapshot(
    trade_date, variety, expiry_date, exercise_price, call_put
);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `trade_date` | date | 交易日 |
| `variety` | varchar(4) | MO/IO/HO |
| `contract_code` | string | 合约代码（如 MO2406C3900） |
| `call_put` | varchar(1) | C / P |
| `exercise_price` | float | 行权价 |
| `expiry_date` | date | 到期日 |
| `settle_price` | float | 结算价 |
| `iv` | float | 隐含波动率（小数，0.185 = 18.5%） |
| `volume` | bigint | 成交量 |
| `open_interest` | bigint | 持仓量 |
| `is_valid` | boolean | 数据质量标记 |

### 2.2 新建 `iv_benchmark` 表

```sql
CREATE TABLE iv_benchmark (
    trade_date      DATE NOT NULL,
    variety         VARCHAR(4) NOT NULL,
    atm_iv          FLOAT,
    atm_strike      FLOAT,
    spot_price      FLOAT,
    hv_20           FLOAT,
    hv_60           FLOAT,
    iv_hv_spread    FLOAT,
    skew_25delta    FLOAT,
    term_structure  TEXT,        -- JSON: {"1M": 18.5, "2M": 19.2, ...}
    iv_percentile_1y FLOAT,
    iv_regime       VARCHAR(20),
    pcr_volume      FLOAT,
    pcr_oi          FLOAT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, variety)
);

CREATE INDEX idx_iv_benchmark_date ON iv_benchmark(trade_date);
CREATE INDEX idx_iv_benchmark_variety ON iv_benchmark(variety);
```

### 2.3 新建 `iv_smile_snapshot` 表

```sql
CREATE TABLE iv_smile_snapshot (
    trade_date   DATE NOT NULL,
    variety      VARCHAR(4) NOT NULL,
    expiry_date  DATE NOT NULL,
    smile_data   TEXT,        -- JSON: {"strikes": [...], "call_iv": [...], "put_iv": [...]}
    atm_iv       FLOAT,
    skew_ratio   FLOAT,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date, variety, expiry_date)
);
```

---

## 三、采集器开发

### 3.1 重命名并扩展 `mo_iv_downloader.py` → `option_iv_downloader.py`

```python
# src/tzdata_pkg/download/tushare/option_iv_downloader.py

class OptionIVDownloader:
    """Download IV data for MO/IO/HO from Tushare opt_daily API."""

    VARIETY_MAP = {
        'MO': {'exchange': 'CFFEX', 'underlying': '000852.SH'},
        'IO': {'exchange': 'CFFEX', 'underlying': '000300.SH'},
        'HO': {'exchange': 'CFFEX', 'underlying': '000016.SH'},
    }

    def download_daily(self, trade_date: str, varieties: list[str] = None) -> int:
        """Download IV data for all (or specified) varieties on a given date."""

    def backfill(self, start_date: str, end_date: str) -> int:
        """Full backfill for historical dates."""
```

### 3.2 新增 `hv_calculator.py`

```python
# src/tzdata_pkg/analysis/hv_calculator.py

class HVCalculator:
    """Calculate Historical Volatility from underlying daily prices."""

    def calculate_hv(self, variety: str, window: int = 20) -> float:
        """Calculate HV for given variety and window (20 or 60 days)."""

    def calculate_hv_series(self, variety: str, window: int = 20) -> list[dict]:
        """Calculate HV time series for all available dates."""
```

### 3.3 新增 `iv_benchmark_downloader.py`

```python
# src/tzdata_pkg/analysis/iv_benchmark_downloader.py

class IVBenchmarkDownloader:
    """Compute daily IV benchmark derivatives and store in iv_benchmark table."""

    def compute_daily(self, trade_date: str) -> int:
        """Compute ATM IV, HV, skew, term structure, percentile for all varieties."""

    def compute_backfill(self, start_date: str, end_date: str) -> int:
        """Backfill benchmarks for historical dates."""
```

---

## 四、Celery 定时任务

在 `src/tzdata_pkg/scheduler/celery_app.py` 的 `beat_schedule` 中新增：

```python
# IV benchmark computation
'iv-benchmark-daily': {
    'task': 'tzdata_pkg.scheduler.tasks.iv_tasks.compute_iv_benchmark',
    'schedule': crontab(hour=19, minute=30, day_of_week='mon-fri'),
},

# IV smile snapshot
'iv-smile-snapshot': {
    'task': 'tzdata_pkg.scheduler.tasks.iv_tasks.compute_iv_smile_snapshot',
    'schedule': crontab(hour=19, minute=40, day_of_week='mon-fri'),
},

# IO/HO data sync (Saturday)
'iv-multi-variety-sync': {
    'task': 'tzdata_pkg.scheduler.tasks.iv_tasks.sync_multi_variety_iv',
    'schedule': crontab(hour=10, minute=30, day_of_week='sat'),
},
```

新建 `src/tzdata_pkg/scheduler/tasks/iv_tasks.py`：

```python
from celery import shared_task
from tzdata_pkg.download.tushare.option_iv_downloader import OptionIVDownloader
from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader


@shared_task
def compute_iv_benchmark():
    """Daily IV benchmark computation."""

@shared_task
def compute_iv_smile_snapshot():
    """Daily IV smile snapshot."""

@shared_task
def sync_multi_variety_iv():
    """Saturday IO/HO data sync."""
```

---

## 五、API 端点

在 `src/tzdata_pkg/api/routes/analysis.py` 新增：

| 端点 | 参数 | 返回 |
|------|------|------|
| `GET /api/iv/benchmark` | `variety`, `start`, `end` | 每日衍生指标列表 |
| `GET /api/iv/surface` | `variety`, `date` | IV 曲面矩阵 |
| `GET /api/iv/smile` | `variety`, `date`, `expiry` | 微笑曲线数据 |
| `GET /api/iv/percentile` | `variety`, `date` | 历史分位数 |
| `GET /api/iv/term-structure` | `variety`, `date` | 期限结构 |
| `GET /api/iv/cross-variety` | `start`, `end` | MO/IO/HO 对比数据 |
| `GET /api/iv/iv-hv-spread` | `variety`, `start`, `end` | IV-HV 价差时序 |
| `GET /api/iv/correlation` | `variety`, `window` | IV-标的滚动相关系数 |

---

## 六、测试

`tests/test_iv_data.py`：

```python
def test_iv_snapshot_insert(): ...
def test_iv_data_quality_flag(): ...
def test_iv_benchmark_calculation(): ...
def test_iv_percentile_accuracy(): ...
def test_hv_calculation(): ...
def test_cross_variety_api(): ...
```
