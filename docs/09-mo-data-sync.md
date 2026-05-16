# MO 期权数据同步

> 版本：v0.7.0 | 最后更新：2026-05-15

## 概述

MO（中证 1000 股指期权）数据同步系统包含多个独立任务，覆盖日线、分钟线、IV、合约、持仓等维度。

## 同步任务清单

| 任务 | 时间 | 频率 | 说明 |
|------|------|------|------|
| `mo-minute-sync` | 15:30 | 交易日 | MO 期权 1 分钟数据同步 |
| `mo-iv-sync` | 16:00 | 交易日 | MO IV 数据同步（Tushare opt_daily） |
| `mo-underlying-sync` | 16:30 | 交易日 | 标的日线数据同步 |
| `mo-position-sync` | 17:00 | 交易日 | MO Top20 持仓同步 |
| `ho-position-sync` | 17:05 | 交易日 | HO Top20 持仓同步 |
| `io-position-sync` | 17:10 | 交易日 | IO Top20 持仓同步 |
| `mo-market-env` | 17:30 | 交易日 | MO 市场环境分析 |
| `mo-quality-check` | 18:00 | 每日 | MO 数据质量检查 |
| `mo-contract-sync` | 10:00 | 每周六 | MO 合约主表同步 |

## MO 分钟数据

### 下载器

```python
from tzdata_pkg.download.tushare.mo_minute_downloader import MOMinuteDownloader

downloader = MOMinuteDownloader(freq="1min")

# 全量下载
results = downloader.download_all_contracts(
    start_date=date(2025, 1, 1),
    end_date=date(2026, 5, 15),
    active_only=True
)

# 增量同步
results = downloader.download_incremental()
```

### 存储

数据写入 `tzdata_trading.db.mo_minute_quotes` 表：

| 字段 | 说明 |
|------|------|
| trade_time | 交易时间（'2025-01-15 09:30:00'） |
| trade_date | 交易日期（'20250115'） |
| contract_code | 合约代码（'MO2501-C-7000'） |
| underlying | 标的（'MO'） |
| option_type | 期权类型（call/put） |
| strike | 行权价 |
| open/high/low/close | 价格 |
| volume/turnover/open_interest | 成交数据 |
| frequency | 频率（1min/5min/...） |

### 频率支持

支持 `1min`, `5min`, `15min`, `30min`, `60min`，当前优先使用 `1min`。

### CLI

```bash
# 全量同步
python -m tzdata_pkg.cli.sync_mo_minute full --freq 1min --start 2025-01-01 --end 2026-05-15

# 增量同步
python -m tzdata_pkg.cli.sync_mo_minute incremental --freq 1min

# 列出合约
python -m tzdata_pkg.cli.sync_mo_minute contracts
```

## MO IV 数据

- **数据源**：Tushare `opt_daily` API
- **支持品种**：MO / HO / IO
- **存储**：`tzdata_trading.db.option_sim_iv_series`
- **包含**：IV、Delta、Gamma、Vega、Theta 等 Greeks

## 标的日线

- **数据源**：AkShare（000852 指数、IM 期货、A00 A50）+ Sina 直连（512100 ETF）
- **存储**：`tzdata_trading.db.option_sim_underlying_daily`
- **同步标的**：000852、IM、512100、A00、510050、510300

## 持仓同步

MO/HO/IO Top20 持仓排名从 CFFEX 网站爬取，写入 `position_detail` 表。

## 数据质量检查

```python
from tzdata_pkg.maintenance.monitoring.mo_data_quality import check_data_quality_summary
import json
print(json.dumps(check_data_quality_summary(), indent=2, ensure_ascii=False))
```

检查项：
- IV 数据新鲜度（滞后天数）
- 标的日线数据新鲜度
- 跨表一致性（IV/指数/标的日期对齐）

## 数据存储总览

| 表名 | 数据内容 |
|------|----------|
| `mo_minute_quotes` | MO 分钟 K 线 |
| `option_sim_iv_series` | 期权 IV 序列（含 Greeks） |
| `option_sim_underlying_daily` | 标的日线行情 |
| `mo_contract_master` | MO 合约主表 |
| `position_detail` | 持仓排名 |

## Celery Beat 时间线

```
15:30 ── MO 分钟数据同步
16:00 ── MO IV 同步
16:30 ── 标的日线同步
17:00 ── MO 持仓同步
17:05 ── HO 持仓同步
17:10 ── IO 持仓同步
17:30 ── MO 市场环境分析
18:00 ── MO 数据质量检查
```

## 下一步

- [Celery 任务调度](10-celery-tasks.md) — 完整调度配置
- [数据维护与同步](06-data-maintenance.md) — 通用同步机制
