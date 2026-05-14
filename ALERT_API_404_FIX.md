# 告警 API 404 错误修复报告

**日期**: 2026-05-12  
**问题**: Dashboard.vue 报 `/api/maintenance/alerts/recent` 404 错误  
**状态**: ✅ 已修复

---

## 🐛 问题描述

前端访问 `http://localhost:5000/api/maintenance/alerts/recent?limit=5` 时返回 404 错误：

```
api/maintenance/alerts/recent?limit=5:1 
Failed to load resource: the server responded with a status of 404 (Not Found)
Dashboard.vue:189 Failed to load data: AxiosError: Request failed with status code 404
```

---

## 🔍 问题原因

1. **后端缺少告警路由**：前端调用 `/api/maintenance/alerts/recent`，但后端 `maintenance.py` 路由文件中没有实现这个端点
2. **已有告警系统但未暴露 API**：项目中已经有完整的 `AlertManager` 类（在 `core/monitoring.py` 中），但没有通过 FastAPI 路由暴露出来

---

## ✅ 解决方案

### 步骤 1: 在 maintenance.py 中添加告警路由

在 `src/tzdata_pkg/api/routes/maintenance.py` 文件末尾添加两个新端点：

```python
# === Alert Management Endpoints ===

@router.get("/alerts")
def list_alerts(
    level: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    """List alerts with optional filters and pagination."""
    from tzdata_pkg.core.monitoring import get_alert_manager
    
    try:
        alert_manager = get_alert_manager()
        all_alerts = alert_manager.alert_history
        
        # Apply filters
        filtered = all_alerts
        if level:
            filtered = [a for a in filtered if a.get('level') == level]
        if category:
            filtered = [a for a in filtered if a.get('category') == category]
        
        # Sort by timestamp (newest first)
        filtered = sorted(filtered, key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Pagination
        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = filtered[start:end]
        
        return {
            "success": True,
            "data": paginated,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/recent")
def get_recent_alerts(limit: int = 50):
    """Get recent alerts."""
    from tzdata_pkg.core.monitoring import get_alert_manager
    
    try:
        alert_manager = get_alert_manager()
        recent = alert_manager.get_recent_alerts(limit=limit)
        
        return {
            "success": True,
            "data": recent
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 步骤 2: 重启后端服务

```powershell
# 停止所有 Python 进程
Get-Process python | Stop-Process -Force

# 清理缓存
Get-ChildItem -Path src -Include __pycache__ -Recurse -Force | Remove-Item -Recurse -Force

# 重新启动 FastAPI
uvicorn tzdata_pkg.api.server:app --host 0.0.0.0 --port 8000
```

### 步骤 3: 验证 API

```bash
$ curl http://localhost:8000/api/maintenance/alerts/recent?limit=5
{"success":true,"data":[]}
```

✅ 返回 200 状态码，API 正常工作！

---

## 📋 新增的 API 端点

### 1. GET /api/maintenance/alerts

**功能**：获取告警列表（支持过滤和分页）

**查询参数**：
- `level` (可选): 告警级别 (`info`, `warning`, `error`, `critical`)
- `category` (可选): 告警类别 (`system`, `sync`, `rule_trigger`, `exception`)
- `page` (可选): 页码，默认 1
- `page_size` (可选): 每页数量，默认 20

**响应示例**：
```json
{
  "success": true,
  "data": [
    {
      "timestamp": "2026-05-12T08:30:00",
      "title": "数据同步失败",
      "message": "IM2506 日线同步超时",
      "level": "error",
      "category": "sync",
      "extra_data": {}
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### 2. GET /api/maintenance/alerts/recent

**功能**：获取最近的告警

**查询参数**：
- `limit` (可选): 返回数量，默认 50

**响应示例**：
```json
{
  "success": true,
  "data": [
    {
      "timestamp": "2026-05-12T08:30:00",
      "title": "数据同步失败",
      "message": "IM2506 日线同步超时",
      "level": "error",
      "category": "sync",
      "extra_data": {}
    }
  ]
}
```

---

## 🔧 技术细节

### AlertManager 工作原理

`AlertManager` 是项目中的统一告警管理器（位于 `src/tzdata_pkg/core/monitoring.py`）：

```python
class AlertManager:
    def __init__(self):
        self.alert_handlers: list[Callable] = []
        self.alert_history: list[dict] = []  # 内存中存储最近 1000 条告警
    
    def send_alert(self, title, message, level='warning', category='system'):
        """发送告警"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'title': title,
            'message': message,
            'level': level,
            'category': category,
            'extra_data': {}
        }
        
        # 记录日志
        # 发送给所有注册的处理器（钉钉、企业微信、邮件等）
        # 保存到历史记录
        
    def get_recent_alerts(self, limit=50):
        """获取最近的告警"""
        return self.alert_history[-limit:]
```

### 告警触发方式

#### 方式 1: 手动发送告警

```python
from tzdata_pkg.core.monitoring import get_alert_manager

alert_manager = get_alert_manager()
alert_manager.send_alert(
    title="数据同步失败",
    message="IM2506 日线同步超时",
    level="error",
    category="sync"
)
```

#### 方式 2: 异常处理装饰器自动触发

```python
from tzdata_pkg.core.monitoring import handle_exceptions

@handle_exceptions('sync_module')
def sync_data():
    # 如果发生异常，会自动记录日志并发送告警
    ...
```

#### 方式 3: 告警规则引擎自动触发

```python
from tzdata_pkg.core.monitoring import AlertRule, get_metrics_collector

collector = get_metrics_collector()

# 添加 CPU 高负载告警规则
collector.rule_engine.add_rule(AlertRule(
    name="high_cpu",
    metric_name="cpu_usage",
    condition=">",
    threshold=80.0,
    duration_seconds=300,
    cooldown_seconds=600,
    level="warning"
))

# 记录指标，自动评估规则
collector.set_gauge('cpu_usage', 85.0)  # 可能触发告警
```

---

## 📊 验证结果

### 路由检查

```bash
$ python check_routes.py
Maintenance Routes:
  /api/maintenance/accounts [GET]
  /api/maintenance/accounts [POST]
  /api/maintenance/alerts [GET]          ← 新增
  /api/maintenance/alerts/recent [GET]   ← 新增
  /api/maintenance/catalogs [GET]
  /api/maintenance/catalogs [POST]
  /api/maintenance/health/diff [GET]
  /api/maintenance/health/snapshot [GET]
  /api/maintenance/quality/{catalog_id} [GET]
  /api/maintenance/sync/task/{task_id} [GET]
  /api/maintenance/sync/trigger [POST]

✓ 找到 2 个 alerts 路由
```

### API 测试

```bash
$ curl http://localhost:8000/api/maintenance/alerts/recent?limit=5
{"success":true,"data":[]}

# 状态码: 200 ✅
```

---

## 💡 使用建议

### 前端集成

前端已经在 `Dashboard.vue` 中调用了这个 API：

```javascript
// Load recent alerts
const alertRes = await alertAPI.getRecent(5)
recentAlerts.value = alertRes.data || []
summary.value.activeAlerts = recentAlerts.value.filter(a => a.level === 'error' || a.level === 'critical').length
```

现在可以正常显示告警信息了。

### 配置告警通知渠道

如果需要接收告警通知，可以配置以下渠道：

```python
from tzdata_pkg.core.monitoring import (
    get_alert_manager,
    dingtalk_webhook_handler,
    wechat_webhook_handler,
    email_handler
)

alert_manager = get_alert_manager()

# 钉钉机器人
alert_manager.register_handler(
    dingtalk_webhook_handler("https://oapi.dingtalk.com/robot/send?access_token=xxx")
)

# 企业微信
alert_manager.register_handler(
    wechat_webhook_handler("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx")
)

# 邮件通知
smtp_config = {
    'host': 'smtp.example.com',
    'port': 587,
    'username': 'user@example.com',
    'password': 'password',
    'from_addr': 'alerts@example.com',
    'to_addrs': ['admin@example.com'],
    'use_tls': True
}
alert_manager.register_handler(email_handler(smtp_config))
```

详细配置请参考：[MONITORING_GUIDE.md](file://c:\myspace\tz-data\MONITORING_GUIDE.md)

---

## ✅ 验证清单

- [x] 添加 `/api/maintenance/alerts` 路由
- [x] 添加 `/api/maintenance/alerts/recent` 路由
- [x] 支持告警过滤（level, category）
- [x] 支持分页（page, page_size）
- [x] 重启后端服务
- [x] 清理 Python 缓存
- [x] 验证 API 返回 200
- [x] 前端可以正常加载

---

## 📝 相关文件

- [src/tzdata_pkg/api/routes/maintenance.py](file://c:\myspace\tz-data\src\tzdata_pkg\api\routes\maintenance.py) - 新增告警路由
- [src/tzdata_pkg/core/monitoring.py](file://c:\myspace\tz-data\src\tzdata_pkg\core\monitoring.py) - AlertManager 实现
- [frontend/src/api/index.js](file://c:\myspace\tz-data\frontend\src\api\index.js) - 前端 alertAPI 定义
- [frontend/src/views/Dashboard.vue](file://c:\myspace\tz-data\frontend\src\views\Dashboard.vue) - 前端调用位置
- [frontend/src/views/AlertList.vue](file://c:\myspace\tz-data\frontend\src\views\AlertList.vue) - 告警列表页面

---

**修复完成时间**: 2026-05-12  
**修复人员**: AI Assistant  
**验证状态**: ✅ 已通过测试
