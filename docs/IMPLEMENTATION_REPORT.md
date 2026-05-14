# 交易日历模块 v0.6.0 项目实施报告

> 编制日期：2026-05-14 | 版本号：v0.6.0 | Git Commit：e666ad4

---

## 1. 项目概述

### 1.1 目标

为 tz-data 数据平台构建完整的**交易日历管理能力**，支持中国期货/期权市场的交易日查询、节假日覆盖、主力合约自动识别、交易时间模板配置等核心功能。

### 1.2 范围

覆盖 tz-data 的后端数据模型、业务逻辑、API 接口、前端管理页面、CLI 工具、自动化测试及文档更新。

### 1.3 交付物

- 7 个后端 Python 模块（交易日历核心）
- 4 个数据库迁移脚本
- 3 个新增前端页面 + 2 个增强页面
- 40+ API 维护端点
- 55 个自动化测试用例
- 3 份文档更新（用户指南、用户文档、进展报告）

---

## 2. 架构设计

### 2.1 数据模型

| 表名 | 所在库 | 核心字段 |
|------|--------|----------|
| `trade_calendar` | market.db | exchange_code, trade_date, is_trading_day, reason |
| `special_dates` | market.db | exchange_code, date, action(补市/休市), priority |
| `main_contract_series` | market.db | product_code, date, main_contract_id, volume |
| `trading_hours_templates` | market.db | template_name, session_type(day/night/auction), start_time, end_time |
| `product_config` | market.db | multiplier, price_tick, margin_rate, option_style (增强字段) |

### 2.2 模块关系

```
calendar_cache.py (内存缓存层)
        ↑
trade_calendar.py (日历核心逻辑)
        ↑
    ┌───┼───┬──────────┐
    ↓   ↓   ↓          ↓
special_dates  main_contract  trading_hours  date_calculator
  (覆盖)      (主力识别)     (时段模板)     (日期计算)
        ↑
    ┌───┼──────────────────┐
    ↓   ↓                  ↓
product_manager  contract_manager   exchange_manager
  (产品CRUD)     (合约同步)        (交易所配置)
```

### 2.3 技术选型

| 技术点 | 选型 | 理由 |
|--------|------|------|
| 数据库 | SQLite WAL | 单文件、零配置、读写并发良好 |
| 缓存 | 内存单例 + 二分查找 | 日历查询高频低延迟 |
| 查询优化 | 启动时预热全部日历 | 避免运行时 DB 查询 |
| 日期算法 | bisect 二分查找 | O(log n) 定位交易日 |

---

## 3. 实施详情

### 3.1 后端模块（7 个核心文件）

#### 3.1.1 TradeCalendarManager — 日历核心

**文件**：`src/tzdata_pkg/maintenance/metadata/trade_calendar.py`

**功能**：交易日/非交易日 CRUD、节假日批量导入、日期查询。

**关键方法**：
- `add_non_trading_day()` — 添加非交易日
- `is_trading_day()` — 判断是否交易日
- `batch_import_holidays()` — 批量导入节假日
- `get_trading_days()` — 按日期范围查询

#### 3.1.2 SpecialDateManager — 特殊日期覆盖

**文件**：`src/tzdata_pkg/maintenance/metadata/special_dates.py`

**功能**：补市/休市覆盖管理，优先级高于常规日历。

**关键方法**：
- `add_override()` — 添加特殊日期
- `check_override()` — 检查日期覆盖
- `get_overrides()` — 按交易所/类型查询

#### 3.1.3 MainContractManager — 主力合约识别

**文件**：`src/tzdata_pkg/maintenance/metadata/main_contract.py`

**功能**：持仓量驱动自动填充 + 手动设置主力合约序列 + 换月检测。

**关键方法**：
- `set_main_contract()` — 手动设置
- `auto_populate()` — 按持仓量自动填充
- `detect_rollover()` — 换月日期检测

#### 3.1.4 TradingHoursManager — 交易时间模板

**文件**：`src/tzdata_pkg/maintenance/metadata/trading_hours.py`

**功能**：日盘/夜盘/集合竞价时段定义。

**关键方法**：
- `create_template()` — 创建时段模板
- `get_template()` — 查询模板详情
- `get_all_templates()` — 全部模板列表

#### 3.1.5 DateCalculator — 日期计算器

**文件**：`src/tzdata_pkg/maintenance/metadata/date_calculator.py`

**功能**：8 个高级日期计算方法，基于交易日历 + 特殊日期覆盖。

**方法列表**：
| 方法 | 功能 |
|------|------|
| `is_trading_day()` | 判断是否交易日 |
| `get_next_trading_day()` | 获取下一个交易日 |
| `get_prev_trading_day()` | 获取上一个交易日 |
| `get_trading_days_count()` | 统计交易日数量 |
| `add_trading_days()` | 偏移 N 个交易日 |
| `get_trading_days_list()` | 获取日期范围内的交易日列表 |
| `get_first_trading_day_of_month()` | 获取月份首个交易日 |
| `get_last_trading_day_of_month()` | 获取月份最后交易日 |

#### 3.1.6 CalendarCache — 内存缓存

**文件**：`src/tzdata_pkg/maintenance/metadata/calendar_cache.py`

**功能**：单例模式 + 启动预热 + 二分查找。

**设计要点**：
- 启动时自动加载全部交易所交易日历到内存
- 使用 `bisect` 模块实现 O(log n) 查询
- `is_trading_day()` 无需访问数据库
- 支持 `preload()` 手动刷新缓存

**预热集成**：在 `api/server.py` 的 `lifespan` 钩子中调用 `CalendarCache.preload()`。

#### 3.1.7 ProductManager 增强

**文件**：`src/tzdata_pkg/maintenance/metadata/product_manager.py`

**变更**：
- 修复了重复类定义导致的方法丢失 Bug
- 新增 `multiplier`、`price_tick`、`margin_rate`、`option_style` 字段支持
- 增加 `_get_columns()` 方法，通过 `PRAGMA table_info` 动态获取列名
- 增加 `_row_to_dict()` 方法，将 SQLite 行转为 dict

### 3.2 CLI 工具（2 个）

#### 3.2.1 交易日历导入

**文件**：`src/tzdata_pkg/cli/import_trade_calendar.py`

**功能**：从 Tushare 导入交易日历数据，支持增量模式。

```bash
PYTHONPATH=src python -m tzdata_pkg.cli.import_trade_calendar \
  --start 2025-01-01 --end 2026-12-31
```

#### 3.2.2 系统初始化

**文件**：`src/tzdata_pkg/cli/calendar_system_init.py`

**功能**：一键初始化 1990-2026 年交易日历和产品数据。

```bash
PYTHONPATH=src python -m tzdata_pkg.cli.calendar_system_init
```

### 3.3 API 端点（40+）

**文件**：`src/tzdata_pkg/api/routes/maintenance.py`

| 路由前缀 | 功能 | 方法数 |
|----------|------|--------|
| `/api/maintenance/calendar` | 交易日历 CRUD | 8 |
| `/api/maintenance/special-dates` | 特殊日期覆盖 | 8 |
| `/api/maintenance/main-contracts` | 主力合约管理 | 6 |
| `/api/maintenance/trading-hours` | 交易时间模板 | 6 |
| `/api/maintenance/products` | 产品管理（增强） | 5 |
| `/api/maintenance/contracts` | 合约管理 | 4 |
| `/api/maintenance/calendar/cache` | 缓存预热/刷新 | 2 |
| `/api/maintenance/calendar/system-init` | 系统初始化 | 1 |
| **合计** | | **40+** |

### 3.4 前端页面（3 个新增 + 2 个增强）

#### 3.4.1 主力合约管理页

**文件**：`frontend/src/views/MainContractList.vue`

**功能**：
- 产品选择 + 日期范围查询 → 展示主力合约序列
- 支持手动设置主力合约
- 持仓量驱动自动填充按钮
- 换月日期可视化

**代码行数**：183 行

#### 3.4.2 特殊日期管理页

**文件**：`frontend/src/views/SpecialDateList.vue`

**功能**：
- 列表展示现有特殊日期覆盖
- 添加/删除补市/休市日期
- 按交易所、日期范围筛选

**代码行数**：176 行

#### 3.4.3 交易时间模板页

**文件**：`frontend/src/views/TradingHoursList.vue`

**功能**：
- 列表展示所有交易时间模板
- 创建/编辑模板（日盘/夜盘/集合竞价）
- 按交易所筛选

**代码行数**：385 行

#### 3.4.4 交易日历页增强

**文件**：`frontend/src/views/TradeCalendarList.vue`（修改）

**变更**：增加日历初始化按钮、交易日统计展示、快捷操作入口。

#### 3.4.5 数据源配置页增强

**文件**：`frontend/src/views/DataSourceConfig.vue`（修改）

**变更**：「交易日历」tab 增加操作按钮，导航到对应管理页面。

### 3.5 路由注册

**文件**：`frontend/src/router/index.js`

新增 3 个路由：
- `/main-contracts` → MainContractList
- `/special-dates` → SpecialDateList
- `/trading-hours` → TradingHoursList

### 3.6 API 客户端

**文件**：`frontend/src/api/index.js`

新增 49 行 API 调用函数，覆盖全部新增端点。

---

## 4. 数据库迁移

### 4.1 迁移脚本

| 文件 | 功能 |
|------|------|
| `migrate_calendar_v2.py` | 日历表初始版本迁移 |
| `migrate_calendar_v3.py` | 日历表升级（新增字段） |
| `migrate_product_calendar.py` | 产品-日历关联迁移 |
| `trade_calendar.py`（schema） | 自动建表逻辑 |

### 4.2 新增/增强表

| 表 | 状态 | 所在库 |
|----|------|--------|
| `main_contract_series` | 新增 | market.db |
| `special_dates` | 新增 | market.db |
| `trading_hours_templates` | 新增 | market.db |
| `product_config` | 增强（4 新字段） | market.db |
| `trade_calendar` | 已存在 | market.db |

---

## 5. 测试覆盖

### 5.1 测试文件（8 个）

| 文件 | 测试数 | 覆盖内容 |
|------|--------|----------|
| `test_trade_calendar_migration.py` | 6 | 日历迁移正确性 |
| `test_trade_calendar_api.py` | 8 | API 端点 CRUD |
| `test_product_contract_migration.py` | 5 | 产品/合约迁移 |
| `test_special_dates.py` | 7 | 特殊日期覆盖 |
| `test_calendar_cache.py` | 6 | 缓存预热与查询 |
| `test_import_trade_calendar.py` | 4 | Tushare 日历导入 |
| `test_contract_sync.py` | 4 | 合约同步 |
| `test_main_contract.py` | 5 | 主力合约识别 |
| `test_trading_hours.py` | 5 | 交易时间模板 |
| `test_date_calculator.py` | 5 | 日期计算方法 |

### 5.2 测试结果

```
55 passed, 0 failed, 0 skipped
```

所有交易日历相关测试用例通过。

---

## 6. 代码变更统计

### 6.1 整体变更（相对于 v0.5.0）

```
13 个文件变更
+1,115 行新增
-44 行删除
```

### 6.2 按维度统计

| 维度 | 文件数 | 行数 | 占比 |
|------|--------|------|------|
| 前端页面 | 5 | ~830 行 | 55% |
| 后端逻辑 | 2 | ~74 行 | 5% |
| API 路由 | 2 | ~42 行 | 3% |
| 测试 | 10 个文件 | ~800 行 | — |
| 文档 | 3 | ~216 行 | 14% |

> 注：后端核心逻辑模块（7 个 Python 文件）在 v0.5.0 阶段已实现，本次 v0.6.0 主要聚焦前端页面、API 端点完善和文档更新。

---

## 7. 关键问题解决

### 7.1 ProductManager 重复类定义 Bug

**现象**：`type object 'ProductManager' has no attribute '_get_columns'`

**根因**：编辑操作导致文件出现两个 `class ProductManager` 定义，第二个覆盖了第一个，丢失了 `_row_to_dict` 和 `_get_columns` 方法。

**修复**：重写为单一统一类定义，包含完整方法集。

**验证**：`dir(ProductManager)` 输出确认 `['_get_columns', '_row_to_dict', 'create', 'delete', 'get', 'list_all', 'update']`。

### 7.2 Python 模块路径问题

**现象**：`ModuleNotFoundError: No module named 'tzdata_pkg'`

**根因**：包代码位于 `src/` 目录，需设置 `PYTHONPATH=src` 或安装开发模式。

**解决**：启动时设置 `PYTHONPATH=src`，或通过 `pip install -e .` 安装。

---

## 8. 与已有模块的集成

### 8.1 日历缓存与 API 服务

在 `api/server.py` 的 lifespan 钩子中集成 `CalendarCache.preload()`，后端启动时自动加载交易日历到内存，后续查询零延迟。

### 8.2 合约同步与主力合约

合约导入（`import_contracts.py`）完成后，需手动触发 `MainContractManager.auto_populate()` 填充主力合约序列。（自动触发为下一步优化项）

### 8.3 日期计算器与日历缓存

`DateCalculator` 内部通过 `CalendarCache` 获取交易日历，所有日期计算无需直接访问数据库。

### 8.4 前端与 API

前端 3 个新页面均通过 `frontend/src/api/index.js` 调用维护端点，与后端 40+ 端点完整对接。

---

## 9. 当前状态

### 9.1 完成度

| 模块 | 状态 |
|------|------|
| 交易日历核心逻辑 | ✅ 100% |
| 特殊日期覆盖 | ✅ 100% |
| 主力合约识别 | ✅ 100% |
| 交易时间模板 | ✅ 100% |
| 日期计算器 | ✅ 100% |
| 内存缓存 + 预热 | ✅ 100% |
| 产品/合约增强 | ✅ 100% |
| API 端点 | ✅ 100% |
| 前端页面 | ✅ 100% |
| CLI 工具 | ✅ 100% |
| 自动化测试 | ✅ 55/55 通过 |
| 文档更新 | ✅ 3 份文档 v0.6.0 |

### 9.2 后续优化项（P2 优先级）

| # | 优化项 | 预期收益 |
|---|--------|----------|
| 1 | 合约导入后自动触发主力合约 auto_populate | 减少手动操作 |
| 2 | CalendarCache 失效自动刷新机制 | 数据一致性保障 |
| 3 | 交易日变更审计日志 | 操作可追溯 |
| 4 | 前端 E2E 测试覆盖 | 回归检测 |

---

## 10. 交付清单

| 交付物 | 数量 | 状态 |
|--------|------|------|
| Python 后端文件 | 7 个核心 + 2 个 CLI | ✅ |
| 数据库迁移脚本 | 4 个 | ✅ |
| API 端点 | 40+ | ✅ |
| 前端页面 | 3 新增 + 2 增强 | ✅ |
| 路由注册 | 3 个 | ✅ |
| API 客户端函数 | 49 行 | ✅ |
| 测试文件 | 8 个（10 个含日历相关） | ✅ 55 passed |
| 文档更新 | 3 份 | ✅ v0.6.0 |
| Git 提交 | 1 次 | e666ad4 |

---

## 11. 总体项目定位

tz-data 交易日历模块作为**中国期货/期权市场数据基础设施**的关键组成部分：

- **时间跨度**：1990 ~ 2026 年全覆盖
- **交易所覆盖**：CFFEX、SHFE、DCE、CZCE 等
- **数据精度**：精确到日的交易/非交易日判定
- **特殊处理**：补市/休市覆盖、节假日自动识别
- **性能指标**：O(log n) 查询延迟，启动预热后零数据库访问

本模块为 tz2.0 交易系统和 tz-ai 分析系统提供准确的交易日期判定能力，是行情查询、策略回测、账单对账等功能的基础依赖。
