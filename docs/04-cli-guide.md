# CLI 使用指南

> 版本：v0.7.0 | 最后更新：2026-05-15

## tzdata 主命令

通过 `tzdata` CLI 入口操作（基于 Click 框架）：

```bash
tzdata --help
```

### 下载行情数据

#### CFFEX（中金所）

```bash
# 下载 MO 品种日线（全量）
tzdata download cffex --product MO

# 指定日期范围
tzdata download cffex --product MO --from 2025-01-01 --to 2025-05-01

# 增量下载（从上次日期开始）
tzdata download cffex --product MO --incremental

# 下载持仓排名
tzdata download cffex --product MO --data-type position --from 2025-01-01 --to 2025-05-01
```

支持的产品：`MO`, `IM`, `IC`, `IF`, `IH`, `IO`, `HO`

#### SHFE（上期所）

```bash
# 下载 AU 品种日线
tzdata download shfe --product AU

# 增量下载
tzdata download shfe --product AU --incremental
```

#### Tushare

```bash
# 下载日线
tzdata download tushare --type daily --underlying MO --from 2025-01-01 --to 2025-05-01

# 下载分钟K线
tzdata download tushare --type minute --underlying MO --from 2025-01-01 --to 2025-05-01

# 下载期权数据（希腊值、IV）
tzdata download tushare --type option --underlying MO --from 2025-01-01 --to 2025-05-01
```

#### CFMMC（监控中心账单）

```bash
# 自动下载（使用存储的 Cookie/凭证）
tzdata download cfmmc --auto
```

### 查询数据

```bash
# 查询行情
tzdata query quotes --exchange CFFEX --contract MO2505

# 查询持仓排名
tzdata query positions --contract MO2505 --date 2025-05-01

# 查询账单
tzdata query bills --account-id ACC001

# 查询盈亏汇总
tzdata query pnl --account-id ACC001 --from 2025-01-01 --to 2025-05-01
```

### 数据库迁移

```bash
# 预览（不执行，仅显示迁移内容）
tzdata migrate --dry-run

# 执行迁移
tzdata migrate

# 验证迁移结果（比较行数）
tzdata migrate --verify
```

### 调度器

```bash
# 启动调度器（前台运行）
tzdata schedule start

# 后台运行
tzdata schedule start --background

# 立即执行某个任务
tzdata schedule run cffex_daily

# 查看任务列表
tzdata schedule list
```

### API 服务

```bash
# 启动 API（默认 0.0.0.0:8000）
tzdata serve

# 指定端口
tzdata serve --port 8100

# 开发模式（自动重载）
tzdata serve --reload
```

### 状态与验证

```bash
# 查看所有数据库表行数
tzdata status

# 数据质量检查
tzdata validate
```

## 模块级 CLI 脚本

### 数据目录同步

```bash
cd C:\myspace\tz-data

# 列出所有数据目录
python -m tzdata_pkg.cli.sync_catalogs list

# 增量同步指定目录
python -m tzdata_pkg.cli.sync_catalogs sync --id 1 --mode incremental

# 全量同步指定目录
python -m tzdata_pkg.cli.sync_catalogs sync --id 1 --mode full --start 2025-01-01 --end 2026-05-15

# 同步所有启用的目录
python -m tzdata_pkg.cli.sync_catalogs sync-all --mode incremental
```

### MO 分钟数据同步

```bash
# 全量同步 MO 分钟数据
python -m tzdata_pkg.cli.sync_mo_minute full --freq 1min --start 2025-01-01 --end 2026-05-15

# 增量同步（自动找最新日期）
python -m tzdata_pkg.cli.sync_mo_minute incremental --freq 1min

# 列出 MO 合约列表
python -m tzdata_pkg.cli.sync_mo_minute contracts
```

### 交易开平匹配

```bash
# 执行开平匹配
python -m tzdata_pkg.cli.trade_match match

# 查看匹配统计
python -m tzdata_pkg.cli.trade_match stats

# 验证匹配完整性
python -m tzdata_pkg.cli.trade_match verify
```

### 其他 CLI

| 脚本 | 用途 |
|------|------|
| `bill_import.py` | 手动导入账单文件 |
| `calendar_init.py` | 初始化交易日历 |
| `import_contracts.py` | 从 Tushare 导入合约 |
| `import_trade_calendar.py` | 从 Tushare 导入交易日历 |
| `daily_sync.py` | MO 每日数据同步（IV + 标的日线） |

## 常见参数说明

### 日期格式

- CLI 使用 `YYYY-MM-DD` 格式（如 `2025-01-01`）
- 数据库存储使用 `YYYYMMDD` 或 `YYYY-MM-DD`（因表而异）

### 同步模式

| 模式 | 说明 |
|------|------|
| `incremental` | 增量同步，从上次同步日期开始 |
| `full` | 全量同步，清空后重新下载 |

### 频率参数

| 值 | 说明 |
|----|------|
| `1min` | 1 分钟 K 线 |
| `5min` | 5 分钟 K 线 |
| `15min` | 15 分钟 K 线 |
| `30min` | 30 分钟 K 线 |
| `60min` | 60 分钟 K 线 |
| `1d` | 日线 |

## 下一页

- [Python SDK](05-python-sdk.md) — Python 查询接口
- [数据维护与同步](06-data-maintenance.md) — 目录管理和同步引擎
