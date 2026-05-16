# 交易日历与合约管理

> 版本：v0.7.0 | 最后更新：2026-05-15

## 交易日历

### 功能概览

交易日历模块提供完整的市场日期管理能力：

- 维护交易所交易日历，支持节假日覆盖
- 非交易日标记和补市日覆盖
- 产品级别的交易日历
- 系统初始化覆盖 1990-2026 年

### 初始化日历

```bash
# 一键初始化 1990-2026 交易日历 + 产品日历
PYTHONPATH=src python -m tzdata_pkg.cli.calendar_system_init
```

```python
# 从 Tushare 导入
from tzdata_pkg.cli.import_trade_calendar import ImportTradeCalendar
ImportTradeCalendar.run(exchange="CFFEX", year_from=2025, year_to=2026)
```

### 日期查询

```python
from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator

# 查询是否交易日
DateCalculator.is_trading_day("CFFEX", "2026-05-14")

# 获取下一个/上一个交易日
DateCalculator.get_next_trading_day("CFFEX", "2026-05-14")
DateCalculator.get_prev_trading_day("CFFEX", "2026-05-14")

# 区间交易日数
DateCalculator.get_trading_days_count("CFFEX", "2026-01-01", "2026-05-14")

# 从某日起加 N 个交易日
DateCalculator.add_trading_days("CFFEX", "2026-05-14", 10)

# 月份首个/最后个交易日
DateCalculator.get_first_trading_day_of_month("CFFEX", "2026-05")
DateCalculator.get_last_trading_day_of_month("CFFEX", "2026-05")

# 对齐到最近的交易日
DateCalculator.snap_to_trading_day("CFFEX", "2026-05-18", direction="next")
```

### 添加节假日

```python
from tzdata_pkg.maintenance.metadata.trade_calendar_manager import TradeCalendarManager

TradeCalendarManager.add_holiday("CFFEX", "2026-01-01", "元旦")
```

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/maintenance/trade-calendar/init` | 初始化日历 |
| GET | `/api/maintenance/trade-calendar/trading-days` | 交易日列表 |
| GET | `/api/maintenance/trade-calendar/is-trading-day` | 是否交易日 |
| GET | `/api/maintenance/trade-calendar/next-trading-day` | 下一个交易日 |
| GET | `/api/maintenance/trade-calendar/prev-trading-day` | 上一个交易日 |
| POST | `/api/maintenance/trade-calendar/add-holiday` | 添加节假日 |
| GET | `/api/maintenance/trade-calendar/count` | 交易日计数 |
| POST | `/api/maintenance/trade-calendar/import-from-tushare` | 从 Tushare 导入 |

## 特殊日期覆盖

特殊日期覆盖优先级高于常规日历，用于处理临时调整（补市/休市）。

```python
from tzdata_pkg.maintenance.metadata.special_dates import SpecialDateManager

# 添加补市日
SpecialDateManager.create(
    exchange_code="CFFEX",
    override_date="2026-01-20",
    override_type="trading",   # trading=补市, non_trading=休市
    reason="临时调整"
)

# 查询覆盖
override = SpecialDateManager.get_by_date("CFFEX", "2026-01-20")
```

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/maintenance/trade-calendar/special-dates` | 添加特殊日期 |
| GET | `/api/maintenance/trade-calendar/special-dates` | 特殊日期列表 |
| DELETE | `/api/maintenance/trade-calendar/special-dates` | 删除特殊日期 |

## 主力合约

### 自动填充（基于持仓量）

```python
from tzdata_pkg.maintenance.metadata.main_contract import MainContractManager

MainContractManager.auto_populate(
    product_code="MO",
    start_date="2026-01-01",
    end_date="2026-05-14"
)
```

### 手动设置

```python
MainContractManager.set_main_contract(
    product_code="MO",
    trade_date="2026-03-15",
    main_contract="MO2506",
    reason="手动设置"
)
```

### 查询主力合约

```python
# 查询主力合约序列
series = MainContractManager.get_series(
    product_code="MO",
    start_date="2026-01-01",
    end_date="2026-05-14"
)

# 查询换月记录
rollovers = MainContractManager.get_rollovers("MO")
```

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/main-contract/{product}` | 获取主力合约 |
| POST | `/api/maintenance/main-contract/{product}` | 设置主力合约 |
| GET | `/api/maintenance/main-contract/{product}/series` | 主力合约序列 |
| GET | `/api/maintenance/main-contract/{product}/rollovers` | 换月记录 |
| POST | `/api/maintenance/main-contract/{product}/auto-populate` | 自动填充 |

## 交易时间模板

### 创建模板

```python
from tzdata_pkg.maintenance.metadata.trading_hours import TradingHoursManager

TradingHoursManager.create_template(
    template_name="CFFEX-股指",
    exchange_code="CFFEX",
    product_type="futures",
    normal_schedule=[("09:30", "11:30"), ("13:00", "15:00")],
    night_schedule=[],                          # 股指无夜盘
    auction_schedule=[("09:25", "09:30")]        # 集合竞价
)
```

### 判断是否交易时间

```python
# API 接口
GET /api/maintenance/trading-hours/is-trading-time?template_id=1&datetime=2026-05-14T10:00:00
```

### 常见模板

| 品种 | 日盘 | 夜盘 | 集合竞价 |
|------|------|------|----------|
| 中金所股指 | 09:30-11:30, 13:00-15:00 | 无 | 09:25-09:30 |
| 上期所黄金 | 09:00-11:30, 13:30-15:00 | 21:00-次日02:30 | 20:55-21:00 |
| 大商所豆粕 | 09:00-11:30, 13:30-15:00 | 21:00-23:00 | 08:55-09:00 |

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/trading-hours/{id}` | 模板详情 |
| POST | `/api/maintenance/trading-hours/templates` | 创建模板 |
| GET | `/api/maintenance/trading-hours/{id}/sessions` | 时段列表 |

## CalendarCache 预热

系统启动时自动预热 `CalendarCache`，将交易日历加载到内存，避免每次查询都访问数据库。

```
POST /api/maintenance/trade-calendar/cache/preload
GET  /api/maintenance/trade-calendar/cache/status
```

## 下一页

- [MO 期权数据同步](09-mo-data-sync.md) — MO 专项同步
- [Celery 任务调度](10-celery-tasks.md) — 定时任务配置
