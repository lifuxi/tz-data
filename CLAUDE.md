# 项目规则

## 本地开发环境约束（阿里云 ECS Windows）

**运行环境**：阿里云 ECS Windows Server，**不支持 Docker**。所有服务必须以原生 Windows 进程方式启动。

### 端口分配

| 服务 | 端口 | 启动方式 |
|------|------|----------|
| 后端 API | 8000 | `uvicorn tzdata_pkg.api.server:app --port 8000` |
| 前端 | 3000 | `npm run dev` (在 frontend 目录) |
| Celery Worker | 系统分配 | `celery -A tzdata_pkg.scheduler.celery_app worker --pool=gevent` |
| Celery Flower | 5555 | `celery -A tzdata_pkg.scheduler.celery_app flower --port=5555` |
| Redis | 6379 | 外部服务（Memurai 或 WSL Redis） |
| QuestDB | 9000/8812 | 外部服务（可选） |

### 启动方式

- **快速启动**：运行 `quick-start.bat` 或 `start.bat` 选择选项 1
- **单独启动后端**：`start-backend.bat`（启动 Celery Worker + FastAPI）
- **单独启动前端**：`start-frontend.bat`（启动 Vite 开发服务器）
- **停止服务**：`stop.bat`

### 数据库架构

本项目使用 **SQLite** 作为主数据库，无需安装任何数据库服务：

```
C:\myspace\tz-data\data\
├── tzdata_market.db      # 市场数据（行情、合约等）
├── tzdata_trading.db     # 交易数据（账户、账单等）
├── tzdata_analysis.db    # 分析数据（监控、健康快照等）
└── bills.db              # 账单数据（被 tz2.0 项目共享读取）
```

- SQLite 使用 WAL 模式提升并发性能
- 数据库文件在首次运行时自动创建并执行 schema
- 备份：直接复制 `.db` 文件即可

### 依赖服务

- **Redis**：Celery 任务队列使用 Redis 作为 broker（`.env` 中 `CELERY_BROKER_URL=redis://localhost:6379/0`）。Windows 上可安装 Memurai（Redis Windows 兼容版）或使用 WSL Redis。如 Redis 未安装，Celery Worker 无法启动，但后端 API 仍可正常运行。
- **QuestDB**：时序数据存储，代码中条件导入，未安装时不影响核心功能。

### Celery Windows 注意

Windows 上 Celery worker 必须使用 `--pool=gevent` 参数，不支持默认 `prefork` 池：
```
celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info --pool=gevent
```

### 数据目录同步

数据目录配置在 `/catalogs` 页面管理，同步通过以下方式触发：

**自动同步**：Celery Beat 每日 18:00 执行 `daily_incremental_sync`，自动同步所有启用的目录。

**手动同步**（CLI）：
```
python -m tzdata_pkg.cli.sync_catalogs list                                    # 列出目录
python -m tzdata_pkg.cli.sync_catalogs sync --id 1 --mode incremental          # 增量同步
python -m tzdata_pkg.cli.sync_catalogs sync --id 1 --mode full --start 2025-01-01 --end 2026-05-15  # 全量同步
python -m tzdata_pkg.cli.sync_catalogs sync-all --mode incremental             # 同步所有启用目录
```

### Docker 文件说明

- `start.bat.docker.backup` 是旧的 Docker 版本备份，包含已废弃的 Docker 命令，可安全删除
- 本项目无 `docker-compose.yml` 或 `Dockerfile`，已完全移除 Docker 依赖

### bat 脚本编码

所有 `.bat` 脚本使用 **UTF-8 with BOM** 编码，首行包含 `chcp 65001 >NUL`（切换控制台代码页为 UTF-8）。Windows 重定向使用 `>NUL 2>&1`，禁止使用 `/dev/null`。编辑后务必保持此编码格式，否则 PowerShell 下中文会乱码。

### 与 tz2.0 的关系

- tz-data 是数据层，独立运行在端口 8000/3000
- tz2.0（`C:\myspace\tz2.0`）是上层应用，依赖 tz-data 的数据
- tz2.0 通过 Python import (`tzdata_pkg`) 和直接读取 SQLite 文件 (`bills.db`, `cffex.db`) 依赖 tz-data
- tz2.0 **不通过 HTTP 调用** tz-data API
- 启动 tz2.0 前，确保 tz-data 的数据库文件存在且数据完整

---

## 前端金额格式化规范

**所有前端页面显示金额类型数据，必须使用千分位格式（`1,234,567.89`），禁止直接使用 `.toFixed()` 显示金额。**

### 实现方式

- 统一使用 `frontend/src/utils/format.js` 中的工具函数
- 金额格式化：`formatMoney(value)` — 千分位 + 万/亿缩写（`123.45 万`）
- 完整金额：`formatMoneyFull(value)` — 千分位不缩写（`1,234,567.89`）
- 通用数字：`formatNumber(value, decimals)` — 千分位格式化工具
- 盈亏显示：`formatPnl(value)` — 带正负号的千分位金额

### 使用示例

```vue
<!-- 模板中 -->
{{ formatMoney(record.amount) }} 元

<!-- 表格列 formatter -->
{ title: '盈亏', key: 'pnl', formatter: v => formatMoney(v) + ' 元' }

<!-- ECharts tooltip -->
formatter: (p) => `盈亏: ${formatMoney(p.value)} 元`
```

### 导入方式

```javascript
import { formatMoney, formatNumber, formatPnl } from '../utils/format'
```

### 不需要格式化的场景

- 百分比数据（`.toFixed(1) + '%'` 可保留）
- 交易笔数/手数等整数计数
- 比率值（如盈亏比、夏普比率等）
