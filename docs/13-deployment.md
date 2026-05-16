# 部署与运维

> 版本：v0.7.0 | 最后更新：2026-05-15

## 运行环境

- **操作系统**：阿里云 ECS Windows Server 2025 Datacenter
- **Docker**：不支持，所有服务以原生 Windows 进程运行
- **数据库**：SQLite（WAL 模式），无需安装数据库服务

## 启动脚本

### quick-start.bat（交互式菜单）

```
1. 启动全部服务（Celery Worker + API + 前端）
2. 仅启动后端（Celery Worker + API）
3. 仅启动前端
4. 停止服务
5. 退出
```

### start.bat（一键启动）

自动启动：
1. Celery Worker（gevent pool）
2. FastAPI 后端（uvicorn，端口 8000）

等待服务就绪后提示是否启动前端。

### start-backend.bat（仅后端）

```bat
1. 启动 Celery Worker: celery -A tzdata_pkg.scheduler.celery_app worker --pool=gevent
2. 启动 FastAPI: uvicorn tzdata_pkg.api.server:app --host 0.0.0.0 --port 8000
```

### start-frontend.bat（仅前端）

```bat
cd frontend
npm run dev
```

### stop.bat（停止服务）

终止所有 Celery worker、uvicorn 和 node 进程。

## 数据库管理

### 备份

```powershell
$backup_dir = "C:\myspace\tz-data\backups\$(Get-Date -Format 'yyyyMMdd')"
New-Item -ItemType Directory -Path $backup_dir -Force
Copy-Item data\tzdata_*.db $backup_dir\
# WAL 模式下也备份日志文件
Copy-Item data\tzdata_*.db-wal $backup_dir\ 2>$null
Copy-Item data\tzdata_*.db-shm $backup_dir\ 2>$null
```

### 优化

```cmd
backup-databases.bat
```

执行 SQLite VACUUM 操作，回收空间、优化性能。

### 数据目录

```
C:\myspace\tz-data\data\
├── tzdata_market.db          # 市场数据
├── tzdata_trading.db         # 交易数据
├── tzdata_analysis.db        # 分析数据
├── bills.db                  # 账单数据（tz2.0 共享）
├── bills/raw/                # 原始账单文件
├── cfmmc/cookies/            # CFMMC Cookie
└── uploads/                  # 上传文件
```

## 日志

### 日志位置

```
C:\myspace\tz-data\logs\
├── app.log                   # 文本格式日志
├── app.json.log              # JSON 格式日志（便于分析）
└── ...
```

### 日志级别

通过 `LOG_LEVEL` 环境变量控制：`DEBUG` < `INFO` < `WARNING` < `ERROR` < `CRITICAL`

### 日志格式

- 控制台输出带颜色
- `app.log` — 纯文本格式
- `app.json.log` — JSON 格式，每行一条记录

### 查看日志

```powershell
# 查看最新日志
Get-Content C:\myspace\tz-data\logs\app.log -Tail 50

# 搜索错误日志
Select-String -Path C:\myspace\tz-data\logs\app.log -Pattern "ERROR"
```

## Celery Worker 运维

### 启动

```bash
celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info --pool=gevent
```

### 监控

```bash
celery -A tzdata_pkg.scheduler.celery_app flower --port=5555
```

访问 `http://localhost:5555` 查看任务状态、队列长度、Worker 健康。

### 重启

先 `stop.bat` 停止，再 `start.bat` 或 `start-backend.bat` 重新启动。

## Redis 运维

### 检查状态

```bash
redis-cli ping    # 应返回 PONG
```

### Windows 方案

- **Memurai** — Redis Windows 兼容版，直接安装
- **WSL Redis** — 通过 WSL 运行 `redis-server`

## 常见问题

### Q1: Celery Worker 在 Windows 上启动失败？

必须使用 `--pool=gevent` 参数：
```bash
celery -A tzdata_pkg.scheduler.celery_app worker --pool=gevent
```

### Q2: Redis 无法连接？

检查 Redis 是否运行：
```bash
redis-cli ping
```
如未安装，可使用 Memurai 或 WSL Redis。

### Q3: 端口被占用？

- 后端：启动时指定 `--port` 或修改 `.env` 中 `BACKEND_PORT`
- 前端：修改 `frontend/vite.config.js` 中的 port 配置

### Q4: 数据库锁定？

SQLite 不支持多进程同时写入。Celery 任务已通过并发控制器确保不会并发写入同一目录。

### Q5: Tushare 下载报错？

确保设置了 `TUSHARE_TOKEN` 环境变量。

### Q6: CFMMC 无法自动下载？

Cookie 可能已过期。手动登录 https://investors.cfmmc.com/，或通过前端「账户管理」页面更新 CFMMC 凭据。

### Q7: 同步任务卡住？

1. 检查 Celery Worker 日志
2. 查看前端「同步任务」页面的错误信息
3. 可能是网络问题或 API 限流

### Q8: 账单解析失败？

确保上传的是 CFMMC 标准格式的 `.txt` 文件。

### Q9: 前端金额显示不正确？

确保使用 `formatMoney()` / `formatMoneyFull()` 工具函数，不要直接使用 `.toFixed()`。

### Q10: 如何重置数据库？

```powershell
# 删除现有数据库（谨慎操作！）
Remove-Item data\tzdata_*.db -Force
Remove-Item data\tzdata_*.db-wal -Force -ErrorAction SilentlyContinue
Remove-Item data\tzdata_*.db-shm -Force -ErrorAction SilentlyContinue

# 重启后端，自动重新建表
```

## 版本历史

| 版本 | 主要变更 |
|------|----------|
| v0.3.0 | 12→3 数据库整合，Python SDK，CLI 入口 |
| v0.5.0 | 数据维护系统（目录/同步/质量/健康快照） |
| v0.6.0 | 交易日历模块、主力合约、交易时间模板 |
| v0.7.0 | MO 分钟数据同步、开平匹配引擎、账单管理 |

## 文档索引

- [快速入门](01-getting-started.md)
- [系统架构](02-architecture.md)
- [API 接口文档](03-api-reference.md)
- [CLI 使用指南](04-cli-guide.md)
- [Python SDK](05-python-sdk.md)
- [数据维护与同步](06-data-maintenance.md)
- [账单与交易管理](07-bill-management.md)
- [交易日历与合约管理](08-trade-calendar.md)
- [MO 期权数据同步](09-mo-data-sync.md)
- [Celery 任务调度](10-celery-tasks.md)
- [前端页面指南](11-frontend.md)
- [数据库表结构](12-database-schema.md)
