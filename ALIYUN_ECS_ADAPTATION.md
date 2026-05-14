# 阿里 ECS Windows 环境适配说明

**日期**: 2026-05-11
**环境**: 阿里 ECS Windows Server
**状态**: 已完成适配

---

## 主要变更

### 1. 移除 Docker 依赖

**原因**: 阿里 ECS Windows 环境不支持 Docker Desktop

**变更内容**:
- 移除所有 Docker 容器启动代码
- 移除 Redis/PostgreSQL/QuestDB 的 Docker 启动命令
- 改为使用 SQLite 数据库（无需额外安装）
- 添加数据库文件检查功能

### 2. 数据库架构调整

#### 原方案（需要 Docker）
```
Docker Containers:
  - Redis (端口 6379)
  - PostgreSQL (端口 5432)
  - QuestDB (端口 8812)
```

#### 新方案（无 Docker）
```
SQLite 数据库文件:
  - tzdata_market.db (市场数据)
  - tzdata_trading.db (交易数据)
  - tzdata_analysis.db (分析数据)
```

**优势**:
- 无需安装任何数据库服务
- 零配置，开箱即用
- 适合中小规模数据
- 易于备份和迁移

---

## 启动脚本变更

### start.bat v2.0（无 Docker 版）

**菜单选项变化**:

| 选项 | 旧版本（Docker） | 新版本（无 Docker） |
|------|-----------------|-------------------|
| 1 | 启动所有服务（含基础设施） | 启动所有服务（后端 + 前端） |
| 2 | 启动基础设施 | **检查数据库状态** |
| 3 | 启动后端服务 | 启动后端服务 |
| 4 | 启动前端服务 | 启动前端服务 |
| 5 | 停止所有服务 | 停止所有服务 |
| 6 | 检查服务状态 | 检查服务状态（含数据库文件） |
| 7 | 查看日志 | 查看日志 |
| 8 | 退出 | 退出 |

**新增功能**:
- `check_databases` - 检查 SQLite 数据库文件是否存在
- 首次运行时会自动创建数据库文件
- `check_status` 中显示数据库文件状态

---

## 服务架构对比

### 原架构（Docker）

```
用户浏览器
  http://localhost:5000
    |
    v
前端 (Vite + Vue3) Port: 5000
    |
    | API 请求
    v
后端 (FastAPI + Uvicorn) Port: 8000
    |
    +-- Celery 任务      +-- 数据库操作
    |                    |
    v                    v
  Celery Worker        Docker Containers
                           |
                  +--------+--------+
                  |        |        |
                Redis     PG     QuestDB
```

### 新架构（无 Docker）

```
用户浏览器
  http://localhost:3000
    |
    v
前端 (Vite + Vue3) Port: 3000
    |
    | API 请求
    v
后端 (FastAPI + Uvicorn) Port: 8000
    |
    +-- Celery 任务      +-- 数据库操作
    |                    |
    v                    v
  Celery Worker        SQLite Databases
                           |
                  +--------+--------+
                  |        |        |
             market.db  trad.db  analysis.db
```

---

## 使用方法

### 快速启动

```bash
# 方式 1: 一键启动
.\quick-start.bat

# 方式 2: 主启动器
.\start.bat
# 选择选项 1 - 启动所有服务
```

### 检查数据库状态

```bash
.\start.bat
# 选择选项 2 - 检查数据库状态
```

输出示例:
```
=== 检查数据库状态 ===

检查 SQLite 数据库...
[OK] tzdata_market.db 存在
[OK] tzdata_trading.db 存在
[OK] tzdata_analysis.db 存在

提示: 本项目使用 SQLite 数据库，无需额外安装
      数据库文件将在首次使用时自动创建
```

### 查看服务状态

```bash
.\start.bat
# 选择选项 6 - 检查服务状态
```

输出示例:
```
=== 服务状态检查 ===

后端进程:
  python.exe    12345  Celery Worker
  uvicorn.exe   12346  FastAPI Backend

前端进程:
  node.exe      12347  Frontend Dev Server

端口占用情况:
  后端端口 8000: 已占用
  前端端口 3000: 已占用

数据库文件:
  [OK] tzdata_market.db
  [OK] tzdata_trading.db
  [OK] tzdata_analysis.db
```

---

## 常见问题

### Q1: 没有 Redis，Celery 能正常工作吗？

**A**: Celery 配置为使用 Redis 作为 broker（`.env` 中 `CELERY_BROKER_URL=redis://localhost:6379/0`）。如果没有安装 Redis，Celery Worker 无法启动，但后端 FastAPI 服务仍然可以正常运行。如需 Celery 功能：
- 安装本地 Redis for Windows（如 Memurai）
- 或使用 RabbitMQ for Windows

### Q2: SQLite 性能如何？

**A**:
- 适合中小规模数据（百万级记录）
- 支持并发读取
- WAL 模式提升写入性能
- 不适合高并发写入场景

### Q3: 如何备份数据库？

**A**: 直接复制 `.db` 文件即可
```bash
# 备份所有数据库
xcopy data\*.db backup\ /Y

# 恢复数据
xcopy backup\*.db data\ /Y
```

### Q4: 如果以后需要 PostgreSQL/QuestDB 怎么办？

**A**: 可以手动安装：
1. 下载 Windows 版本的 PostgreSQL/QuestDB
2. 安装并启动服务
3. 修改 `.env` 配置文件
4. 更新代码中的数据库连接

---

## 技术细节

### SQLite 配置

项目使用优化后的 SQLite 配置：

```python
PRAGMA journal_mode=WAL          # Write-Ahead Logging
PRAGMA foreign_keys=ON           # 外键约束
PRAGMA busy_timeout=5000         # 忙等待超时 5 秒
PRAGMA cache_size=-64000         # 64MB 缓存
```

### 数据库文件位置

```
C:\myspace\tz-data\data\
├── tzdata_market.db      # 市场数据（行情、合约等）
├── tzdata_trading.db     # 交易数据（账户、账单等）
└── tzdata_analysis.db    # 分析数据（监控、健康快照等）
```

### 自动初始化

首次运行时，系统会自动：
1. 检查数据库文件是否存在
2. 如不存在，创建空的数据库文件
3. 执行 schema SQL 创建表结构
4. 初始化必要的索引

---

## 验证清单

启动后请验证：

- [ ] `start.bat` 能正常显示中文菜单
- [ ] 选项 2 能正确检查数据库状态
- [ ] 后端服务能正常启动（FastAPI + Celery）
- [ ] 前端服务能正常启动（Vite）
- [ ] 浏览器能访问 http://localhost:3000
- [ ] 浏览器能访问 http://localhost:8000/docs
- [ ] 数据库文件在首次使用后自动创建

---

## 总结

**完成时间**: 2026-05-11
**适配环境**: 阿里 ECS Windows Server
**主要变更**: 移除 Docker 依赖，改用 SQLite
**优势**: 零配置、易部署、易维护

**重要提示**:
- 本项目默认使用 SQLite，无需安装任何数据库服务
- 如需更高性能，可手动安装 Redis/PostgreSQL/QuestDB
- 数据库文件位于 `data/` 目录，定期备份
