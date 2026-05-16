# tz-data 工程：资金流水与盈亏分析 — 数据服务需求

> **来源**：本需求从 `tz2.0/docs/bill/账单-资金流水与盈亏分析.md` 提取
> **目标**：在 tz-data 工程中新增数据表、分类引擎和校验任务，为 tz2.0 的分析服务提供结构化数据
> **优先级**：阶段一先实施资金流水分类 + 日终快照 + 恒等式校验

---

## 一、现有能力盘点

### 1.1 已有数据表（bills.db / tzdata_trading.db）

| 表名 | 用途 | 维护方 |
|------|------|--------|
| `bills` | 账单主记录（日结单概要） | tz2.0 |
| `bill_details` | 账单明细（JSON 存储） | tz2.0 |
| `trades` | 扁平化交易记录 | tz2.0 |
| `account_summary` | 月度账户汇总 | tz-data |
| `positions_summary` | 日终持仓汇总 | tz-data |

### 1.2 已有服务

| 服务 | 文件 | 功能 |
|------|------|------|
| `BillStorage` | `src/data/bill_storage.py` | 账单 CRUD |
| `BillParser` | `src/data/bill_parser/parser.py` | PDF 解析 |
| 数据模型 | `src/data/bill_parser/models.py` | BillSummary, TransactionRecord, PositionRecord, DepositRecord |

### 1.3 现有缺口

- 没有独立的**资金流水表**（出入金、手续费、权利金等作为独立流水记录存储）
- 没有**资金流水分类**能力（无法按类型归集统计）
- 没有**日终资金快照表**（无法高效查询历史权益曲线）
- 没有**会计恒等式自动校验**能力
- 盈亏计算依赖 `trades` 表的 `total_pnl` 字段，缺乏逐笔配对

---

## 二、阶段一：资金流水分类引擎

### 2.1 新增数据表

#### 2.1.1 资金流水原始记录表

```sql
CREATE TABLE IF NOT EXISTS capital_transactions_raw (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL,                          -- 关联账单ID
    trade_date TEXT NOT NULL,                          -- 交易日 YYYY-MM-DD
    transaction_time TEXT,                             -- 交易时间（如有）
    serial_no TEXT UNIQUE,                             -- 流水号（期货公司生成）
    transaction_type TEXT NOT NULL,                    -- 原始类型描述
    amount REAL NOT NULL,                              -- 金额（正为收入，负为支出）
    balance_after REAL NOT NULL,                       -- 交易后余额
    description TEXT,                                  -- 摘要/备注
    channel TEXT,                                      -- 渠道：银期转账/柜台
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cap_txn_bill
    ON capital_transactions_raw(bill_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_cap_txn_date
    ON capital_transactions_raw(trade_date);
```

**数据来源**：从 `bill_details` 表中 `detail_type = 'deposit'` 的记录提取出入金流水；从 `bill_details` 表中 `detail_type = 'transaction'` 的记录提取手续费、盈亏等流水。

#### 2.1.2 标准化资金流水分类表

```sql
CREATE TABLE IF NOT EXISTS capital_transactions_classified (
    classified_id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_transaction_id INTEGER NOT NULL,
    bill_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,

    -- 标准化类型
    flow_type TEXT NOT NULL,                           -- 标准化流水类型
    flow_category TEXT NOT NULL,                       -- 归类类别（一级分类）
    flow_subtype TEXT,                                 -- 二级分类

    -- 业务属性
    business_context TEXT,                             -- 交易/交割/行权/质押/强平
    is_recurring INTEGER DEFAULT 0,                    -- 是否定期发生
    is_external_transfer INTEGER DEFAULT 0,            -- 是否外部资金划转

    amount REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (raw_transaction_id) REFERENCES capital_transactions_raw(transaction_id) ON DELETE CASCADE,
    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cap_classified_type
    ON capital_transactions_classified(bill_id, flow_type, trade_date);
CREATE INDEX IF NOT EXISTS idx_cap_classified_category
    ON capital_transactions_classified(flow_category, flow_subtype, trade_date);
```

#### 2.1.3 账户日终资金余额表

```sql
CREATE TABLE IF NOT EXISTS daily_account_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL UNIQUE,                -- 日期 YYYY-MM-DD

    -- 期初/期末权益
    opening_balance REAL NOT NULL,                     -- 日初权益
    closing_balance REAL NOT NULL,                     -- 日终权益

    -- 当日变动（按分类汇总）
    deposit_total REAL DEFAULT 0,                      -- 当日入金总额
    withdrawal_total REAL DEFAULT 0,                   -- 当日出金总额
    realized_pnl REAL DEFAULT 0,                       -- 当日已实现盈亏
    unrealized_pnl REAL DEFAULT 0,                     -- 当日未实现盈亏
    premium_net REAL DEFAULT 0,                        -- 权利金净收支
    exercise_pnl REAL DEFAULT 0,                       -- 行权/交割盈亏
    fee_total REAL DEFAULT 0,                          -- 当日费用总额
    interest_total REAL DEFAULT 0,                     -- 当日利息总额
    other_total REAL DEFAULT 0,                        -- 其他变动

    -- 净变动
    net_change REAL NOT NULL,                          -- 当日净变动

    -- 可用资金与保证金
    available_balance REAL NOT NULL,                   -- 可用资金
    margin_used REAL NOT NULL,                         -- 保证金占用

    -- 校验
    balance_check_status TEXT DEFAULT 'pending',       -- pending/ok/error
    balance_discrepancy REAL DEFAULT 0,                -- 余额差异

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_snapshot_date
    ON daily_account_snapshots(snapshot_date);
```

### 2.2 资金流水分类体系

建立标准化的分类映射规则：

| 原始流水类型模式 | flow_type | flow_category | flow_subtype | 归类类别 |
|:---|:---|:---|:---|:---|
| 入金, 银期转账入 | `deposit` | `capital_transfer` | `bank_transfer_in` | 本金增加 |
| 出金, 银期转账出 | `withdrawal` | `capital_transfer` | `bank_transfer_out` | 本金提取 |
| 平仓盈亏, 期货盈亏, 盯市盈亏-平仓 | `realized_pnl` | `pnl_transfer` | `close_pnl` | 已实现盈亏 |
| 持仓盈亏, 盯市盈亏-持仓 | `unrealized_pnl` | `pnl_transfer` | `position_pnl` | 未实现盈亏 |
| 权利金收入, 卖方权利金 | `premium_income` | `pnl_transfer` | `premium_received` | 卖出期权收取 |
| 权利金支出, 买方权利金 | `premium_expense` | `pnl_transfer` | `premium_paid` | 买入期权支付 |
| 行权盈亏, 交割盈亏 | `exercise_pnl` | `pnl_transfer` | `exercise_delivery` | 行权/期货交割 |
| 手续费, 交易费, 佣金 | `commission` | `fee` | `trading_fee` | 交易成本 |
| 交易所规费 | `exchange_fee` | `fee` | `exchange_fee` | 交易所规费 |
| 结算费 | `settlement_fee` | `fee` | `settlement_fee` | 结算费 |
| 交割手续费 | `delivery_fee` | `fee` | `delivery_fee` | 交割手续费 |
| 存款利息 | `interest_income` | `interest` | `deposit_interest` | 利息收入 |
| 融资利息 | `interest_expense` | `interest` | `financing_interest` | 利息支出 |
| 其他收入/支出 | `other` | `other` | `other` | 其他调整 |

### 2.3 类型映射引擎

**新增文件**：`src/data/fund_classification.py`

```python
class FundClassificationEngine:
    """资金流水分类引擎。

    将账单原始流水记录映射为标准化 flow_type。
    """

    # 映射规则：原始类型模式 → (flow_type, flow_category, flow_subtype)
    MAPPING_RULES = {
        # 出入金
        '入金': ('deposit', 'capital_transfer', 'bank_transfer_in'),
        '银期转账入': ('deposit', 'capital_transfer', 'bank_transfer_in'),
        '银行转入': ('deposit', 'capital_transfer', 'bank_transfer_in'),
        '出金': ('withdrawal', 'capital_transfer', 'bank_transfer_out'),
        '银期转账出': ('withdrawal', 'capital_transfer', 'bank_transfer_out'),
        '银行转出': ('withdrawal', 'capital_transfer', 'bank_transfer_out'),
        # 盈亏
        '平仓盈亏': ('realized_pnl', 'pnl_transfer', 'close_pnl'),
        '期货盈亏': ('realized_pnl', 'pnl_transfer', 'close_pnl'),
        '期权盈亏': ('realized_pnl', 'pnl_transfer', 'close_pnl'),
        '持仓盈亏': ('unrealized_pnl', 'pnl_transfer', 'position_pnl'),
        '浮动盈亏': ('unrealized_pnl', 'pnl_transfer', 'position_pnl'),
        '盯市盈亏': ('unrealized_pnl', 'pnl_transfer', 'position_pnl'),
        # 权利金
        '权利金收入': ('premium_income', 'pnl_transfer', 'premium_received'),
        '卖方权利金': ('premium_income', 'pnl_transfer', 'premium_received'),
        '权利金支出': ('premium_expense', 'pnl_transfer', 'premium_paid'),
        '买方权利金': ('premium_expense', 'pnl_transfer', 'premium_paid'),
        # 费用
        '手续费': ('commission', 'fee', 'trading_fee'),
        '交易费': ('commission', 'fee', 'trading_fee'),
        '佣金': ('commission', 'fee', 'trading_fee'),
        '交易所规费': ('exchange_fee', 'fee', 'exchange_fee'),
        '结算费': ('settlement_fee', 'fee', 'settlement_fee'),
        '交割手续费': ('delivery_fee', 'fee', 'delivery_fee'),
        # 行权/交割
        '行权盈亏': ('exercise_pnl', 'pnl_transfer', 'exercise_delivery'),
        '交割盈亏': ('exercise_pnl', 'pnl_transfer', 'exercise_delivery'),
        # 利息
        '存款利息': ('interest_income', 'interest', 'deposit_interest'),
        '融资利息': ('interest_expense', 'interest', 'financing_interest'),
    }

    @classmethod
    def classify_transaction(cls, raw_type: str) -> tuple:
        """将原始流水类型映射为标准化分类。

        Args:
            raw_type: 账单中的原始类型描述

        Returns:
            (flow_type, flow_category, flow_subtype) 三元组

        Raises:
            ValueError: 无法匹配任何规则时
        """
        for pattern, classification in cls.MAPPING_RULES.items():
            if pattern in raw_type:
                return classification
        raise ValueError(f"无法分类的流水类型: {raw_type}")

    @classmethod
    def classify_bill_details(cls, bill_id: int, session) -> int:
        """对指定账单的所有 detail 记录执行分类。

        Args:
            bill_id: 账单ID
            session: 数据库会话

        Returns:
            分类记录数
        """
        # 1. 从 bill_details 提取 deposit 类型记录 → capital_transactions_raw
        # 2. 从 bill_details 提取 transaction 类型记录 → capital_transactions_raw
        # 3. 对每条 raw 记录调用 classify_transaction → capital_transactions_classified
        # 4. 返回分类总数
        pass
```

### 2.4 会计恒等式校验

**新增文件**：`src/data/balance_reconciliation.py`

```python
class BalanceReconciliationService:
    """日终余额勾稽校验服务。

    校验公式：
    期末权益 = 期初权益 + 入金 - 出金 + 已实现盈亏 + 未实现盈亏
              + 权利金净收支 + 行权盈亏 - 手续费 - 其他费用
    """

    EQUATION_TOLERANCE = 0.01  # 允许四舍五入误差

    @classmethod
    def verify_daily_snapshot(cls, snapshot_date: str, session) -> dict:
        """校验指定日期的余额勾稽关系。

        Args:
            snapshot_date: 校验日期 YYYY-MM-DD
            session: 数据库会话

        Returns:
            {
                'status': 'ok' | 'error',
                'expected_closing': float,
                'actual_closing': float,
                'discrepancy': float,
                'components': {...}
            }
        """
        # 1. 从 daily_account_snapshots 获取当日快照
        # 2. 计算各项变动汇总（从 capital_transactions_classified）
        # 3. 计算 expected_closing = opening + 各变动项
        # 4. discrepancy = actual_closing - expected_closing
        # 5. 更新 balance_check_status 和 balance_discrepancy
        # 6. 返回校验结果
        pass

    @classmethod
    def verify_all_snapshots(cls, session) -> list:
        """校验所有日终快照。

        Returns:
            校验结果列表，含 status 和 discrepancy 信息
        """
        pass
```

### 2.5 日终快照生成任务

**新增文件**：`src/data/daily_snapshot_generator.py`

```python
class DailySnapshotGenerator:
    """日终资金快照生成器。

    从账单解析结果自动生成 daily_account_snapshots。
    """

    @classmethod
    def generate_from_bill(cls, bill_id: int, session) -> int:
        """从指定账单生成日终快照。

        Args:
            bill_id: 账单ID
            session: 数据库会话

        Returns:
            生成的快照数
        """
        # 1. 获取前一日 closing_balance 作为当日 opening_balance
        # 2. 从 capital_transactions_classified 汇总当日变动
        # 3. 计算 net_change = 各项变动之和
        # 4. closing_balance = opening_balance + net_change
        # 5. 从 positions_summary 获取保证金占用
        # 6. available_balance = closing_balance - margin_used
        # 7. 写入 daily_account_snapshots
        # 8. 返回快照数
        pass

    @classmethod
    def regenerate_all(cls, session) -> int:
        """重新生成所有日终快照。

        Returns:
            生成的快照总数
        """
        pass
```

### 2.6 实施计划

| 任务 | 优先级 | 预估工时 | 前置依赖 |
|------|--------|----------|----------|
| 创建 3 张新表 DDL | P0 | 2h | 无 |
| 实现 FundClassificationEngine | P0 | 4h | DDL 完成 |
| 实现 BalanceReconciliationService | P0 | 3h | 分类引擎完成 |
| 实现 DailySnapshotGenerator | P0 | 3h | 分类引擎完成 |
| 编写单元测试 | P0 | 3h | 服务完成 |
| 集成到账单解析流程 | P1 | 2h | 全部完成 |

---

## 三、阶段二：盈亏计算引擎（后续实施）

### 3.1 新增数据表

```sql
-- 逐笔交易记录表（扩展现有 trades 表的字段）
CREATE TABLE IF NOT EXISTS trade_transactions (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER,
    trade_ref TEXT NOT NULL,                         -- 成交编号
    trade_date TEXT NOT NULL,
    trade_time TEXT,                                 -- 精确到毫秒
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    contract_month TEXT,                             -- 合约月份
    trade_type TEXT NOT NULL,                        -- open/close/close_today/close_ystd
    direction TEXT NOT NULL,                         -- B=买, S=卖
    offset_flag TEXT NOT NULL,                       -- 0=开仓, 1=平仓, 2=平今, 3=平昨
    price REAL NOT NULL,
    volume INTEGER NOT NULL,
    turnover REAL NOT NULL,
    commission REAL NOT NULL,
    strategy_tag TEXT,                               -- 策略标签
    open_trade_ref TEXT,                             -- 对应开仓编号
    open_price REAL,                                 -- 开仓均价（平仓时回填）
    open_time TEXT,                                  -- 开仓时间（平仓时回填）
    realized_pnl REAL,                               -- 平仓盈亏
    pnl_percentage REAL,                             -- 盈亏百分比
    is_paired INTEGER DEFAULT 0,                     -- 是否已配对
    pairing_method TEXT,                             -- FIFO/LIFO/指定
    holding_days INTEGER,                            -- 持仓天数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 日终持仓记录表
CREATE TABLE IF NOT EXISTS daily_positions (
    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER,
    position_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    long_volume INTEGER DEFAULT 0,
    long_cost REAL DEFAULT 0,
    short_volume INTEGER DEFAULT 0,
    short_cost REAL DEFAULT 0,
    settlement_price REAL NOT NULL,
    unrealized_pnl REAL DEFAULT 0,
    margin_required REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bill_id, position_date, symbol)
);

-- 盈亏流水表
CREATE TABLE IF NOT EXISTS pnl_waterfall (
    pnl_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER,
    pnl_date TEXT NOT NULL,
    pnl_type TEXT NOT NULL,                          -- realized/unrealized/fee/other
    pnl_subtype TEXT,
    amount REAL NOT NULL,
    trade_ref TEXT,
    symbol TEXT,
    is_realized INTEGER NOT NULL,
    holding_days INTEGER,
    reference_price REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 盈亏归因分析表
CREATE TABLE IF NOT EXISTS pnl_attribution (
    attribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    attribution_date TEXT NOT NULL,
    period_type TEXT NOT NULL,                       -- daily/weekly/monthly
    dimension_type TEXT NOT NULL,                    -- symbol/direction/strategy
    dimension_value TEXT NOT NULL,
    total_pnl REAL NOT NULL,
    realized_pnl REAL DEFAULT 0,
    unrealized_pnl REAL DEFAULT 0,
    trade_count INTEGER DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    win_rate REAL,
    profit_factor REAL,
    is_summary INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(attribution_date, period_type, dimension_type, dimension_value)
);
```

### 3.2 开平配对引擎（FIFO）

```python
class TradePairingEngine:
    """开平仓配对引擎。

    支持 FIFO、LIFO、指定配对方法。
    """
    def pair_trades(self, trades: list, method: str = 'FIFO') -> list:
        pass
```

### 3.3 盈亏计算公式

```python
class PnlCalculator:
    """盈亏计算器。"""

    @staticmethod
    def calculate_future_pnl(open_price, close_price, volume, multiplier, direction) -> float:
        """期货盈亏计算。"""
        pass

    @staticmethod
    def calculate_option_pnl(open_premium, close_premium, volume, multiplier, direction) -> float:
        """期权平仓盈亏。"""
        pass

    @staticmethod
    def calculate_net_value(equity_series: dict) -> list:
        """动态权益法净值计算（剔除出入金影响）。

        r_t = (权益_t - 权益_{t-1} - 净出入金_t) / 权益_{t-1}
        """
        pass
```

---

## 四、与现有流程的集成点

### 4.1 账单解析流程集成

在现有 `BillStorage.batch_insert_details()` 之后，新增后处理步骤：

```
账单解析完成
    ↓
bill_details 写入完成
    ↓
【新增】FundClassificationEngine.classify_bill_details()  →  分类流水写入
    ↓
【新增】DailySnapshotGenerator.generate_from_bill()      →  日终快照写入
    ↓
【新增】BalanceReconciliationService.verify_daily_snapshot()  →  勾稽校验
    ↓
更新账单状态（含校验结果）
```

### 4.2 API 暴露（通过 tz-data 或 tz2.0）

| API | 路径 | 返回 |
|-----|------|------|
| 资金流水分类汇总 | `/api/bills/{bill_id}/fund-flow/summary` | 按 flow_type 汇总的金额 |
| 日终快照查询 | `/api/bills/fund-flow/snapshots?start=&end=` | 快照列表 |
| 恒等式校验结果 | `/api/bills/{bill_id}/reconciliation` | 校验状态和差异 |
| 盈亏流水查询 | `/api/bills/{bill_id}/pnl/waterfall` | 盈亏流水列表 |
| 盈亏归因查询 | `/api/bills/{bill_id}/pnl/attribution?dimension=symbol` | 归因结果 |

---

## 五、测试要求

**所有新增服务必须遵循 TDD 规范**，测试文件位于 `tests/data/`：

- `tests/data/test_fund_classification.py` — 分类引擎测试
- `tests/data/test_daily_snapshot.py` — 快照生成测试
- `tests/data/test_balance_reconciliation.py` — 恒等式校验测试

详见 `tz2.0/docs/bill/资金流水与盈亏分析-测试规划.md`。
