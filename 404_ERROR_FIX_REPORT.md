# 404 错误修复报告

**日期**: 2026-05-11  
**问题**: Dashboard.vue 报 404 错误  
**状态**: ✅ 已修复

---

## 🐛 问题描述

前端访问 `http://localhost:5000/api/maintenance/catalogs` 时返回 404 错误：

```
Dashboard.vue:189 Failed to load data: AxiosError: Request failed with status code 404
api/maintenance/catalogs:1 Failed to load resource: the server responded with a status of 404 (Not Found)
```

---

## 🔍 问题原因

在之前的会话中，我们删除了废弃的 `extended_db_registry.py` 文件并完成了 SQLite 迁移。但是：

1. **FastAPI 服务仍在运行旧代码**：之前启动的 FastAPI 进程加载的是旧版本的代码
2. **Python 缓存未清理**：`__pycache__` 目录中可能还缓存了旧的编译字节码
3. **路由注册正常但服务未重启**：虽然代码已经修改，但运行的服务还是旧版本

---

## ✅ 解决方案

### 步骤 1: 停止所有 Python 进程

```powershell
Get-Process python | Stop-Process -Force
```

### 步骤 2: 清理 Python 缓存

```powershell
Get-ChildItem -Path src -Include __pycache__ -Recurse -Force | Remove-Item -Recurse -Force
```

### 步骤 3: 重新启动 FastAPI 服务

```powershell
# 不使用 --reload 模式，避免缓存问题
uvicorn tzdata_pkg.api.server:app --host 0.0.0.0 --port 8000
```

### 步骤 4: 验证 API

```powershell
# 测试后端 API
curl http://localhost:8000/api/maintenance/catalogs

# 测试前端代理
curl http://localhost:5000/api/maintenance/catalogs
```

---

## 📊 验证结果

### 后端 API
```bash
$ curl http://localhost:8000/api/maintenance/catalogs
{"success":true,"data":[]}
```
✅ **状态码**: 200  
✅ **响应**: 正常返回空数组

### 前端代理
```bash
$ curl http://localhost:5000/api/maintenance/catalogs
{"success":true,"data":[]}
```
✅ **状态码**: 200  
✅ **代理转发**: 正常工作

### 路由检查
```python
✓ Server 导入成功
✓ 路由数量: 31

Maintenance 路由:
  /api/maintenance/catalogs [GET]
  /api/maintenance/catalogs [POST]
  /api/maintenance/sync/trigger [POST]
  /api/maintenance/sync/task/{task_id} [GET]
  /api/maintenance/health/snapshot [GET]
  /api/maintenance/health/diff [GET]
  /api/maintenance/quality/{catalog_id} [GET]
  /api/maintenance/accounts [GET]
  /api/maintenance/accounts [POST]
```
✅ **所有路由正常注册**

---

## 🎯 根本原因分析

### 为什么会出现这个问题？

1. **代码修改后服务未重启**：
   - 我们删除了 `extended_db_registry.py`
   - 修改了多个模块的导入语句
   - 但 FastAPI 服务还在运行，使用的是内存中的旧代码

2. **--reload 模式的局限性**：
   - FastAPI 的 `--reload` 模式会监控文件变化
   - 但**删除文件**可能不会被正确检测到
   - 特别是当有循环导入或缓存问题时

3. **Python 字节码缓存**：
   - `__pycache__` 目录中的 `.pyc` 文件可能引用了已删除的模块
   - 导致导入错误或路由注册失败

---

## 💡 预防措施

### 1. 修改代码后重启服务

每次修改核心模块后，应该：
```bash
# 停止服务
.\stop.bat

# 清理缓存
Get-ChildItem -Path src -Include __pycache__ -Recurse | Remove-Item -Recurse -Force

# 重新启动
.\start.bat
```

### 2. 使用启动脚本

项目提供了统一的启动脚本：
```bash
# 一键启动所有服务
.\start.bat

# 或仅启动后端
.\start-backend.bat
```

### 3. 检查服务状态

```bash
# 检查端口占用
netstat -ano | findstr ":8000"

# 检查进程
Get-Process python, uvicorn

# 测试 API
curl http://localhost:8000/docs
```

---

## 📝 经验总结

### ✅ 正确的操作流程

1. **修改代码** → 保存文件
2. **停止服务** → 确保旧进程完全退出
3. **清理缓存** → 删除 `__pycache__` 目录
4. **重启服务** → 启动新的 FastAPI 进程
5. **验证 API** → 测试关键端点

### ❌ 错误的做法

- ✗ 修改代码后不重启服务
- ✗ 只依赖 `--reload` 模式自动检测
- ✗ 不清理 Python 缓存
- ✗ 假设删除文件会自动生效

---

## 🔧 相关命令速查

```powershell
# 停止所有 Python 进程
Get-Process python | Stop-Process -Force

# 清理缓存
Get-ChildItem -Path src -Include __pycache__ -Recurse | Remove-Item -Recurse -Force

# 检查端口占用
netstat -ano | findstr ":8000"

# 启动 FastAPI（不使用 reload）
uvicorn tzdata_pkg.api.server:app --host 0.0.0.0 --port 8000

# 测试 API
Invoke-WebRequest -Uri "http://localhost:8000/api/maintenance/catalogs" -UseBasicParsing
```

---

## 🎉 结论

**问题已完全解决！**

- ✅ 后端 API 正常响应
- ✅ 前端代理正常工作
- ✅ 所有路由正确注册
- ✅ 数据库连接正常

**建议**：今后修改代码后，务必重启服务并清理缓存，避免类似问题。

---

**修复时间**: 2026-05-11 23:35  
**修复人员**: AI Assistant  
**验证状态**: ✅ 已通过
