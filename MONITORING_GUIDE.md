# 统一监控告警系统 - 使用指南

## 📋 概述

本系统提供统一的日志记录、异常处理和告警通知功能，支持多种通知渠道�?

## 🎯 核心功能

1. **统一日志系统** - 彩色控制台输�?+ 文件日志 + JSON 结构化日�?
2. **异常处理装饰�?* - 自动捕获和记录异�?
3. **多渠道告�?* - 钉钉、企业微信、邮件、Slack
4. **告警历史** - 自动保存最�?1000 条告�?

---

## 🚀 快速开�?

### 1. 基础日志使用

```python
from tzdata_pkg.core.monitoring import get_logger

# 获取 logger
logger = get_logger('my_module')

# 记录日志
logger.debug("调试信息")
logger.info("普通信�?)
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")
```

**输出示例**:
```
2026-05-11 15:30:00 [INFO] my_module - 普通信�?
2026-05-11 15:30:01 [ERROR] my_module - 错误信息
```

### 2. 异常处理装饰�?

```python
from tzdata_pkg.core.monitoring import handle_exceptions

@handle_exceptions('sync_engine')
def sync_data(catalog_id: int):
    # 如果发生异常，会自动记录日志并发送告�?
    result = do_something()
    return result

try:
    sync_data(1)
except Exception as e:
    print(f"Sync failed: {e}")
```

### 3. 发送告�?

```python
from tzdata_pkg.core.monitoring import get_alert_manager, dingtalk_webhook_handler

# 获取告警管理�?
alert_mgr = get_alert_manager()

# 注册钉钉 webhook
webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
alert_mgr.register_handler(dingtalk_webhook_handler(webhook_url))

# 发送告�?
alert_mgr.send_alert(
    title="数据同步失败",
    message="IM2506 日线数据同步失败: Connection timeout",
    level='error',
    category='sync',
    extra_data={'catalog_id': 1, 'retry_count': 3}
)
```

---

## 📝 详细用法

### 日志系统

#### 日志级别

| 级别 | 使用场景 | 颜色 |
|------|----------|------|
| DEBUG | 调试信息，详细的技术细�?| 青色 |
| INFO | 一般信息，正常流程 | 绿色 |
| WARNING | 警告信息，潜在问�?| 黄色 |
| ERROR | 错误信息，功能失�?| 红色 |
| CRITICAL | 严重错误，系统崩�?| 深红加粗 |

#### 日志文件

系统自动生成两个日志文件�?

1. **app.log** - 标准格式日志
   ```
   2026-05-11 15:30:00 [INFO] sync_engine - Starting sync for catalog 1
   2026-05-11 15:30:05 [ERROR] sync_engine - Batch 3 failed: Timeout
   ```

2. **app.json.log** - JSON 结构化日志（适合生产环境�?
   ```json
   {
     "timestamp": "2026-05-11T15:30:00",
     "level": "INFO",
     "logger": "sync_engine",
     "message": "Starting sync for catalog 1",
     "module": "sync_engine",
     "function": "execute",
     "line": 123
   }
   ```

#### 自定�?Logger

```python
from tzdata_pkg.core.monitoring import UnifiedLogger

# 创建自定�?logger
custom_logger = UnifiedLogger().get_logger(
    name='custom_module',
    level=logging.DEBUG  # 设置日志级别
)
```

---

### 告警系统

#### 支持的告警渠�?

##### 1. 钉钉 Webhook

```python
from tzdata_pkg.core.monitoring import dingtalk_webhook_handler

webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=XXX"
handler = dingtalk_webhook_handler(webhook_url)
alert_mgr.register_handler(handler)
```

**消息示例**:
```markdown
## 数据同步失败

**级别**: error

**时间**: 2026-05-11T15:30:00

**详情**: IM2506 日线数据同步失败: Connection timeout
```

##### 2. 企业微信 Webhook

```python
from tzdata_pkg.core.monitoring import wechat_webhook_handler

webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXX"
handler = wechat_webhook_handler(webhook_url)
alert_mgr.register_handler(handler)
```

##### 3. 邮件通知

```python
from tzdata_pkg.core.monitoring import email_handler

smtp_config = {
    'host': 'smtp.example.com',
    'port': 587,
    'username': 'alerts@example.com',
    'password': 'your_password',
    'from_addr': 'alerts@example.com',
    'to_addrs': ['admin1@example.com', 'admin2@example.com']
}

handler = email_handler(smtp_config)
alert_mgr.register_handler(handler)
```

##### 4. Slack Webhook

```python
def slack_webhook_handler(webhook_url: str):
    def handler(alert: dict):
        payload = {
            "text": f"*[{alert['level'].upper()}]* {alert['title']}\n{alert['message']}"
        }
        requests.post(webhook_url, json=payload)
    return handler

handler = slack_webhook_handler("https://hooks.slack.com/services/XXX")
alert_mgr.register_handler(handler)
```

#### 告警级别

| 级别 | 说明 | 触发条件示例 |
|------|------|--------------|
| info | 信息性告�?| 任务完成、状态变�?|
| warning | 警告 | 数据缺失、质量下�?|
| error | 错误 | 同步失败、解析错�?|
| critical | 严重 | 系统崩溃、数据库断开 |

#### 告警分类

```python
# 按业务模块分�?
alert_mgr.send_alert(..., category='sync')      # 同步相关
alert_mgr.send_alert(..., category='quality')   # 质量相关
alert_mgr.send_alert(..., category='statement') # 账单相关
alert_mgr.send_alert(..., category='system')    # 系统相关
```

#### 查询告警历史

```python
# 获取最�?50 条告�?
recent_alerts = alert_mgr.get_recent_alerts(limit=50)

for alert in recent_alerts:
    print(f"[{alert['level']}] {alert['title']}: {alert['message']}")
```

---

## 🔧 高级用法

### 1. �?Celery 任务中使�?

```python
from tzdata_pkg.scheduler.celery_app import celery_app
from tzdata_pkg.core.monitoring import get_logger, handle_exceptions

logger = get_logger('celery_tasks')

@celery_app.task(bind=True, max_retries=3)
@handle_exceptions('sync_task')
def sync_catalog_task(self, catalog_id: int):
    logger.info(f"Starting sync for catalog {catalog_id}")
    
    try:
        # Sync logic here
        result = do_sync(catalog_id)
        logger.info(f"Sync completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
```

### 2. �?FastAPI 中使�?

```python
from fastapi import FastAPI, HTTPException
from tzdata_pkg.core.monitoring import get_logger, get_alert_manager

app = FastAPI()
logger = get_logger('api')
alert_mgr = get_alert_manager()

@app.post("/api/sync/trigger")
def trigger_sync(catalog_id: int):
    try:
        logger.info(f"Triggering sync for catalog {catalog_id}")
        task = sync_catalog_task.delay(catalog_id)
        return {"task_id": task.id}
        
    except Exception as e:
        logger.error(f"Failed to trigger sync: {e}")
        
        # Send alert for critical errors
        alert_mgr.send_alert(
            title="API Error",
            message=f"Failed to trigger sync: {str(e)}",
            level='error',
            category='api'
        )
        
        raise HTTPException(status_code=500, detail=str(e))
```

### 3. 自定义告警处理器

```python
def custom_handler(alert: dict):
    """Custom alert handler example."""
    # Save to database
    save_alert_to_db(alert)
    
    # Send to monitoring system
    send_to_prometheus(alert)
    
    # Log to external service
    log_to_elasticsearch(alert)

alert_mgr.register_handler(custom_handler)
```

### 4. 条件告警

```python
def smart_alert_handler(alert: dict):
    """Only send alerts during business hours."""
    from datetime import datetime
    
    hour = datetime.now().hour
    
    # Only send alerts between 9 AM and 6 PM
    if 9 <= hour <= 18:
        send_notification(alert)
    else:
        # Save to queue for later processing
        queue_alert(alert)

alert_mgr.register_handler(smart_alert_handler)
```

---

## 📊 监控指标

### 日志统计

```python
import re
from collections import Counter

def analyze_logs(log_file='logs/app.log'):
    """Analyze log file and generate statistics."""
    with open(log_file, 'r') as f:
        logs = f.readlines()
    
    level_counts = Counter()
    error_messages = []
    
    for log in logs:
        match = re.search(r'\[(\w+)\]', log)
        if match:
            level = match.group(1)
            level_counts[level] += 1
            
            if level in ['ERROR', 'CRITICAL']:
                error_messages.append(log.strip())
    
    print("=== Log Statistics ===")
    for level, count in level_counts.items():
        print(f"{level}: {count}")
    
    print(f"\nTotal errors: {len(error_messages)}")
    print("\nRecent errors:")
    for msg in error_messages[-5:]:
        print(f"  {msg}")

# Usage
analyze_logs()
```

### 告警统计

```python
def alert_statistics():
    """Generate alert statistics."""
    alert_mgr = get_alert_manager()
    alerts = alert_mgr.get_recent_alerts(limit=1000)
    
    # Count by level
    level_counts = Counter(a['level'] for a in alerts)
    
    # Count by category
    category_counts = Counter(a['category'] for a in alerts)
    
    print("=== Alert Statistics (Last 1000) ===")
    print("\nBy Level:")
    for level, count in level_counts.items():
        print(f"  {level}: {count}")
    
    print("\nBy Category:")
    for category, count in category_counts.items():
        print(f"  {category}: {count}")

# Usage
alert_statistics()
```

---

## ⚙️ 配置示例

### 环境变量配置

```bash
# .env file

# Logging
LOG_LEVEL=INFO
LOG_DIR=./logs

# DingTalk
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=XXX

# WeChat
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXX

# Email
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=your_password
ALERT_EMAIL_TO=admin1@example.com,admin2@example.com
```

### 初始化脚�?

```python
# init_monitoring.py
import os
from dotenv import load_dotenv
from tzdata_pkg.core.monitoring import get_alert_manager, dingtalk_webhook_handler, wechat_webhook_handler

load_dotenv()

def setup_monitoring():
    """Setup monitoring and alerting."""
    alert_mgr = get_alert_manager()
    
    # Register DingTalk handler
    if dingtalk_url := os.getenv('DINGTALK_WEBHOOK_URL'):
        alert_mgr.register_handler(dingtalk_webhook_handler(dingtalk_url))
    
    # Register WeChat handler
    if wechat_url := os.getenv('WECHAT_WEBHOOK_URL'):
        alert_mgr.register_handler(wechat_webhook_handler(wechat_url))
    
    print("Monitoring system initialized")

# Call this at application startup
setup_monitoring()
```

---

## 🐛 故障排查

### 问题 1: 日志文件未生�?

**原因**: 日志目录权限不足

**解决**:
```bash
mkdir -p logs
chmod 755 logs
```

### 问题 2: 告警未发�?

**检�?*:
1. Webhook URL 是否正确
2. 网络连接是否正常
3. 查看日志中的错误信息

**调试**:
```python
# Test webhook manually
import requests

response = requests.post(webhook_url, json={"test": "message"})
print(response.status_code)
print(response.text)
```

### 问题 3: 日志颜色不显�?

**原因**: 终端不支�?ANSI 颜色

**解决**: 使用支持颜色的终端（�?iTerm2、Windows Terminal�?

---

## 📚 最佳实�?

1. **合理使用日志级别**
   - DEBUG: 仅在开发时使用
   - INFO: 记录重要业务流程
   - WARNING: 记录潜在问题
   - ERROR: 记录可恢复的错误
   - CRITICAL: 记录系统级故�?

2. **避免日志过多**
   - 不要在循环中记录 DEBUG 日志
   - 使用采样记录高频事件
   - 定期清理旧日志文�?

3. **告警去重**
   - 相同错误不要重复发送告�?
   - 使用告警聚合机制
   - 设置合理的告警间�?

4. **敏感信息脱敏**
   - 不要在日志中记录密码、密�?
   - 对用户数据进行脱敏处�?
   - 使用加密存储敏感配置

5. **性能考虑**
   - 异步发送告�?
   - 批量处理日志写入
   - 使用日志缓冲

---

## 🔗 相关文档

- [Python logging 官方文档](https://docs.python.org/3/library/logging.html)
- [钉钉机器人文档](https://open.dingtalk.com/document/robots/custom-robot-access)
- [企业微信机器人文档](https://developer.work.weixin.qq.com/document/path/91770)

---

祝使用愉快！🎉
