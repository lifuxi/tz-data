# tz-data 运维手册

> 版本：0.3.0 | 运维人员参考文档

## 目录

1. [系统架构](#1-系统架构)
2. [部署与安装](#2-部署与安装)
3. [日常运维](#3-日常运维)
4. [调度器管理](#4-调度器管理)
5. [数据质量监控](#5-数据质量监控)
6. [数据库维护](#6-数据库维护)
7. [API 服务运维](#7-api-服务运维)
8. [故障排查](#8-故障排查)
9. [升级与迁移](#9-升级与迁移)
10. [安全与备份](#10-安全与备份)

---

## 1. 系统架构

### 1.1 组件概览

```
                      ┌──────────────────────────┐
                      │     tzdata CLI (Click)    │
                      │  download / status / etc  │
                      └──────────┬───────────────┘
                                 │
                      ┌──────────v───────────────┐
                      │   APScheduler 调度器      │
                      │   日线 18:00 / 账单 20:00  │
                      └──────────┬───────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
  ┌──────v──────┐        ┌──────v──────┐        ┌───────v───────┐
  │ 交易所下载器  │        │ 外部 API     │        │ CFMMC 账单    │
  │ CFFEX/SHFE  │        │ Tushare     │        │ Selenium      │
  └──────┬──────┘        └──────┬──────┘        └───────┬───────┘
         │                      │                       │
         └──────────────────────┼───────────────────────┘
                                │
                      ┌─────────v───────────────┐
                      │   统一存储层 (3 DBs)      │
                      │   Market / Trading       │
                      │   / Analysis             │
                      └─────────┬───────────────┘
                                │
                ┌───────────────┼───────────────┐
           ┌────v────┐   ┌─────v──────┐  ┌─────v──────┐
           │ tz2.0    │   │ tz-ai      │  │ FastAPI    │
           │ (SDK)    │   │ (SDK)      │  │ (HTTP)     │
           └─────────┘   └────────────┘  └────────────┘
```

### 1.2 数据库分布

| 数据库 | 大小 | 核心表 | 用途 |
|--------|------|--------|------|
| `tzdata_market.db` | ~339 MB | daily_quotes(967K), position_detail(639K) | 行情、持仓、合约 |
| `tzdata_trading.db` | ~120 MB | cffex_daily_settlement(889K), trades(13.5K) | 账单、交易、账户 |
| `tzdata_analysis.db` | ~0.5 MB | feature_daily(5.5K) | 机构特征、信号 |

---

## 2. 部署与安装

### 2.1 环境要求

- Python 3.11+
- SQLite（Python 内置）
- Windows Server 2025 或 Linux

### 2.2 安装步骤

```bash
# 1. 克隆/进入项目
cd C:\myspace\tz-data

# 2. 安装依赖
pip install -e .

# 3. 设置环境变量
$env:TZ_DATA_DIR = "C:\myspace\tz-data\data"
$env:TUSHARE_TOKEN = "your_token"

# 4. 验证安装
tzdata --version   # 应显示 0.3.0
tzdata status      # 应显示各表行数
```

### 2.3 依赖说明

| 依赖 | 用途 | 必需 |
|------|------|------|
| requests | HTTP 下载 | 是 |
| pandas | 数据处理 | 是 |
| httpx | 异步 HTTP | 是 |
| beautifulsoup4 | HTML 解析 | 是 |
| chardet | 编码检测 | 是 |
| akshare | SHFE 数据下载 | 是 |
| tushare | Tushare API | 是 |
| selenium | CFMMC 自动下载 | 是 |
| Pillow | 验证码处理 | 是 |
| apscheduler | 定时任务调度 | 是 |
| click | CLI 框架 | 是 |
| fastapi | API 服务 | 是 |
| uvicorn | ASGI 服务器 | 是 |

---

## 3. 日常运维

### 3.1 每日数据下载

```bash
# 手动触发所有数据源下载
tzdata download cffex --product MO --incremental
tzdata download cffex --product IO --incremental
tzdata download cffex --product IM --incremental
tzdata download cffex --product HO --incremental
tzdata download shfe --product AU --incremental
tzdata download cfmmc --auto
```

### 3.2 数据状态检查

```bash
# 快速检查
tzdata status

# 数据质量
tzdata validate

# 数据库文件大小
ls -lh data/tzdata_*.db
```

### 3.3 日志查看

日志位于 `data/logs/` 目录：

```bash
# 查看最近下载日志
Get-Content data/logs\tzdata_*.log -Tail 50
```

### 3.4 定时任务执行清单

| 时间 | 任务 | 数据源 |
|------|------|--------|
| 18:00 | CFFEX 日线 | CFFEX 官网 |
| 18:30 | SHFE 日线 | AkShare |
| 19:00 | CFFEX 持仓 | CFFEX 官网 |
| 20:00 | CFMMC 账单 | 监控中心 |
| 22:00 | Tushare 日线 | Tushare API |
| 02:00 | 数据质量检查 | 内部 |

---

## 4. 调度器管理

### 4.1 启动调度器

```bash
# 前台运行（测试用）
tzdata schedule start

# 后台运行（生产用）
tzdata schedule start --background
```

### 4.2 查看任务状态

```bash
tzdata schedule list
```

输出示例：
```
  cffex_daily          | next: 2025-05-10 18:00:00 | cron
  shfe_daily           | next: 2025-05-10 18:30:00 | cron
  cffex_position       | next: 2025-05-10 19:00:00 | cron
  cfmmc_bills          | next: 2025-05-10 20:00:00 | cron
  tushare_daily        | next: 2025-05-10 22:00:00 | cron
  data_validate        | next: 2025-05-11 02:00:00 | cron
```

### 4.3 手动执行任务

```bash
# 立即执行 CFFEX 日线下载
tzdata schedule run cffex_daily

# 立即执行数据验证
tzdata schedule run data_validate
```

### 4.4 作为 Windows 服务运行

```powershell
# 使用 NSSM 将调度器注册为 Windows 服务
nssm install tzdata-scheduler "python" "-m tzdata_pkg schedule start --background"
nssm set tzdata-scheduler AppDirectory "C:\myspace\tz-data"
nssm set tzdata-scheduler Start SERVICE_AUTO_START
nssm start tzdata-scheduler
```

---

## 5. 数据质量监控

### 5.1 内置检查

```bash
tzdata validate
```

检查项：
- 表是否为空
- 行数是否异常
- 数据库是否可访问

### 5.2 数据新鲜度检查

```bash
tzdata query quotes --exchange CFFEX | Select-Object -First 1
```

查看最新 `trade_date`，确认数据是否及时更新。

### 5.3 自定义检查脚本

```python
from tzdata_pkg.query import TzDataClient
from datetime import date, timedelta

with TzDataClient() as client:
    # 检查最近 3 个交易日是否有数据
    quotes = client.quotes(exchange="CFFEX")
    dates = sorted(set(q["trade_date"] for q in quotes), reverse=True)
    latest = date.fromisoformat(dates[0]) if dates else None
    today = date.today()

    if latest and (today - latest).days > 3:
        print(f"WARNING: Latest CFFEX data is from {latest}, expected today")
    else:
        print(f"OK: Latest CFFEX data: {latest}")
```

---

## 6. 数据库维护

### 6.1 数据库备份

```powershell
# 备份所有数据库（PowerShell）
$backup_dir = "C:\myspace\tz-data\backups\$(Get-Date -Format 'yyyyMMdd')"
New-Item -ItemType Directory -Path $backup_dir -Force
Copy-Item data\tzdata_market.db $backup_dir\
Copy-Item data\tzdata_trading.db $backup_dir\
Copy-Item data\tzdata_analysis.db $backup_dir\
```

### 6.2 数据库优化

```bash
# SQLite VACUUM 回收空间
python -c "
import sqlite3
for db in ['data/tzdata_market.db', 'data/tzdata_trading.db', 'data/tzdata_analysis.db']:
    conn = sqlite3.connect(db)
    conn.execute('VACUUM')
    conn.execute('ANALYZE')
    conn.close()
    print(f'{db}: optimized')
"
```

### 6.3 WAL 模式说明

所有数据库使用 WAL (Write-Ahead Logging) 模式：
- 优点：读写不互斥，查询更快
- 注意：WAL 模式下会产生 `-wal` 和 `-shm` 伴生文件
- 备份时需要同时复制 `.db`, `-wal`, `-shm` 三个文件

### 6.4 索引维护

数据库创建时已自动建立以下索引：

```sql
-- Market DB
idx_daily_quotes_date         ON daily_quotes(trade_date)
idx_daily_quotes_contract     ON daily_quotes(contract_code)
idx_daily_quotes_exchange     ON daily_quotes(exchange)
idx_daily_quotes_date_contract ON daily_quotes(trade_date, contract_code)
idx_position_date             ON position_detail(trade_date)
idx_position_contract         ON position_detail(contract_code)

-- Trading DB
idx_trades_date               ON trades(trade_date)
idx_trades_account            ON trades(account_id)
idx_trades_product            ON trades(product)
idx_matched_open_date         ON matched_trades(open_date)
idx_matched_close_date        ON matched_trades(close_date)
idx_settlement_date           ON cffex_daily_settlement(trade_date)
```

---

## 7. API 服务运维

### 7.1 启动与停止

```bash
# 启动（前台）
tzdata serve --port 8100

# 开发模式（代码变更自动重启）
tzdata serve --reload

# 停止：Ctrl+C
```

### 7.2 健康检查

```bash
# 健康端点
curl http://localhost:8100/api/v1/admin/health

# 预期响应：{"status": "ok"}
```

### 7.3 使用 PM2 管理（Node.js 环境）

```bash
pm2 start "tzdata serve --port 8100" --name tzdata-api
pm2 save
pm2 startup
```

### 7.4 使用 NSSM 管理（Windows 服务）

```powershell
nssm install tzdata-api "tzdata" "serve --port 8100"
nssm set tzdata-api AppDirectory "C:\myspace\tz-data"
nssm set tzdata-api Start SERVICE_AUTO_START
nssm start tzdata-api
```

### 7.5 性能监控

| 指标 | 检查方式 | 正常范围 |
|------|----------|----------|
| API 响应时间 | `curl -w '%{time_total}'` | < 2s |
| 数据库大小 | `ls -lh data/tzdata_*.db` | < 1GB/库 |
| 内存占用 | Task Manager / `top` | < 500MB |
| 磁盘空间 | `df -h` / `Get-PSDrive` | > 5GB 可用 |

---

## 8. 故障排查

### 8.1 CFFEX 下载失败

**症状**：`tzdata download cffex` 报错

**排查步骤**：

1. 检查网络连接：
   ```bash
   curl -I http://www.cffex.com.cn/sj/mrhq/MO/csv/MO20250509.csv
   ```

2. 检查 Cookie 是否过期（CFMMC）：
   ```bash
   ls data/cfmmc/cookies/
   ```

3. 检查 CSV 解析是否正常：
   ```bash
   # 查看原始 CSV 文件
   ls data/cffex/raw/
   ```

**常见原因**：
- 交易所网站维护（通常在非交易时间）
- CSV 格式变更（需要更新 parser）
- 网络超时（可重试）

### 8.2 SHFE 下载失败

**症状**：`tzdata download shfe` 报错

**排查步骤**：

1. 检查 akshare 版本：
   ```bash
   pip show akshare
   ```

2. 测试 akshare 连接：
   ```python
   import akshare as ak
   print(ak.__version__)
   df = ak.futures_zh_daily_sina(symbol="AU0")
   print(df.head())
   ```

3. 升级 akshare：
   ```bash
   pip install --upgrade akshare
   ```

### 8.3 Tushare 下载失败

**症状**：token 无效或积分不足

**排查**：
1. 检查 token：`echo $env:TUSHARE_TOKEN`
2. 登录 tushare.pro 查看积分
3. 部分接口需要 2000+ 积分

### 8.4 CFMMC 下载失败

**症状**：Selenium 无法登录

**排查步骤**：

1. 检查 Chrome/Edge 驱动：
   ```bash
   pip show selenium
   ```

2. 检查 Cookie 文件是否存在：
   ```bash
   ls data/cfmmc/cookies/
   ```

3. Cookie 过期处理：
   - 手动登录 https://investors.cfmmc.com/
   - 导出 Cookie 到 `data/cfmmc/cookies/` 目录

### 8.5 数据库锁定

**症状**：`database is locked` 错误

**原因**：SQLite 写操作被阻塞

**解决**：
1. 确保没有多个进程同时写入同一数据库
2. 调度器中的任务已按时间错开，避免并发写入
3. 检查是否有未关闭的连接：
   ```bash
   # 查看谁在使用数据库文件
   handle.exe tzdata_market.db
   ```

### 8.6 API 服务无响应

**排查步骤**：

1. 检查进程：
   ```powershell
   Get-Process | Where-Object { $_.ProcessName -like "*python*" }
   ```

2. 检查端口：
   ```powershell
   netstat -ano | findstr 8100
   ```

3. 重启服务：
   ```powershell
   Restart-Service tzdata-api  # 如果注册为服务
   ```

---

## 9. 升级与迁移

### 9.1 版本升级

```bash
cd C:\myspace\tz-data
git pull
pip install -e .
tzdata --version
```

### 9.2 12→3 数据库迁移

**前置条件**：
- 所有旧数据库完整存在
- 新 3 个数据库不存在或为空

**步骤**：

```bash
# 1. 预览
tzdata migrate --dry-run

# 2. 执行
tzdata migrate

# 3. 验证
tzdata migrate --verify

# 4. 检查状态
tzdata status
```

**迁移后验证**：
```python
from tzdata_pkg.query import TzDataClient

with TzDataClient() as client:
    # 验证行情
    quotes = client.quotes()
    print(f"Quotes: {len(quotes)}")

    # 验证账单
    bills = client.bills()
    print(f"Bills: {len(bills)}")
```

### 9.3 回滚方案

如果迁移后发现问题：

```bash
# 删除新数据库，保留旧库
Remove-Item data/tzdata_market.db*
Remove-Item data/tzdata_trading.db*
Remove-Item data/tzdata_analysis.db*

# 重新执行迁移
tzdata migrate
```

---

## 10. 安全与备份

### 10.1 备份策略

**建议**：每日备份，保留 30 天

```powershell
# 备份脚本 (backup.ps1)
$backup_dir = "C:\myspace\tz-data\backups\$(Get-Date -Format 'yyyyMMdd')"
New-Item -ItemType Directory -Path $backup_dir -Force

# 关闭 WAL 确保数据一致
$dbs = @("tzdata_market.db", "tzdata_trading.db", "tzdata_analysis.db")
foreach ($db in $dbs) {
    $conn = New-Object System.Data.SQLite.SQLiteConnection
    $conn.ConnectionString = "Data Source=data/$db"
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "PRAGMA wal_checkpoint(TRUNCATE)"
    $cmd.ExecuteNonQuery() | Out-Null
    $conn.Close()

    Copy-Item "data/$db" "$backup_dir/$db"
    Copy-Item "data/$db-wal" "$backup_dir/$db-wal" -ErrorAction SilentlyContinue
    Copy-Item "data/$db-shm" "$backup_dir/$db-shm" -ErrorAction SilentlyContinue
}

# 清理 30 天前的备份
Get-ChildItem "C:\myspace\tz-data\backups" -Directory |
    Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Recurse -Force
```

### 10.2 敏感信息

| 信息 | 位置 | 保护方式 |
|------|------|----------|
| Tushare Token | 环境变量 | 不提交到代码库 |
| CFMMC Cookie | `data/cfmmc/cookies/` | 目录已加入 .gitignore |
| 账单数据 | `tzdata_trading.db` | 包含交易记录，限制访问 |

### 10.3 访问控制

- 数据库文件：设置 NTFS 权限，仅允许管理员和 tz-data 服务账户
- API 服务：当前为内网访问，不对外开放
- 日志文件：定期检查，清理过期日志

---

## 附录：快速参考

### 常用命令速查

```bash
# 日常操作
tzdata status                      # 数据状态
tzdata validate                    # 数据质量
tzdata download cffex --product MO --incremental  # 增量下载
tzdata schedule list               # 调度器状态

# 维护操作
tzdata serve --port 8100           # 启动 API
tzdata migrate --verify            # 验证迁移

# 开发操作
pip install -e ".[dev]"            # 安装开发依赖
pytest                             # 运行测试
```

### 数据量参考

| 指标 | 值 |
|------|-----|
| 日线行情总行数 | ~967K |
| 持仓排名总行数 | ~639K |
| 账单结算数据 | ~889K |
| 交易记录 | ~13.5K |
| 机构特征 | ~5.5K |
| 总数据量 | ~460 MB |
| 日均增量 | ~1-5 MB |
