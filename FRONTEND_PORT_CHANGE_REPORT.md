# 前端端口变更报告（3000 → 5000）✅

**日期**: 2026-05-11  
**变更**: 前端开发服务器端口从 3000 改为 5000  
**状态**: ✅ 已完成

---

## 📋 修改清单

### 1️⃣ **启动脚本**（start.bat）

**文件**: `c:\myspace\tz-data\start.bat`

```batch
REM 端口配置
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5000"  ← 从 3000 改为 5000
```

### 2️⃣ **Vite 配置**（vite.config.js）

**文件**: `c:\myspace\tz-data\frontend\vite.config.js`

```javascript
server: {
  port: 5000,  ← 从 3000 改为 5000
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
},
```

### 3️⃣ **环境配置**（.env）

**文件**: `c:\myspace\tz-data\.env` 和 `.env.example`

```ini
# Vite Dev Server
VITE_PORT=5000  ← 从 3000 改为 5000
VITE_API_BASE_URL=http://localhost:8000/api/maintenance
```

### 4️⃣ **文档更新**

已更新以下文档中的所有端口引用：

- ✅ CHEATSHEET.md
- ✅ ALIYUN_ECS_ADAPTATION.md
- ✅ ADAPTATION_COMPLETION_REPORT.md
- ✅ QUICK_START_GUIDE.md
- ✅ STARTUP_SCRIPTS_GUIDE.md
- ✅ PORT_CONFIGURATION.md
- ✅ STARTUP_SYSTEM_SUMMARY.md
- ✅ 其他所有 .md 文档

---

## 🔗 访问地址变更

| 服务 | 旧地址 | 新地址 |
|------|--------|--------|
| **前端界面** | http://localhost:3000 | **http://localhost:5000** ⭐ |
| **API 文档** | http://localhost:8000/docs | http://localhost:8000/docs（不变） |
| **QuestDB Console** | http://localhost:8812 | http://localhost:8812（不变） |

---

## 🚀 使用方法

### 启动前端服务

```bash
# 方式 1: 使用启动脚本
.\start.bat
# 选择选项 1 或 4

# 方式 2: 直接启动
cd frontend
npm run dev
```

### 访问前端

浏览器打开：**http://localhost:5000**

---

## ⚠️ 注意事项

### 1. 端口冲突检查

如果端口 5000 已被占用，启动时会提示错误。

**检查端口占用**:
```bash
netstat -ano | findstr ":5000"
```

**终止占用进程**:
```bash
taskkill /F /PID <PID>
```

### 2. 防火墙设置

确保 Windows 防火墙允许端口 5000 的入站连接（如果需要远程访问）。

### 3. 代理配置

Vite 的代理配置保持不变，仍然将 `/api` 请求转发到后端 8000 端口：

```javascript
proxy: {
  '/api': {
    target: 'http://localhost:8000',  // 后端端口不变
    changeOrigin: true,
  },
}
```

---

## 📊 端口分配总览

| 服务 | 端口 | 协议 | 说明 |
|------|------|------|------|
| **FastAPI** | 8000 | HTTP | 后端 API 服务 |
| **Vite Dev Server** | **5000** | HTTP | **前端开发服务器** ⭐ |
| **Redis** | 6379 | TCP | 缓存（可选） |
| **PostgreSQL** | 5432 | TCP | 数据库（可选） |
| **QuestDB** | 8812 | HTTP/TCP | 时序数据库（可选） |

---

## ✅ 验证清单

启动后请验证：

- [ ] `start.bat` 显示前端端口为 5000
- [ ] Vite 启动时显示 "Local: http://localhost:5000"
- [ ] 浏览器能访问 http://localhost:5000
- [ ] 前端页面正常显示 Dashboard
- [ ] API 请求正常（代理到 8000 端口）
- [ ] 无端口冲突错误

---

## 💡 为什么选择 5000？

**常见原因**:
1. **避免冲突**: 3000 端口可能被其他应用占用（如 React、Next.js 默认端口）
2. **统一规范**: 某些团队偏好使用 5000 作为前端开发端口
3. **易于记忆**: 5000 是整数，便于记忆

**其他常用前端端口**:
- 3000 - React/Next.js 默认
- 5000 - Flask/Django 默认（Python 生态）
- 8080 - Java/Tomcat 常用
- 8000 - Django 默认

---

## 🎉 总结

✅ **完成时间**: 2026-05-11  
✅ **影响范围**: 启动脚本、Vite 配置、环境配置、所有文档  
✅ **向后兼容**: 需要更新书签和快捷方式  

**重要提示**: 
- 前端访问地址已变更为 **http://localhost:5000**
- 后端 API 端口保持 8000 不变
- 所有文档已同步更新

---

**端口变更完成！** 🚀
