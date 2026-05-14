# 前端代理配置错误修复报告

**日期**: 2026-05-12  
**问题**: 前端访问 API 时返回 500 Internal Server Error  
**状态**: ✅ 已修复

---

## 🐛 问题描述

前端运行在端口 **5101**，访问 `http://localhost:5101/api/maintenance/catalogs` 时返回：

```
GET http://localhost:5101/api/maintenance/catalogs 500 (Internal Server Error)
Dashboard.vue:189 Failed to load data: AxiosError: Request failed with status code 500
```

---

## 🔍 问题原因

### 根本原因：Vite 代理配置错误 + start.bat 端口配置错误

#### 1. Vite 代理配置错误

检查 [vite.config.js](file://c:\myspace\tz-data\frontend\vite.config.js) 发现：

```javascript
server: {
  port: 5100,
  proxy: {
    '/api': {
      target: 'http://localhost:8100',  // ❌ 错误的端口
      changeOrigin: true,
    },
  },
},
```

**问题分析**：
- **前端实际运行端口**: 5101（5100 被占用后自动递增）
- **代理目标端口**: 8100（配置错误）
- **后端实际运行端口**: 8000

当前端通过代理转发请求时：
```
浏览器 → localhost:5101/api/... 
  → Vite Proxy → localhost:8100/api/... (❌ 连接失败，后端在 8000)
```

#### 2. start.bat 端口配置错误

[start.bat](file://c:\myspace\tz-data\start.bat) 中也配置了错误的端口：

```batch
REM 端口配置（与 tz2.0 项目分离）
set "BACKEND_PORT=8100"  ← ❌ 应该是 8000
set "FRONTEND_PORT=5100"
```

---

## ✅ 解决方案

### 步骤 1: 修正 Vite 代理配置

修改 `frontend/vite.config.js`：

```javascript
server: {
  port: 5100,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',  // ✅ 修正为正确的后端端口
      changeOrigin: true,
    },
  },
},
```

### 步骤 2: 修正 start.bat 端口配置

修改 `start.bat`：

```batch
REM 端口配置（与 tz2.0 项目分离）
set "BACKEND_PORT=8000"  ← ✅ 修正为 8000
set "FRONTEND_PORT=5100"
```

### 步骤 3: 重启前端服务

由于修改了 Vite 配置，需要重启前端开发服务器：

```bash
cd frontend
npm run dev
```

或者使用启动脚本：

```cmd
start.bat
# 选择选项 4: 启动前端服务
```

### 步骤 4: 验证修复

```bash
# 测试前端代理
$ curl http://localhost:5100/api/maintenance/catalogs
{"success":true,"data":[]}

# 状态码: 200 ✅
```

---

## 📊 端口配置总览

| 服务 | 配置端口 | 实际端口 | 说明 |
|------|---------|---------|------|
| **后端 (FastAPI)** | 8000 | 8000 | ✅ 正确 |
| **前端 (Vite)** | 5100 | 5101 | ⚠️ 5100 被占用，自动递增 |
| **前端代理目标** | ~~8100~~ → 8000 | - | ✅ 已修复 |
| **start.bat BACKEND_PORT** | ~~8100~~ → 8000 | - | ✅ 已修复 |

---

## 🔧 修复的文件

1. [frontend/vite.config.js](file://c:\myspace\tz-data\frontend\vite.config.js)
   - 代理目标：`http://localhost:8100` → `http://localhost:8000`

2. [start.bat](file://c:\myspace\tz-data\start.bat)
   - BACKEND_PORT：`8100` → `8000`

---

## 💡 最佳实践建议

### 1. 统一端口配置

建议在项目根目录创建 `.env` 文件统一管理端口：

```env
# Backend
BACKEND_PORT=8000

# Frontend
FRONTEND_PORT=5100
```

然后在 `vite.config.js` 中读取：

```javascript
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    server: {
      port: parseInt(env.FRONTEND_PORT) || 5100,
      proxy: {
        '/api': {
          target: `http://localhost:${env.BACKEND_PORT || 8000}`,
          changeOrigin: true,
        },
      },
    },
  }
})
```

### 2. 避免端口冲突

如果前端端口 5100 被占用，Vite 会自动尝试 5101、5102 等。

**建议**：
- 确保没有其他服务占用 5100 端口
- 或者明确指定一个不常用的端口（如 5173、3000 等）

### 3. 使用 start.bat 统一管理

[start.bat](file://c:\myspace\tz-data\start.bat) 已经配置了正确的端口（现已修正为 8000）。

建议使用它来管理服务，而不是手动启动：

```cmd
cd C:\myspace\tz-data
start.bat
```

然后选择：
- **选项 3**: 启动后端服务（FastAPI + Celery）
- **选项 4**: 启动前端服务（Vite Dev Server）

---

## ✅ 验证清单

- [x] 修正 vite.config.js 代理目标端口（8100 → 8000）
- [x] 修正 start.bat BACKEND_PORT（8100 → 8000）
- [x] 重启前端服务
- [x] 验证前端代理正常工作
- [x] 确认后端服务运行在 8000 端口

---

## 📝 相关文档

- [ALERT_API_404_FIX.md](file://c:\myspace\tz-data\ALERT_API_404_FIX.md) - 告警 API 404 错误修复
- [BATCH_FILE_ENCODING_FIX.md](file://c:\myspace\tz-data\BATCH_FILE_ENCODING_FIX.md) - 批处理文件编码修复
- [BATCH_ENCODING_QUICKFIX.md](file://c:\myspace\tz-data\BATCH_ENCODING_QUICKFIX.md) - 编码问题快速修复指南

---

**修复完成时间**: 2026-05-12  
**修复人员**: AI Assistant  
**验证状态**: ✅ 已通过测试
