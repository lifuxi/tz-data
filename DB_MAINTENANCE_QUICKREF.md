# 🚀 数据库维护快速参考

---

## 💾 备份数据库

### 最简单的方式
```bash
.\backup-databases.bat
```

### Python 方式（更多功能）
```bash
# 备份（压缩）
python scripts\backup_databases.py --action backup

# 查看备份列表
python scripts\backup_databases.py --action list

# 恢复数据库
python scripts\backup_databases.py --action restore --db tzdata_market.db
```

---

## ⚡ 优化数据库

### 最简单的方式
```bash
.\optimize-databases.bat
```

### Python 方式
```bash
python scripts\optimize_sqlite.py
```

---

## 📊 当前状态

| 项目 | 状态 |
|------|------|
| WAL 模式 | ✅ 已启用 |
| 缓存大小 | 64 MB |
| 同步级别 | NORMAL |
| 临时存储 | MEMORY |
| 最新备份 | `backups/` 目录 |
| 节省空间 | ~23 MB |

---

## 🔧 常用命令

```bash
# 查看所有备份
dir backups

# 检查数据库完整性
python -c "import sqlite3; conn = sqlite3.connect('data/tzdata_market.db'); print(conn.execute('PRAGMA integrity_check;').fetchone())"

# 查看数据库大小
dir data\*.db

# 停止所有服务（备份前建议执行）
.\stop.bat

# 启动所有服务
.\start.bat
```

---

## ⏰ 自动化设置

### Windows 任务计划程序

**每日备份**（凌晨 2:00）:
- 程序: `C:\myspace\tz-data\backup-databases.bat`
- 触发器: 每天 02:00

**每周优化**（周日凌晨 3:00）:
- 程序: `C:\myspace\tz-data\optimize-databases.bat`
- 触发器: 每周日 03:00

---

## 🆘 紧急恢复

```bash
# 1. 停止服务
.\stop.bat

# 2. 列出备份
python scripts\backup_databases.py --action list

# 3. 恢复数据库
python scripts\backup_databases.py --action restore --db tzdata_market.db

# 4. 验证完整性
python -c "import sqlite3; conn = sqlite3.connect('data/tzdata_market.db'); print(conn.execute('PRAGMA integrity_check;').fetchone())"

# 5. 重启服务
.\start.bat
```

---

## 📁 重要文件

| 文件 | 用途 |
|------|------|
| `backup-databases.bat` | 备份脚本 |
| `optimize-databases.bat` | 优化脚本 |
| `scripts/backup_databases.py` | Python 备份工具 |
| `scripts/optimize_sqlite.py` | Python 优化工具 |
| `DATABASE_BACKUP_GUIDE.md` | 详细指南 |
| `backups/` | 备份文件目录 |

---

## 💡 提示

- ✅ 建议每日备份
- ✅ 建议每周优化
- ✅ 定期测试恢复流程
- ✅ 保留至少 7 天的备份
- ✅ 监控磁盘空间（至少 20% 空闲）

---

**最后更新**: 2026-05-11
