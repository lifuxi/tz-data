# tz-data 数据层需求文档

> **版本**: 1.0
> **日期**: 2026-05-14
> **来源**: 账单分析体系三份需求文档整合
> **实施方**: tz-data 工程

---

## 一、目标

为账单分析体系提供高质量数据基础，确保：
1. 账单解析覆盖所有分析所需字段
2. 市场数据（基准指数、VWAP、希腊字母）可按日获取
3. 数据表结构支持多维度分析查询

---

## 二、数据表扩展

### 2.1 `bill_fund_flows` — 标准化资金流水表

**目的**: 将账单中的资金变动项从 JSON 中解耦为独立行，支持高效查询和恒等式校验。

```sql
CREATE TABLE bill_fund_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(id),
    trade_date DATE NOT NULL,
    flow_type TEXT NOT NULL,       -- 出入金/平仓盈亏/持仓盈亏/手续费/权利金/交割/利息/其他
    amount DECIMAL(20,4) NOT NULL, -- 正为收入，负为支出
    symbol TEXT,                   -- 关联合约（可空，出入金类为空）
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_bill_date (bill_id, trade_date),
    INDEX idx_flow_type (flow_type, trade_date)
);
```

**flow_type 枚举**:

| 值 | 说明 | 方向 | 恒等式科目 |
|----|------|------|-----------|
| `deposit` | 入金 | + | 入金 |
| `withdrawal` | 出金 | - | 出金 |
| `realized_pnl` | 平仓盈亏 | +/- | 平仓盈亏 |
| `unrealized_pnl` | 持仓盈亏（盯市） | +/- | 持仓盈亏 |
| `commission` | 手续费 | - | 手续费 |
| `premium_income` | 权利金收入 | + | 权利金收入 |
| `premium_expense` | 权利金支出 | - | 权利金支出 |
| `exercise_pnl` | 行权/交割盈亏 | +/- | 行权交割盈亏 |
| `interest_income` | 利息收入 | + | 其他 |
| `interest_expense` | 利息支出 | - | 其他 |
| `other` | 其他调整 | +/- | 其他费用 |

### 2.2 `trades` 表扩展字段

**目的**: 支持滑点、VWAP、执行质量、策略归因分析。

```sql
ALTER TABLE trades ADD COLUMN trade_time TEXT;       -- HH:MM:SS，成交时间
ALTER TABLE trades ADD COLUMN order_type TEXT;        -- 市价/限价/对手价
ALTER TABLE trades ADD COLUMN strategy_tag TEXT;      -- 策略标签（用户标记或自动推断）
ALTER TABLE trades ADD COLUMN vwap DECIMAL(20,4);     -- 当日合约VWAP（日结后回填）
ALTER TABLE trades ADD COLUMN slippage DECIMAL(20,4); -- 滑点 = 成交价 - 参考价
```

### 2.3 `option_greeks_daily` — 期权希腊字母预计算表

**目的**: 避免 tz2.0 每次查询都重新计算 BS 模型，提升持仓分析性能。

```sql
CREATE TABLE option_greeks_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    option_type TEXT,             -- CE/PE
    strike_price DECIMAL(20,4),
    expiry_date DATE,
    underlying_price DECIMAL(20,4),  -- 标的收盘价
    iv DECIMAL(10,4),                -- 隐含波动率
    delta DECIMAL(20,4),
    gamma DECIMAL(20,4),
    vega DECIMAL(20,4),
    theta DECIMAL(20,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trade_date, symbol)
);
```

### 2.4 `daily_index_prices` — 标的指数日线表

**目的**: 提供基准对比（中证1000）和市场环境分析的数据源。

```sql
CREATE TABLE daily_index_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_code TEXT NOT NULL,     -- 000852 = 中证1000, 000300 = 沪深300
    trade_date DATE NOT NULL,
    open DECIMAL(20,4),
    high DECIMAL(20,4),
    low DECIMAL(20,4),
    close DECIMAL(20,4),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(index_code, trade_date)
);
```

### 2.5 `contract_expiry` — 合约到期信息表

**目的**: 支持持仓期限结构分析。

```sql
CREATE TABLE contract_expiry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    exchange TEXT NOT NULL,
    product_type TEXT,            -- FUTURES/OPTION
    expiry_date DATE NOT NULL,
    underlying_symbol TEXT,       -- 标的合约（期权用）
    strike_price DECIMAL(20,4),   -- 行权价（期权用）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 三、定时任务（Celery Beat）

### 3.1 同步指数日线

| 属性 | 值 |
|------|-----|
| 任务名 | `sync_index_daily` |
| 频率 | 每日 18:30 |
| 数据源 | Tushare API / AKShare |
| 指数 | 000852（中证1000）、000300（沪深300） |
| 写入表 | `daily_index_prices` |

### 3.2 预计算期权希腊字母

| 属性 | 值 |
|------|-----|
| 任务名 | `compute_option_greeks` |
| 频率 | 每日 20:00 |
| 输入 | 当日结算价 + 合约信息 + 标的收盘价 |
| 计算 | Black-Scholes 模型逐腿计算 Delta/Gamma/Vega/Theta |
| 写入表 | `option_greeks_daily` |

### 3.3 计算日频 VWAP

| 属性 | 值 |
|------|-----|
| 任务名 | `compute_daily_vwap` |
| 频率 | 每日 18:30 |
| 输入 | 分钟成交数据（`minute_quotes`） |
| 写入 | `trades.vwap` 字段（按合约回填） |

---

## 四、账单解析器增强

### 4.1 新增解析字段

| 字段 | 来源位置 | 目标表 | 说明 |
|------|----------|--------|------|
| `trade_time` | 成交明细表时间列 | `trades.trade_time` | 精确到秒 |
| `order_type` | 委托类型列（如有） | `trades.order_type` | 市价/限价 |
| `strategy_tag` | 用户预配置映射 | `trades.strategy_tag` | 按合约/品种自动标记 |
| `flow_type` | 资金变动描述 | `bill_fund_flows.flow_type` | 标准化分类 |

### 4.2 解析后处理

账单解析完成后，自动执行：

1. **资金流水提取**: 从 `bill_raw_sections` 中提取资金变动项，写入 `bill_fund_flows`
2. **VWAP 回填**: 触发 `compute_daily_vwap` 任务
3. **恒等式校验**: 验证 `bill_fund_flows` 合计与账单期末权益一致

---

## 五、API 接口（tz-data 提供）

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/bills/{id}/fund-flows` | 获取账单资金流水 |
| GET | `/api/market/index/{code}/daily` | 指数日线数据 |
| GET | `/api/options/greeks/{date}` | 指定日期希腊字母 |
| GET | `/api/contracts/{symbol}/expiry` | 合约到期信息 |

---

## 六、TDD 测试清单

| 测试文件 | 测试内容 |
|----------|----------|
| `tests/test_bill_parser_enhanced.py` | 新增字段解析准确性 |
| `tests/test_fund_flows.py` | bill_fund_flows CRUD + 恒等式校验 |
| `tests/test_greeks_precompute.py` | 希腊字母计算精度（与理论值对比） |
| `tests/test_index_sync.py` | 指数同步幂等性 + 数据完整性 |
| `tests/test_vwap_calc.py` | VWAP 计算正确性 |
| `tests/test_contract_expiry.py` | 到期信息准确性 |

---

## 七、数据质量保障

### 7.1 校验规则

| 规则 | 检查方式 | 处理 |
|------|----------|------|
| 流水号连续性 | 序列号递增检查 | 告警 |
| 余额勾稽 | 上日余额 + 当日变动 = 本日余额 | 标记异常 |
| 流水去重 | 流水号唯一性约束 | 拒绝插入 |
| 金额非负校验 | 特定 flow_type 金额符号检查 | 拒绝插入 |

### 7.2 审计

- `bill_fund_flows` 原始数据不可修改，修正需新增记录
- 所有解析操作记录日志（`parse_log` 表）
- 数据版本号标记（`bills.parse_version`）
