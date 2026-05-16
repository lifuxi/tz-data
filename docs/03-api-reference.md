# API 接口文档

> 版本：v0.7.0 | 最后更新：2026-05-15

> 基础 URL: `http://localhost:8000`
> Swagger 文档: `http://localhost:8000/docs`

## 行情接口 `/api/v1/market/*`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v1/market/quotes` | 查询行情数据 | `exchange`, `contract`, `start_date`, `end_date` |
| GET | `/api/v1/market/contracts` | 合约列表 | `exchange`, `variety` |

## 持仓接口 `/api/v1/positions/*`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v1/positions/{product}` | 品种持仓排名 | `product`: 品种代码, `trade_date` |
| GET | `/api/v1/positions/{product}/top-holders` | 主力持仓集中度 | `product`: 品种代码 |

## 交易接口 `/api/v1/*`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v1/bills` | 账单列表 | `account_id`, `start_date`, `end_date` |
| GET | `/api/v1/trades` | 交易记录 | `account_id`, `start_date`, `end_date` |
| GET | `/api/v1/pnl` | 盈亏汇总 | `account_id`, `start_date`, `end_date` |
| GET | `/api/v1/account-summary` | 账户概览 | `account_id` |

## 分析接口 `/api/v1/*`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v1/signals` | 交易信号 | `signal_type`, `product`, `start_date`, `end_date` |
| GET | `/api/v1/regime` | 市场状态 | `product`, `trade_date` |
| GET | `/api/v1/institution-features` | 机构特征 | `product`, `trade_date` |
| GET | `/api/v1/option-features` | 期权特征 | `product`, `trade_date` |
| GET | `/api/v1/iv-snapshot` | IV 快照 | `underlying`, `trade_date` |
| GET | `/api/v1/tushare-daily` | Tushare 日线 | `underlying`, `start_date`, `end_date` |

## 管理接口 `/api/v1/admin/*`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v1/admin/status` | 系统完整状态 | — |
| GET | `/api/v1/admin/health` | 健康检查 | — |
| GET | `/api/v1/admin/verify/report` | 上次校验报告 | — |
| POST | `/api/v1/admin/verify/run` | 触发数据校验 | — |

## 数据层接口 `/api/v1/*`

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| GET | `/api/v1/bills/{bill_id}/fund-flows` | 账单资金流 | `bill_id` |
| GET | `/api/v1/market/index/{code}/daily` | 指数日线 | `code`: 000852/000300, `start_date`, `end_date` |
| GET | `/api/v1/options/greeks/{date}` | 期权 Greeks | `date`: YYYYMMDD |
| GET | `/api/v1/contracts/{symbol}/expiry` | 合约到期信息 | `symbol`: 品种代码 |

## 维护接口 `/api/maintenance/*`

### 数据目录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/catalogs` | 数据目录列表 |
| POST | `/api/maintenance/catalogs` | 创建数据目录 |
| GET | `/api/maintenance/catalogs/{id}` | 目录详情 |
| PUT | `/api/maintenance/catalogs/{id}` | 更新目录 |

### 健康快照

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/health/snapshot` | 最新健康快照 |
| GET | `/api/maintenance/health/diff` | 两次快照差异 |
| GET | `/api/maintenance/quality/{catalog_id}` | 目录质量评估 |
| POST | `/api/maintenance/health-snapshots/generate` | 生成健康快照 |
| GET | `/api/maintenance/health-snapshots` | 历史快照列表 |
| GET | `/api/maintenance/health-snapshots/latest` | 最新快照 |

### 账户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/accounts` | 账户列表 |
| POST | `/api/maintenance/accounts` | 创建账户 |

### 交易所管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/exchanges` | 交易所列表 |
| POST | `/api/maintenance/exchanges` | 创建交易所 |
| PUT | `/api/maintenance/exchanges/{id}` | 更新交易所 |
| DELETE | `/api/maintenance/exchanges/{id}` | 删除交易所 |

### 品种管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/products` | 品种列表 |
| POST | `/api/maintenance/products` | 创建品种 |
| PUT | `/api/maintenance/products/{id}` | 更新品种 |
| DELETE | `/api/maintenance/products/{id}` | 删除品种 |

### 合约管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/contracts` | 合约列表 |
| POST | `/api/maintenance/contracts` | 创建合约 |
| PUT | `/api/maintenance/contracts/{id}` | 更新合约 |
| DELETE | `/api/maintenance/contracts/{id}` | 删除合约 |
| POST | `/api/maintenance/contracts/import-from-tushare` | 从 Tushare 导入合约 |
| POST | `/api/maintenance/contracts/check-expired` | 检查到期合约 |
| GET | `/api/maintenance/contracts/expiring` | 即将到期合约 |

### 告警

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/alerts` | 告警列表 |
| GET | `/api/maintenance/alerts/recent` | 最近告警 |

### 交易日历

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/maintenance/trade-calendar/init` | 初始化交易日历 |
| GET | `/api/maintenance/trade-calendar/trading-days` | 查询交易日列表 |
| GET | `/api/maintenance/trade-calendar/is-trading-day` | 判断是否交易日 |
| GET | `/api/maintenance/trade-calendar/calendar` | 日历数据 |
| GET | `/api/maintenance/trade-calendar/status` | 日历状态 |
| GET | `/api/maintenance/trade-calendar/count` | 交易日计数 |
| GET | `/api/maintenance/trade-calendar/product/stats` | 产品日历统计 |
| POST | `/api/maintenance/trade-calendar/product/init` | 产品日历初始化 |
| POST | `/api/maintenance/trade-calendar/system-init` | 系统初始化 |
| GET | `/api/maintenance/trade-calendar/product/listing-dates` | 上市日期 |
| GET | `/api/maintenance/trade-calendar/product/trading-days` | 产品交易日 |
| POST | `/api/maintenance/trade-calendar/add-holiday` | 添加节假日 |
| GET | `/api/maintenance/trade-calendar/next-trading-day` | 下一个交易日 |
| GET | `/api/maintenance/trade-calendar/prev-trading-day` | 上一个交易日 |
| GET | `/api/maintenance/trade-calendar/trading-days-count` | 区间交易日数 |
| POST | `/api/maintenance/trade-calendar/import-from-tushare` | 从 Tushare 导入日历 |
| GET | `/api/maintenance/trade-calendar/cache/status` | 缓存状态 |
| POST | `/api/maintenance/trade-calendar/cache/preload` | 缓存预热 |
| POST | `/api/maintenance/trade-calendar/special-dates` | 添加特殊日期 |
| GET | `/api/maintenance/trade-calendar/special-dates` | 特殊日期列表 |
| DELETE | `/api/maintenance/trade-calendar/special-dates` | 删除特殊日期 |

### 主力合约

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/main-contract/{product}` | 获取主力合约 |
| POST | `/api/maintenance/main-contract/{product}` | 设置主力合约 |
| GET | `/api/maintenance/main-contract/{product}/series` | 主力合约序列 |
| GET | `/api/maintenance/main-contract/{product}/rollovers` | 换月记录 |
| POST | `/api/maintenance/main-contract/{product}/auto-populate` | 自动填充主力合约 |

### 交易时间

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/trading-hours/is-trading-time` | 判断是否交易时间 |
| GET | `/api/maintenance/trading-hours/{id}` | 模板详情 |
| POST | `/api/maintenance/trading-hours/templates` | 创建模板 |
| GET | `/api/maintenance/trading-hours/{id}/sessions` | 时段列表 |

### 账单管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maintenance/statements` | 账单状态列表 |
| POST | `/api/maintenance/statements/upload` | 上传账单 |
| POST | `/api/maintenance/statements/{id}/parse` | 解析账单 |
| DELETE | `/api/maintenance/statements/{id}` | 删除账单 |
| POST | `/api/maintenance/statements/verify-balance` | 余额校验 |
| POST | `/api/maintenance/statements/reconcile` | 滑点对账 |
| GET | `/api/maintenance/statements/reconcile/{account_id}` | 对账结果 |

### 凭证与配置

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/maintenance/credentials` | 创建 CFMMC 凭证 |
| GET | `/api/maintenance/sync/status` | 同步状态 |
| GET | `/api/maintenance/system-config` | 系统配置列表 |
| GET | `/api/maintenance/system-config/{key}` | 配置项详情 |
| PUT | `/api/maintenance/system-config` | 更新配置 |
| DELETE | `/api/maintenance/system-config/{key}` | 删除配置 |
| GET | `/api/maintenance/schedule` | Celery Beat 调度任务列表 |

## 请求/响应格式

所有接口使用 JSON 格式：

**成功响应**：
```json
{
  "success": true,
  "data": { ... },
  "total": 100
}
```

**错误响应**：
```json
{
  "detail": "错误描述信息"
}
```

## 下一页

- [CLI 使用指南](04-cli-guide.md) — 命令行工具用法
- [Python SDK](05-python-sdk.md) — Python 查询接口
