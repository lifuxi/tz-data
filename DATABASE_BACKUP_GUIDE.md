# 数据库备份与优化指南

**日期**: 2026-05-11  
**状态**: ✅ 已完成配置

---

## 📋 目录

1. [数据库备份](#数据库备份)
2. [SQLite 性能优化](#sqlite-性能优化)
3. [自动化建议](#自动化建议)
4. [故障恢复](#故障恢复)

---

## 数据库备份

### 🛠️ 备份工具

项目提供了两种备份方式：

#### 方式 1: Windows 批处理脚本（推荐）

```bash
# 双击运行或命令行执行
.\backup-databases.bat
```

**特点**：
- ✅ 简单易用，无需 Python 环境
- ✅ 自动创建带时间戳的备份
- ✅ 自动清理 7 天前的旧备份
- ✅ 彩色输出，清晰易读

**备份文件命名**：
```
backups/
├── tzdata_market.db.bak.20260511_232900.db
├── tzdata_trading.db.bak.20260511_232900.db
└── tzdata_analysis.db.bak.20260511_232900.db
```

#### 方式 2: Python 脚本（高级功能）

```bash
# 备份所有数据库（压缩）
python scripts\backup_databases.py --action backup

# 备份所有数据库（不压缩）
python scripts\backup_databases.py --action backup --no-compress

# 列出所有备份
python scripts\backup_databases.py --action list

# 恢复数据库
python scripts\backup_databases.py --action restore --db tzdata_market.db

# 清理旧备份
python scripts\backup_databases.py --action cleanup --retention-days 14
```

**特点**：
- ✅ 支持 gzip 压缩（节省 70-80% 空间）
- ✅ 灵活的恢复功能
- ✅ 可自定义保留天数
- ✅ 详细的日志记录

### 📅 定期备份建议

#### Windows 任务计划程序

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器：每天凌晨 2:00
4. 操作：启动程序 `C:\myspace\tz-data\backup-databases.bat`

#### 或使用 crontab（如果有 WSL）

```bash
# 编辑 crontab
crontab -e

# 添加每日备份任务（凌晨 2:00）
0 2 * * * /mnt/c/myspace/tz-data/backup-databases.bat
```

---

## SQLite 性能优化

### 🚀 已应用的优化

所有数据库已应用以下优化：

| 优化项 | 设置值 | 说明 |
|--------|--------|------|
| **WAL 模式** | ✅ 启用 | Write-Ahead Logging，提升并发性能 |
| **缓存大小** | 64 MB | 减少磁盘 I/O |
| **同步级别** | NORMAL | 平衡性能和安全性 |
| **临时存储** | MEMORY | 加快临时表操作 |
| **数据库分析** | ✅ 完成 | 优化查询计划 |
| **碎片清理** | ✅ 完成 | 回收空间（节省 ~23 MB） |

### 📊 优化效果

```
tzdata_market.db:    节省 19.29 MB
tzdata_trading.db:   节省 3.79 MB
tzdata_analysis.db:  无变化（已是最新）
----------------------------------------
总计节省:            ~23 MB
```

### 🔧 手动优化

```bash
# 方式 1: 使用批处理脚本（推荐）
.\optimize-databases.bat

# 方式 2: 使用 Python 脚本
python scripts\optimize_sqlite.py

# 方式 3: 优化指定数据库
python scripts\optimize_sqlite.py data\tzdata_market.db
```

### ⚙️ WAL 模式优势

**WAL (Write-Ahead Logging)** 是 SQLite 的高级日志模式：

✅ **读写不阻塞**：读者和 writer 可以并发访问  
✅ **更好的性能**：特别是写密集型场景  
✅ **崩溃安全**：数据一致性得到保证  
✅ **更快的提交**：减少了 fsync 调用  

**注意事项**：
- WAL 模式会产生 `-wal` 和 `-shm` 辅助文件
- 这些文件在数据库关闭时会自动清理
- 不要手动删除这些文件

---

## 自动化建议

### 🔄 推荐的自动化流程

#### 1. 每日备份 + 每周优化

```
每天 02:00 → 备份数据库
每周日 03:00 → 备份 + 优化
```

#### 2. 实现方案

创建 `maintenance-schedule.bat`：

```batch
@echo off
REM 维护调度脚本

set "DAY_OF_WEEK=%date:~0,3%"

echo 执行日常维护...
call backup-databases.bat

if "%DAY_OF_WEEK%"=="Sun" (
    echo.
    echo 执行周日深度维护...
    call optimize-databases.bat
)
```

然后在任务计划程序中设置为每天运行。

---

## 故障恢复

### 🆘 数据库损坏恢复步骤

#### 步骤 1: 停止所有服务

```bash
.\stop.bat
```

#### 步骤 2: 查找最新备份

```bash
# 列出所有备份
python scripts\backup_databases.py --action list
```

#### 步骤 3: 恢复数据库

```bash
# 恢复 market 数据库
python scripts\backup_databases.py --action restore --db tzdata_market.db

# 或指定备份文件
python scripts\backup_databases.py --action restore --db tzdata_market.db --file backups\tzdata_market.db.bak.20260511_232900.db.gz
```

#### 步骤 4: 验证恢复

```bash
# 检查数据库完整性
python -c "import sqlite3; conn = sqlite3.connect('data/tzdata_market.db'); print(conn.execute('PRAGMA integrity_check;').fetchone())"
```

应该输出：`('ok',)`

#### 步骤 5: 重启服务

```bash
.\start.bat
```

### 🔍 常见问题

#### Q1: 备份文件太大怎么办？

**A**: 使用压缩备份：
```bash
python scripts\backup_databases.py --action backup
# 默认启用 gzip 压缩，可节省 70-80% 空间
```

#### Q2: 如何减少备份频率？

**A**: 修改 `backup_databases.py` 中的 `retention_days` 参数，或在任务计划中调整触发器。

#### Q3: WAL 文件可以删除吗？

**A**: **不要手动删除**！WAL 文件会在数据库正常关闭时自动清理。如果数据库异常退出，下次打开时会自动恢复。

#### Q4: 优化会影响正在运行的服务吗？

**A**: 
- WAL 模式下，优化不会阻塞读写操作
- VACUUM 操作会锁定数据库，建议在低峰期执行
- 建议在凌晨执行优化任务

---

## 📁 相关文件

| 文件 | 用途 |
|------|------|
| `backup-databases.bat` | Windows 备份脚本（简单版） |
| `scripts/backup_databases.py` | Python 备份工具（完整版） |
| `optimize-databases.bat` | Windows 优化脚本 |
| `scripts/optimize_sqlite.py` | Python 优化工具 |
| `DATABASE_BACKUP_GUIDE.md` | 本文档 |

---

## 🎯 最佳实践总结

1. ✅ **每日备份**：至少每天备份一次
2. ✅ **定期优化**：每周或每月优化一次
3. ✅ **异地备份**：重要数据备份到云存储或外部硬盘
4. ✅ **测试恢复**：定期测试备份文件的恢复流程
5. ✅ **监控空间**：确保磁盘有足够空间（至少保留 20% 空闲）
6. ✅ **日志审查**：定期检查 `logs/backup.log` 和 `logs/app.log`

---

**最后更新**: 2026-05-11  
**维护人员**: AI Assistant
