# 账单与交易管理

> 版本：v0.7.0 | 最后更新：2026-05-17

## CFMMC 账单下载

### 前提条件

1. 拥有 CFMMC（中国期货市场监控中心）账户
2. 通过前端「账户管理」页面配置 CFMMC 凭证（AES-256 加密存储）
3. 或手动将 Cookie 保存到 `data/cfmmc/cookies/` 目录

### 自动下载

```bash
# CLI 自动下载
tzdata download cfmmc --auto

# 或通过前端「账单管理」页面上传
```

### Celery 自动获取

```python
from tzdata_pkg.scheduler.tasks.statement_tasks import auto_fetch_statements
auto_fetch_statements.delay(account_id=1)
```

## 账单解析

### 解析流程

1. 账单文件上传（`.txt` 格式，CFMMC 标准格式）
2. `CFMMCParser` 解析 HTML/txt 内容
3. 提取交易记录写入 `trades` 表
4. 记录解析状态到 `statement_status` 表

### 手动解析

```python
from tzdata_pkg.maintenance.statements.parsers.cfmmc_parser import CFMMCParser

parser = CFMMCParser()
result = parser.parse_file("path/to/bill.txt")
```

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/maintenance/statements/upload` | 上传账单 |
| POST | `/api/maintenance/statements/{id}/parse` | 解析账单 |
| DELETE | `/api/maintenance/statements/{id}` | 删除账单 |
| GET | `/api/maintenance/statements` | 账单状态列表 |

## 交易开平匹配

### 匹配算法

`TradeMatcher` 使用 **FIFO（先进先出）** 算法配对开平仓：

1. 按 `instrument` 分组交易
2. 收集所有开仓（buy open / sell open）和平仓（sell close / buy close）
3. 双向匹配：
   - 多头开仓 vs 空头平仓（long opens vs long closes）
   - 空头开仓 vs 多头平仓（short opens vs short closes）
4. 支持部分平仓：单笔开仓可被多笔平仓消耗

### 运行匹配

```bash
# 执行匹配
python -m tzdata_pkg.cli.trade_match match

# 查看统计
python -m tzdata_pkg.cli.trade_match stats

# 验证完整性
python -m tzdata_pkg.cli.trade_match verify
```

### Celery 自动匹配

每日 20:30 自动执行：
```python
from tzdata_pkg.scheduler.tasks.statement_tasks import trade_matching_task
trade_matching_task.delay()
```

### 匹配结果

- `matched_trades` 表 — 开平仓配对记录
- `trade_performance` 表 — 交易绩效分析（含 Greeks 字段）

## 盈亏计算

### 期货盈亏

```
price_pnl = close_price - open_price  (多头)
price_pnl = open_price - close_price  (空头)
money_pnl = price_pnl × volume × multiplier
net_pnl = money_pnl - commission
```

### 期权盈亏

```
premium_pnl = close_premium - open_premium  (多头)
premium_pnl = open_premium - close_premium  (空头)
money_pnl = premium_pnl × volume
net_pnl = money_pnl - commission
```

### 合约乘数

常见品种乘数定义在 `trade_matcher.py` 的 `CONTRACT_MULTIPLIERS` 字典中：

| 品种 | 乘数 | 品种 | 乘数 |
|------|------|------|------|
| IF/IH | 300 | IC/IM | 200 |
| MO | 100 | HO | 10000 |
| AG | 15 | AU | 1000 |
| RB | 10 | M/Y/A | 10 |

## 余额校验与滑点对账

### 余额校验

验证复式记账方程：期初余额 + 出入金 + 盈亏 = 期末余额

```
POST /api/maintenance/statements/verify-balance
```

### 滑点对账

对比账单价格与市场价格（结算价）：

```
POST /api/maintenance/statements/reconcile
GET  /api/maintenance/statements/reconcile/{account_id}
```

## 账户管理

### 创建账户

```python
# 通过 API
POST /api/maintenance/accounts
Body: {
    "account_name": "测试账户",
    "account_number": "123456",
    "futures_company": "XX期货",
    "cfmmc_username": "user",
    "cfmmc_password": "pass",
    "tracking_start_date": "2025-01-01"
}
```

### 凭证管理

```python
from tzdata_pkg.maintenance.statements.credential_vault import CredentialVault

vault = CredentialVault()
vault.save_credentials(account_id=1, username="user", password="pass")
creds = vault.get_credentials(account_id=1)
```

## 下一页

- [交易日历与合约管理](08-trade-calendar.md) — 日历和主力合约
- [MO 期权数据同步](09-mo-data-sync.md) — MO 专项同步
