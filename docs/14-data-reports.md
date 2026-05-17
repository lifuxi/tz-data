# 数据报告全量清单

> 版本：v0.7.0 | 最后更新：2026-05-17

本文档列出 tz-data 工程中所有数据相关报告的完整清单，涵盖数据质量、一致性校验、账单交易、系统运维四大类。

## 一、数据质量类（6 份）

### 1. 健康快照（HealthSnapshotGenerator）

**代码位置**：`src/tzdata_pkg/maintenance/monitoring/health_snapshot.py`

**触发方式**：
- API：`POST /api/maintenance/health-snapshot/generate`
- Celery Beat：每日调度
- 内部：`HealthSnapshotGenerator.generate_all_snapshots()`

**产出数据**：
| 字段 | 说明 |
|------|------|
| 完整性百分比 | 该目录数据覆盖率（预期 vs 实际） |
| 质量评分 | 综合评分（见下方质量评估） |
| 一致性状态 | 跨源/跨表一致性 |
| 上次同步状态 | 最新同步时间、记录数、状态 |
| 缺失天数 | 缺失的交易日列表 |
| 告警列表 | 相关异常告警 |

**查询端点**：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/health-snapshot/latest/{catalog_id}` | 最新快照 |
| GET | `/api/maintenance/health-snapshot/list` | 分页历史列表 |

---

### 2. 质量评估（QualityEvaluator）

**代码位置**：`src/tzdata_pkg/maintenance/monitoring/quality_evaluator.py`

**触发方式**：API / Beat / 被 HealthSnapshotGenerator 调用

**评分维度**：
| 维度 | 权重 | 检查内容 |
|------|------|---------|
| 完整性 | 50% | 数据覆盖度（预期交易日 vs 实际记录） |
| 准确性 | 30% | 零价格、极端日涨跌幅(>9%)、零成交量有收盘价、close/settle偏离(>2%)、负成交量 |
| 一致性 | 20% | 跨源/跨表数据一致性 |

**质量等级**：
| 等级 | 分数范围 |
|------|---------|
| excellent | 90-100 |
| good | 75-89 |
| fair | 50-74 |
| poor | 25-49 |
| critical | 0-24 |

**API 端点**：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/quality/overview` | 全部目录概览 |
| GET | `/api/maintenance/quality/{catalog_id}` | 单目录详情 |

---

### 3. 完整性检查（CompletenessChecker）

**代码位置**：`src/tzdata_pkg/maintenance/monitoring/completeness_checker.py`

**触发方式**：Celery Beat `daily-completeness-check`（每日 19:00）

**产出数据**：
| 字段 | 说明 |
|------|------|
| expected_days | 应采集的交易日数 |
| actual_days | 实际有数据的交易日数 |
| missing_dates | 缺失的日期列表 |
| completeness_pct | 完整性百分比 |
| status | complete / incomplete |

---

### 4. 分钟数据完整性（MinuteCompletenessChecker）

**代码位置**：`src/tzdata_pkg/maintenance/monitoring/minute_completeness.py`

**触发方式**：被 CompletenessChecker 内部调用

**产出数据**：
| 字段 | 说明 |
|------|------|
| expected_sessions | 预期交易时段数（日盘 + 夜盘） |
| actual_records | 实际记录数 |
| missing_minutes | 缺失的时间段列表 |
| status | complete / incomplete / no_data |

---

### 5. 异常检测（AnomalyDetector）

**代码位置**：`src/tzdata_pkg/maintenance/monitoring/anomaly_detector.py`

**触发方式**：Celery Beat `daily-anomaly-detection`（每日 21:30），检测到异常时 DingTalk 告警

**检测规则**：
| 规则 | 条件 | 返回类型 |
|------|------|---------|
| 价格突跃 | 相邻交易日 close 涨跌幅 > 20% | `price_spike` |
| 成交量异常 | 当日 volume > 30 日均值 × 3 | `volume_anomaly` |
| 零价格 | close = 0 但 volume > 0 | `zero_price` |
| 持仓突变 | top20 持仓总量日环比变化 > 50% | `position_spike` |
| IV 异常 | 同一合约 IV 日环比变化 > 0.3 | `iv_anomaly` |

---

### 6. MO 期权专项质量

**代码位置**：`src/tzdata_pkg/maintenance/monitoring/mo_data_quality.py`

**触发方式**：Celery Beat `mo-quality-check`（每日 18:00）

**检查项目**：
| 项目 | 内容 |
|------|------|
| 数据新鲜度 | 基于交易日历的滞后天数 |
| IV 完整性 | 合约数量、IV 非空率 |
| 跨表一致性 | MO IV 数据与指数数据对齐 |
| 综合质量摘要 | 汇总以上三项结论 |

---

## 二、数据一致性类（3 份）

### 7. 跨源差异报告（DiffEngine）

**代码位置**：`src/tzdata_pkg/maintenance/monitoring/diff_engine.py`

**触发方式**：API / Celery Beat `generate_diff_report()`

**产出数据**：
| 字段 | 说明 |
|------|------|
| 字段值对比 | 两数据源逐字段对比 |
| 偏差百分比 | 差值 / 基准值的比例 |
| 告警统计 | 总告警数、受影响目录数、受影响天数 |

---

### 8. 跨库一致性检查（CrossDBChecker）

**代码位置**：`src/tzdata_pkg/verify/cross_db_check.py`

**触发方式**：Celery Beat `daily-cross-db-consistency`（每日 19:05），5 项全部 FAIL 时告警

**检查项目**：
| # | 检查项 | 对比对象 |
|---|--------|---------|
| 1 | trades 表行数 | tzdata_trading.db vs bills.db |
| 2 | trades 聚合金额 | total_pnl / commission / turnover |
| 3 | matched_trades | 行数 + 净盈亏 |
| 4 | account_summary | 逐行对比 |
| 5 | positions_summary | 行数对比 |

---

### 9. 数据量对账

**代码位置**：`src/tzdata_pkg/scheduler/tasks/check_tasks.py` → `reconcile_catalog_records()`

**触发方式**：Celery Beat `daily-reconcile-records`（每日 18:45）

**逻辑**：对比 `data_status_local.total_records` vs 实际 `COUNT(*)`，偏差超过阈值时自动修正并告警。

---

## 三、账单与交易类（4 份）

### 10. 账单复核（BillReconciler）

**代码位置**：`src/tzdata_pkg/verify/bill_reconcile.py`

**触发方式**：API `POST /api/verify/run` → `_run_verification()`

**验证内容**：
- 重新解析原始账单文件，验证关键字段（balance_bf、balance_cf、client_equity）
- 资金平衡方程：`期末权益 = 期初 + 出入金 + 盈亏 - 手续费 +/- 权利金`

---

### 11. 资金平衡校验（BillBalanceVerifier）

**代码位置**：`src/tzdata_pkg/maintenance/statements/bill_balance_verifier.py`

**触发方式**：API `POST /api/maintenance/verify-balance`

**校验方程**：
```
期末权益 = 期初权益 + 入金 - 出金 + 平仓盈亏 + 持仓盈亏 - 手续费 - 交割盈亏 +/- 其他
```

**输出状态**：
| 状态 | 含义 |
|------|------|
| balanced | 方程平衡 |
| suspicious | 偏差在可接受范围 |
| unbalanced | 偏差超阈值 |

---

### 12. 滑点分析报告（BillMarketReconciler）

**代码位置**：`src/tzdata_pkg/maintenance/statements/bill_reconciler.py`

**触发方式**：API `POST /api/maintenance/reconcile`、`POST /api/maintenance/reconcile-from-db`

**产出数据**：
| 字段 | 说明 |
|------|------|
| 逐笔滑点 | 执行价 vs VWAP / settle / close |
| 滑点百分比 | 滑点 / 基准价的百分比 |
| 区间内检查 | 执行价是否在日内高低区间内 |
| 聚合统计 | 总交易数、告警数、平均滑点、最大滑点 |

---

### 13. FIFO 交易配对（TradeMatcher）

**代码位置**：`src/tzdata_pkg/maintenance/statements/trade_matcher.py`

**触发方式**：
- Celery Beat `daily-trade-matching`（每日 20:30）
- CLI：`python -m tzdata_pkg.cli.trade_match match`
- CLI 统计：`python -m tzdata_pkg.cli.trade_match stats`
- CLI 验证：`python -m tzdata_pkg.cli.trade_match verify`

**产出数据**：
| 表 | 内容 |
|----|------|
| `matched_trades` | 开仓/平仓 FIFO 配对记录 |
| `trade_performance` | 逐笔绩效（含合约乘数计算） |

**合约乘数**：
| 品种 | 乘数 | 品种 | 乘数 |
|------|------|------|------|
| IF/IH | 300 | IC/IM | 200 |
| MO | 100 | HO | 10000 |
| AG | 15 | AU | 1000 |
| RB | 10 | M/Y/A | 10 |

**盈亏计算**：

期货：
```
price_pnl = close_price - open_price  （多头）
price_pnl = open_price - close_price  （空头）
money_pnl = price_pnl × volume × multiplier
net_pnl = money_pnl - commission
```

期权：
```
premium_pnl = close_premium - open_premium  （多头）
premium_pnl = open_premium - close_premium  （空头）
money_pnl = premium_pnl × volume
net_pnl = money_pnl - commission
```

---

## 四、系统运维类（3 份）

### 14. 系统验证报告

**代码位置**：`src/tzdata_pkg/verify/bill_reconcile.py` + `cross_db_check.py` + `analysis_verify.py`

**触发方式**：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/verify/report` | 获取验证报告 |
| POST | `/api/verify/run` | 触发完整验证 |

**综合评级**：
| 等级 | 条件 |
|------|------|
| TRUSTWORTHY | 所有检查通过 |
| QUESTIONABLE | 部分警告 |
| UNRELIABLE | 多项失败 |
| NO_DATA | 无数据可验证 |

---

### 15. 同步审计报告

**代码位置**：`src/tzdata_pkg/maintenance/sync/sync_engine.py` + `scheduler/tasks/sync_tasks.py`

**触发方式**：
- API：`GET /api/maintenance/sync/status`
- Celery Beat `daily-incremental-sync`（每日 18:00）
- CLI：`python -m tzdata_pkg.cli.sync_catalogs sync`

**产出数据**：
| 字段 | 说明 |
|------|------|
| task_id | Celery 任务 ID |
| status | success / failed / timeout |
| catalog_id | 数据目录 ID |
| mode | incremental / full |
| records_fetched | 本次拉取记录数 |
| started_at / completed_at | 时间范围 |
| audit_log | 审计日志条目 |

**同步失败查询**：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/sync-failures` | 同步失败记录列表 |

---

### 16. CFMMC 爬虫健康检查

**代码位置**：`src/tzdata_pkg/maintenance/statements/cfmmc_scraper.py`

**触发方式**：Celery Beat `cfmmc-health-check`（每周六 09:00）

**检查内容**：
1. HTTP 可达性（访问登录页，检查 200）
2. 登录表单选择器检测
3. 选择器不匹配时 → DingTalk 告警 `STRUCTURE_CHANGED`

---

## 五、触发方式汇总

### 触发方式概览

| 方式 | 数量 | 说明 |
|------|------|------|
| **Celery Beat 定时** | 23 个任务 | 自动调度，时间见调度表 |
| **REST API** | 50+ 端点 | 按需 HTTP 请求 |
| **CLI 手动** | 4 个命令组 | sync / trade-match / verify |
| **内部调用** | 模块间 | QualityEvaluator → CompletenessChecker 等 |

### Celery Beat 任务与报告的映射

| 时间 | 任务 | 产出报告 |
|------|------|---------|
| 18:00 | `daily-incremental-sync` | 同步审计 |
| 18:00 | `mo-quality-check` | MO 专项质量 |
| 18:30 | `sync-index-daily` | 指数日线同步 |
| 18:45 | `daily-reconcile-records` | 数据量对账 |
| 19:00 | `daily-completeness-check` | 完整性检查 |
| 19:05 | `daily-cross-db-consistency` | 跨库一致性 |
| 20:00 | `daily-bill-missing-check` | 缺失账单 |
| 20:30 | `daily-trade-matching` | FIFO 交易配对 |
| 21:00 | `daily-bill-calendar-check` | 账单完整性 |
| 21:30 | `daily-anomaly-detection` | 异常检测 |
| 09:00 周六 | `cfmmc-health-check` | CFMMC 爬虫健康 |

### 前端展示

| 前端页面 | 文件 | 展示内容 |
|---------|------|---------|
| 数据维护看板 | `DataDashboard.vue` | 5 Tab：数据库概览、数据目录、定时任务执行、数据消费映射、质量概览 |
| Dashboard | `Dashboard.vue` | 同步趋势、告警列表、目录状态 |
| 健康快照 | `HealthSnapshotList.vue` | 快照历史 + 详情弹窗 |
| 告警列表 | `AlertList.vue` | 告警历史按级别/类别过滤 |

## 六、数据库覆盖范围

| 数据库 | 文件 | 涉及的报告 |
|--------|------|-----------|
| **market** | `tzdata_market.db` | 健康快照、质量评估、完整性检查、异常检测、跨源差异、同步审计 |
| **trading** | `tzdata_trading.db` | 账单复核、资金平衡、交易配对、滑点分析、跨库一致性 |
| **analysis** | `tzdata_analysis.db` | 系统验证、健康快照、跨库一致性 |
| **bills** | `bills.db` | 账单复核、跨库一致性（trades 对比） |

## 相关文档

- [数据维护与同步](06-data-maintenance.md) — 同步引擎、质量评估、健康快照
- [账单与交易管理](07-bill-management.md) — CFMMC 下载、账单解析、开平匹配
- [Celery 任务调度](10-celery-tasks.md) — Beat 完整调度表
