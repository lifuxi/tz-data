# Celery 任务调度

> 版本：v0.7.0 | 最后更新：2026-05-15

## Celery 配置

```python
# celery_app.py
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,           # 1 小时超时
    task_soft_time_limit=3000,      # 50 分钟软超时
    task_autoretry_for=(Exception,),
    task_retry_backoff=True,
    task_retry_backoff_max=600,     # 最大重试间隔 10 分钟
    task_max_retries=3,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)
```

## 启动 Worker

### Windows（必须使用 gevent）

```bash
celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info --pool=gevent
```

> **注意**：Windows 不支持默认 `prefork` pool，必须使用 `--pool=gevent`。

### 监控面板

```bash
celery -A tzdata_pkg.scheduler.celery_app flower --port=5555
```

访问 `http://localhost:5555` 查看任务状态。

## Beat 完整调度表

### MO 系列（交易日）

| 任务名 | 任务 ID | 时间 | 频率 |
|--------|---------|------|------|
| MO 分钟数据同步 | `mo-minute-sync` | 15:30 | 周一~周五 |
| MO IV 同步 | `mo-iv-sync` | 16:00 | 周一~周五 |
| 标的日线同步 | `mo-underlying-sync` | 16:30 | 周一~周五 |
| MO 持仓同步 | `mo-position-sync` | 17:00 | 周一~周五 |
| HO 持仓同步 | `ho-position-sync` | 17:05 | 周一~周五 |
| IO 持仓同步 | `io-position-sync` | 17:10 | 周一~周五 |
| MO 市场环境 | `mo-market-env` | 17:30 | 周一~周五 |
| MO 质量检查 | `mo-quality-check` | 18:00 | 每日 |
| MO 合约同步 | `mo-contract-sync` | 10:00 | 每周六 |

### 通用数据维护（每日）

| 任务名 | 任务 ID | 时间 | 说明 |
|--------|---------|------|------|
| 增量数据同步 | `daily-incremental-sync` | 18:00 | 同步所有启用目录 |
| 状态刷新 | `daily-status-refresh` | 18:30 | 刷新本地/远程状态 |
| 完整性检查 | `daily-completeness-check` | 19:00 | 数据完整性检查 |
| 缺失账单检测 | `daily-bill-missing-check` | 20:00 | 检测缺失账单 |
| 交易开平匹配 | `daily-trade-matching` | 20:30 | FIFO 开平配对 |
| 账单日历检查 | `daily-bill-calendar-check` | 21:00 | 交易日账单驱动检查 |

### 数据层任务（周一~周五）

| 任务名 | 任务 ID | 时间 | 说明 |
|--------|---------|------|------|
| 指数日线同步 | `sync-index-daily` | 18:30 | 000852/000300 指数 |
| 日频 VWAP 计算 | `compute-daily-vwap` | 18:35 | 计算日频 VWAP |
| 期权 Greeks 预计算 | `compute-option-greeks` | 20:00 | 预计算 Greeks |

## 任务模块列表

| 模块 | 任务 |
|------|------|
| `mo_tasks.py` | `sync_mo_minute`, `sync_mo_iv`, `sync_underlying_daily`, `sync_mo_contracts`, `mo_data_quality_check`, `compute_mo_market_env` |
| `position_tasks.py` | `sync_mo_position`, `sync_ho_position`, `sync_io_position` |
| `market_env_tasks.py` | `compute_mo_market_env` |
| `sync_tasks.py` | `daily_incremental_sync`, `sync_catalog_task` |
| `check_tasks.py` | `refresh_status_task`, `completeness_check_task` |
| `statement_tasks.py` | `parse_statement_task`, `auto_fetch_statements`, `batch_upload_statements`, `check_missing_bills_task`, `trade_matching_task` |
| `bill_tasks.py` | `daily_bill_calendar_check` |
| `data_tasks.py` | `sync_index_daily`, `compute_daily_vwap`, `compute_option_greeks` |
| `alert_tasks.py` | 告警相关任务 |

## Redis 配置

```bash
# 默认配置
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Windows 上推荐：
- **Memurai** — Redis Windows 兼容版
- **WSL Redis** — 通过 WSL 运行 Redis

验证 Redis 运行：
```bash
redis-cli ping  # 应返回 PONG
```

## 查看调度任务

```
GET /api/maintenance/schedule
```

返回所有 Beat 调度任务的列表。

## Windows 注意事项

1. **必须使用 gevent pool**：`--pool=gevent`
2. **时区**：`Asia/Shanghai`
3. **Redis broker**：推荐 Memurai 或 WSL Redis
4. **Celery Beat** 可与 Worker 同一进程运行（`--beat` 参数），或单独启动

## 下一页

- [前端页面指南](11-frontend.md) — Vue3 前端
- [部署与运维](13-deployment.md) — 启动脚本和 FAQ
