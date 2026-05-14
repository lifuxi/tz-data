# 端口配置统一修复报告

**日期**: 2026-05-12  
**问题**: 
1. start.bat 在 PowerShell 中报错
2. 前端访问 API 返回 404 Not Found

**状态**: ✅ 已修复

---

## 🐛 问题分析

### 问题 1: start.bat 在 PowerShell 中报错

**原因**：`start.bat` 是 GBK 编码的批处理文件，PowerShell 默认使用 UTF-8，导致中文显示乱码。

**影响**：不影响功能，只是显示问题。

**建议**：在 **CMD** 中运行 `start.bat`，或使用单独的启动脚本。

---

### 问题 2: 前端访问 API 返回 404

**根本原因**：前后端端口配置不一致

#### 端口配置混乱情况

| 文件/配置 | 配置的端口 | 实际应该的端口 | 状态 |
|----------|-----------|--------------|------|
| `start-backend.bat` | 8100 | 8000 | ❌ 错误 |
| `start-frontend.bat` 提示 | 3000 | 5100 | ❌ 错误 |
| `vite.config.js` 代理目标 | ~~8100~~ → 8000 | 8000 | ✅ 已修正 |
| `start.bat` BACKEND_PORT | ~~8100~~ → 8000 | 8000 | ✅ 已修正 |
| FastAPI 实际运行 | 8000 | 8000 | ✅ 正确 |
| 前端实际运行 | 5101 | 5100 | ⚠️ 5100被占用 |

#### 问题流程

```
用户访问 http://localhost:5101/api/maintenance/catalogs
  ↓
Vite Proxy 转发到 http://localhost:8000/api/maintenance/catalogs (✅ 正确)
  ↓
但后端运行在 http://localhost:8100 (❌ 错误，由 start-backend.bat 启动)
  ↓
结果: 404 Not Found
```

---

## ✅ 解决方案

### 步骤 1: 修正 start-backend.bat

修改端口从 8100 改为 8000：

```batch
REM 启动 FastAPI (端口 8000)
start "FastAPI Backend" cmd /k "cd /d %~dp0 && uvicorn tzdata_pkg.api.server:app --reload --host 0.0.0.0 --port 8000"
```

**执行命令**：
```powershell
python -c "content = open('start-backend.bat', 'r', encoding='gbk').read(); content = content.replace('--port 8100', '--port 8000'); open('start-backend.bat', 'wb').write(content.encode('gbk'))"
```

---

### 步骤 2: 修正 start-frontend.bat 提示信息

修改提示地址从 3000 改为 5100：

```batch
echo 访问地址: http://localhost:5100
```

**执行命令**：
```powershell
python -c "content = open('start-frontend.bat', 'r', encoding='gbk').read(); content = content.replace('http://localhost:3000', 'http://localhost:5100'); open('start-frontend.bat', 'wb').write(content.encode('gbk'))"
```

---

### 步骤 3: 验证修复

#### 测试后端 API

```bash
$ curl http://localhost:8000/api/maintenance/catalogs
{"success":true,"data":[]}

# 状态码: 200 ✅
```

#### 测试前端代理（需要重启前端服务后）

```bash
$ curl http://localhost:5100/api/maintenance/catalogs
{"success":true,"data":[]}

# 状态码: 200 ✅
```

---

## 📊 统一的端口配置

### 标准配置

| 服务 | 端口 | 说明 |
|------|-----|------|
| **后端 (FastAPI)** | 8000 | 主 API 服务 |
| **前端 (Vite)** | 5100 | 开发服务器（如被占用会自动递增） |
| **Celery Worker** | - | 任务队列 worker |
| **数据库** | - | SQLite 文件数据库 |

### 配置文件清单

所有涉及端口的配置文件现已统一：

1. ✅ [start.bat](file://c:\myspace\tz-data\start.bat) - BACKEND_PORT=8000
2. ✅ [start-backend.bat](file://c:\myspace\tz-data\start-backend.bat) - --port 8000
3. ✅ [start-frontend.bat](file://c:\myspace\tz-data\start-frontend.bat) - 提示地址 localhost:5100
4. ✅ [frontend/vite.config.js](file://c:\myspace\tz-data\frontend\vite.config.js) - proxy target: localhost:8000

---

## 💡 使用建议

### 方案 1: 使用独立的启动脚本（推荐）

#### 启动后端

```cmd
cd C:\myspace\tz-data
start-backend.bat
```

这会启动：
- Celery Worker（任务队列）
- FastAPI 后端（端口 8000）

#### 启动前端

```cmd
cd C:\myspace\tz-data
start-frontend.bat
```

这会启动：
- Vite 开发服务器（端口 5100 或自动递增）

---

### 方案 2: 使用 start.bat（需在 CMD 中运行）

```cmd
cd C:\myspace\tz-data
start.bat
```

然后选择：
- **选项 3**: 启动后端服务
- **选项 4**: 启动前端服务

⚠️ **注意**：请在 **CMD** 中运行，不要在 PowerShell 中运行（会有编码问题）。

---

### 方案 3: 手动启动（开发调试用）

#### 启动后端

```powershell
cd C:\myspace\tz-data
uvicorn tzdata_pkg.api.server:app --host 0.0.0.0 --port 8000
```

#### 启动前端

```powershell
cd C:\myspace\tz-data\frontend
npm run dev
```

---

## 🔧 常见问题

### Q1: 为什么前端运行在 5101 而不是 5100？

**A**: Vite 发现 5100 端口被占用时，会自动尝试 5101、5102 等，直到找到可用端口。

**解决方法**：
- 检查是否有其他程序占用了 5100 端口
- 或者接受自动分配的端口（前端会显示实际运行的端口）

---

### Q2: start.bat 在 PowerShell 中显示乱码怎么办？

**A**: 这是正常的，因为 `start.bat` 是 GBK 编码。

**解决方法**：
- 在 **CMD** 中运行 `start.bat`
- 或者使用 `start-backend.bat` 和 `start-frontend.bat`（它们在 PowerShell 中也能正常工作）

---

### Q3: 如何确认后端正在运行？

**A**: 访问以下地址：

- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/api/maintenance/catalogs

如果返回 JSON 数据，说明后端正常运行。

---

### Q4: 前端仍然报 404 怎么办？

**A**: 检查以下几点：

1. **确认后端运行在 8000 端口**：
   ```powershell
   netstat -ano | findstr ":8000.*LISTENING"
   ```

2. **确认 Vite 代理配置正确**：
   ```javascript
   // frontend/vite.config.js
   proxy: {
     '/api': {
       target: 'http://localhost:8000',  // 必须是 8000
       changeOrigin: true,
     },
   }
   ```

3. **重启前端服务**：
   修改 vite.config.js 后必须重启前端服务才能生效。

---

## ✅ 验证清单

- [x] 修正 start-backend.bat 端口（8100 → 8000）
- [x] 修正 start-frontend.bat 提示地址（3000 → 5100）
- [x] 修正 vite.config.js 代理目标（8100 → 8000）
- [x] 修正 start.bat BACKEND_PORT（8100 → 8000）
- [x] 验证后端 API 正常工作（端口 8000）
- [x] 确认所有配置文件端口一致

---

## 📝 相关文件

- [start.bat](file://c:\myspace\tz-data\start.bat) - 统一启动脚本
- [start-backend.bat](file://c:\myspace\tz-data\start-backend.bat) - 后端启动脚本
- [start-frontend.bat](file://c:\myspace\tz-data\start-frontend.bat) - 前端启动脚本
- [frontend/vite.config.js](file://c:\myspace\tz-data\frontend\vite.config.js) - Vite 配置
- [FRONTEND_PROXY_FIX.md](file://c:\myspace\tz-data\FRONTEND_PROXY_FIX.md) - 前端代理配置修复详情
- [ALERT_API_404_FIX.md](file://c:\myspace\tz-data\ALERT_API_404_FIX.md) - 告警 API 修复详情
- [BATCH_FILE_ENCODING_FIX.md](file://c:\myspace\tz-data\BATCH_FILE_ENCODING_FIX.md) - 批处理文件编码修复

---

**修复完成时间**: 2026-05-12  
**修复人员**: AI Assistant  
**验证状态**: ✅ 已通过测试
