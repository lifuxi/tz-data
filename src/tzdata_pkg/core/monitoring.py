"""
Unified logging, monitoring and alerting system.
Provides centralized logging, exception handling, and alert notifications.
"""
import logging
import sys
import traceback
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from pathlib import Path
import json
from collections import defaultdict
from dataclasses import dataclass, field

# Try to import optional dependencies
try:
    import requests
    NOTIFICATION_AVAILABLE = True
except ImportError:
    NOTIFICATION_AVAILABLE = False


class LogLevel:
    """Log level constants."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class UnifiedLogger:
    """
    Unified logging system with multiple handlers and formatters.
    
    Features:
    - Console output with colors
    - File logging with rotation
    - Structured JSON logging for production
    - Log level filtering
    """
    
    _instance = None
    _loggers = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
    def get_logger(self, name: str, level: int = logging.INFO) -> logging.Logger:
        """
        Get or create a logger with unified configuration.
        
        Args:
            name: Logger name (usually __name__)
            level: Logging level
        
        Returns:
            Configured logger instance
        """
        if name in self._loggers:
            return self._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Prevent duplicate handlers
        if logger.handlers:
            self._loggers[name] = logger
            return logger
        
        # Create formatter
        formatter = self._create_formatter()
        
        # Add console handler
        console_handler = self._create_console_handler(formatter)
        logger.addHandler(console_handler)
        
        # Add file handler
        file_handler = self._create_file_handler(formatter)
        logger.addHandler(file_handler)
        
        # Add JSON file handler for production
        json_handler = self._create_json_handler()
        logger.addHandler(json_handler)
        
        self._loggers[name] = logger
        return logger
    
    def _create_formatter(self) -> logging.Formatter:
        """Create standard log formatter."""
        return logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _create_console_handler(self, formatter: logging.Formatter) -> logging.Handler:
        """Create console handler with color support."""
        handler = logging.StreamHandler(sys.stdout)
        
        # Add color formatter for console
        color_formatter = ColorFormatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(color_formatter)
        
        return handler
    
    def _create_file_handler(self, formatter: logging.Formatter) -> logging.Handler:
        """Create rotating file handler."""
        from logging.handlers import RotatingFileHandler
        
        log_file = self.log_dir / "app.log"
        handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        handler.setFormatter(formatter)
        
        return handler
    
    def _create_json_handler(self) -> logging.Handler:
        """Create JSON format file handler for production."""
        from logging.handlers import RotatingFileHandler
        
        json_log_file = self.log_dir / "app.json.log"
        handler = RotatingFileHandler(
            filename=json_log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        
        json_formatter = JsonFormatter()
        handler.setFormatter(json_formatter)
        
        return handler


class ColorFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[1;31m', # Bold Red
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        # Save original levelname
        original_levelname = record.levelname
        
        # Add color to levelname
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        # Format the message
        result = super().format(record)
        
        # Restore original levelname
        record.levelname = original_levelname
        
        return result


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        return json.dumps(log_data, ensure_ascii=False)


class AlertManager:
    """
    Alert notification manager.
    
    Supports multiple notification channels:
    - Email
    - DingTalk webhook
    - WeChat Work webhook
    - Slack webhook
    - SMS (via third-party service)
    """
    
    def __init__(self):
        self.alert_handlers: list[Callable] = []
        self.alert_history: list[dict] = []
    
    def register_handler(self, handler: Callable):
        """
        Register an alert handler.
        
        Args:
            handler: Function that takes alert_dict and sends notification
        """
        self.alert_handlers.append(handler)
    
    def send_alert(
        self,
        title: str,
        message: str,
        level: str = 'warning',
        category: str = 'system',
        extra_data: Optional[dict] = None
    ):
        """
        Send alert through all registered handlers.
        
        Args:
            title: Alert title
            message: Alert message
            level: Alert level (info/warning/error/critical)
            category: Alert category
            extra_data: Additional data
        """
        alert = {
            'timestamp': datetime.now().isoformat(),
            'title': title,
            'message': message,
            'level': level,
            'category': category,
            'extra_data': extra_data or {}
        }
        
        # Log the alert
        logger = UnifiedLogger().get_logger('alert_manager')
        log_message = f"[{level.upper()}] {title}: {message}"
        
        if level in ['error', 'critical']:
            logger.error(log_message)
        elif level == 'warning':
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        # Send through all handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
        
        # Store in history
        self.alert_history.append(alert)
        
        # Keep only last 1000 alerts
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
    
    def get_recent_alerts(self, limit: int = 50) -> list[dict]:
        """Get recent alerts."""
        return self.alert_history[-limit:]


# === Pre-built Alert Handlers ===

def dingtalk_webhook_handler(webhook_url: str) -> Callable:
    """
    Create a DingTalk webhook alert handler.
    
    Args:
        webhook_url: DingTalk webhook URL
    
    Returns:
        Alert handler function
    """
    if not NOTIFICATION_AVAILABLE:
        return lambda alert: None
    
    def handler(alert: dict):
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": alert['title'],
                "text": f"## {alert['title']}\n\n"
                       f"**级别**: {alert['level']}\n\n"
                       f"**时间**: {alert['timestamp']}\n\n"
                       f"**详情**: {alert['message']}\n"
            }
        }
        
        try:
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Failed to send DingTalk alert: {e}")
    
    return handler


def wechat_webhook_handler(webhook_url: str) -> Callable:
    """
    Create a WeChat Work webhook alert handler.
    
    Args:
        webhook_url: WeChat webhook URL
    
    Returns:
        Alert handler function
    """
    if not NOTIFICATION_AVAILABLE:
        return lambda alert: None
    
    def handler(alert: dict):
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {alert['title']}\n"
                          f"> **级别**: {alert['level']}\n"
                          f"> **时间**: {alert['timestamp']}\n"
                          f"> **详情**: {alert['message']}\n"
            }
        }
        
        try:
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Failed to send WeChat alert: {e}")
    
    return handler


def email_handler(smtp_config: dict) -> Callable:
    """
    Create an email alert handler with HTML template support.
    
    Args:
        smtp_config: SMTP configuration dict with keys:
            - host: SMTP server host
            - port: SMTP server port
            - username: SMTP username
            - password: SMTP password
            - from_addr: Sender email
            - to_addrs: List of recipient emails
            - use_tls: Whether to use TLS (default: True)
    
    Returns:
        Alert handler function
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # Level color mapping
    level_colors = {
        'info': '#409EFF',
        'warning': '#E6A23C',
        'error': '#F56C6C',
        'critical': '#F56C6C'
    }
    
    def handler(alert: dict):
        subject = f"[{alert['level'].upper()}] {alert['title']}"
        
        # Create HTML email with template
        color = level_colors.get(alert['level'], '#909399')
        body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
                .info-row {{ margin: 10px 0; padding: 10px; background-color: white; border-left: 4px solid {color}; }}
                .label {{ font-weight: bold; color: #666; }}
                .footer {{ margin-top: 20px; text-align: center; color: #999; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2 style="margin: 0;">🔔 {alert['title']}</h2>
                </div>
                <div class="content">
                    <div class="info-row">
                        <span class="label">级别:</span> {alert['level'].upper()}
                    </div>
                    <div class="info-row">
                        <span class="label">时间:</span> {alert['timestamp']}
                    </div>
                    <div class="info-row">
                        <span class="label">类别:</span> {alert.get('category', 'system')}
                    </div>
                    <div class="info-row">
                        <span class="label">详情:</span><br>
                        <p style="margin: 10px 0;">{alert['message']}</p>
                    </div>
                </div>
                <div class="footer">
                    <p>此邮件由数据维护系统自动发送，请勿回复</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_config['from_addr']
        msg['To'] = ', '.join(smtp_config['to_addrs'])
        msg.attach(MIMEText(body, 'html', 'utf-8'))
        
        try:
            use_tls = smtp_config.get('use_tls', True)
            if use_tls:
                server = smtplib.SMTP(smtp_config['host'], smtp_config['port'])
                server.ehlo()
                server.starttls()
                server.ehlo()
            else:
                server = smtplib.SMTP(smtp_config['host'], smtp_config['port'])
            
            server.login(smtp_config['username'], smtp_config['password'])
            server.sendmail(
                smtp_config['from_addr'],
                smtp_config['to_addrs'],
                msg.as_string()
            )
            server.quit()
        except Exception as e:
            print(f"Failed to send email alert: {e}")
    
    return handler


# === Global Instances ===

_unified_logger = UnifiedLogger()
_alert_manager = AlertManager()


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Get a unified logger instance."""
    return _unified_logger.get_logger(name, level)


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    return _alert_manager


# === Exception Handler Decorator ===

def handle_exceptions(logger_name: str = 'app'):
    """
    Decorator to handle exceptions in functions.
    
    Usage:
        @handle_exceptions('my_module')
        def my_function():
            ...
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Exception in {func.__name__}: {e}",
                    exc_info=True
                )
                
                # Send alert for critical errors
                if isinstance(e, (ConnectionError, TimeoutError)):
                    get_alert_manager().send_alert(
                        title=f"Function Error: {func.__name__}",
                        message=str(e),
                        level='error',
                        category='exception'
                    )
                
                raise
        return wrapper
    return decorator


# === Alert Rule Engine ===

@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    metric_name: str
    condition: str  # '>', '<', '>=', '<=', '==', '!='
    threshold: float
    duration_seconds: int = 0  # How long condition must be true
    cooldown_seconds: int = 300  # Minimum time between alerts
    level: str = 'warning'
    enabled: bool = True
    last_triggered: Optional[float] = None
    condition_start_time: Optional[float] = None


class AlertRuleEngine:
    """
    Alert rule engine for threshold-based alerting.
    
    Features:
    - Threshold detection
    - Duration-based triggering
    - Cooldown period to prevent alert storms
    - Automatic rule evaluation
    """
    
    def __init__(self):
        self.rules: dict[str, AlertRule] = {}
        self.metric_values: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self.logger = get_logger('alert_rule_engine')
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.rules[rule.name] = rule
        self.logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """Remove an alert rule."""
        if rule_name in self.rules:
            del self.rules[rule_name]
            self.logger.info(f"Removed alert rule: {rule_name}")
    
    def record_metric(self, metric_name: str, value: float, timestamp: Optional[float] = None):
        """
        Record a metric value.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            timestamp: Unix timestamp (default: current time)
        """
        if timestamp is None:
            timestamp = time.time()
        
        self.metric_values[metric_name].append((timestamp, value))
        
        # Keep only last 1000 values per metric
        if len(self.metric_values[metric_name]) > 1000:
            self.metric_values[metric_name] = self.metric_values[metric_name][-1000:]
        
        # Evaluate rules for this metric
        self._evaluate_rules(metric_name, timestamp)
    
    def _evaluate_rules(self, metric_name: str, current_time: float):
        """Evaluate all rules for a given metric."""
        for rule in self.rules.values():
            if not rule.enabled or rule.metric_name != metric_name:
                continue
            
            # Check cooldown
            if rule.last_triggered and (current_time - rule.last_triggered) < rule.cooldown_seconds:
                continue
            
            # Get recent values
            values = self._get_recent_values(metric_name, rule.duration_seconds, current_time)
            if not values:
                continue
            
            # Check if condition is met for all values in duration
            condition_met = all(
                self._check_condition(value, rule.condition, rule.threshold)
                for _, value in values
            )
            
            if condition_met:
                if rule.duration_seconds == 0:
                    # Immediate trigger
                    self._trigger_alert(rule, values[-1][1])
                else:
                    # Duration-based trigger
                    if rule.condition_start_time is None:
                        rule.condition_start_time = values[0][0]
                    
                    duration_met = (current_time - rule.condition_start_time) >= rule.duration_seconds
                    if duration_met:
                        self._trigger_alert(rule, values[-1][1])
                        rule.condition_start_time = None
            else:
                # Reset condition start time
                rule.condition_start_time = None
    
    def _get_recent_values(self, metric_name: str, duration: int, current_time: float) -> list[tuple[float, float]]:
        """Get metric values within the specified duration."""
        if duration == 0:
            # Return latest value
            values = self.metric_values.get(metric_name, [])
            return [values[-1]] if values else []
        
        cutoff_time = current_time - duration
        return [
            (ts, val) for ts, val in self.metric_values.get(metric_name, [])
            if ts >= cutoff_time
        ]
    
    def _check_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Check if a value meets the condition."""
        if condition == '>':
            return value > threshold
        elif condition == '<':
            return value < threshold
        elif condition == '>=':
            return value >= threshold
        elif condition == '<=':
            return value <= threshold
        elif condition == '==':
            return value == threshold
        elif condition == '!=':
            return value != threshold
        return False
    
    def _trigger_alert(self, rule: AlertRule, current_value: float):
        """Trigger an alert for a rule."""
        alert_manager = get_alert_manager()
        alert_manager.send_alert(
            title=f"Alert Rule Triggered: {rule.name}",
            message=f"Metric '{rule.metric_name}' = {current_value:.2f} {rule.condition} {rule.threshold}",
            level=rule.level,
            category='rule_trigger',
            extra_data={
                'rule_name': rule.name,
                'metric_name': rule.metric_name,
                'current_value': current_value,
                'threshold': rule.threshold,
                'condition': rule.condition
            }
        )
        
        rule.last_triggered = time.time()
        self.logger.warning(f"Alert rule triggered: {rule.name}")


# === Metrics Collector ===

@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    timestamp: float
    tags: dict = field(default_factory=dict)


class MetricsCollector:
    """
    Metrics collector for system, application, and business metrics.
    
    Supports:
    - Counter metrics (monotonically increasing)
    - Gauge metrics (current value)
    - Histogram metrics (distribution)
    - Timer metrics (duration)
    """
    
    def __init__(self):
        self.metrics: dict[str, list[MetricPoint]] = defaultdict(list)
        self.counters: dict[str, float] = defaultdict(float)
        self.gauges: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = defaultdict(list)
        self.timers: dict[str, list[float]] = defaultdict(list)
        self.rule_engine = AlertRuleEngine()
        self.logger = get_logger('metrics_collector')
    
    # --- Counter Metrics ---
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Optional[dict] = None):
        """Increment a counter metric."""
        self.counters[name] += value
        self._record_metric(name, self.counters[name], tags or {})
    
    def get_counter(self, name: str) -> float:
        """Get current counter value."""
        return self.counters.get(name, 0.0)
    
    # --- Gauge Metrics ---
    
    def set_gauge(self, name: str, value: float, tags: Optional[dict] = None):
        """Set a gauge metric."""
        self.gauges[name] = value
        self._record_metric(name, value, tags or {})
    
    def get_gauge(self, name: str) -> Optional[float]:
        """Get current gauge value."""
        return self.gauges.get(name)
    
    # --- Histogram Metrics ---
    
    def observe_histogram(self, name: str, value: float, tags: Optional[dict] = None):
        """Record a histogram observation."""
        self.histograms[name].append(value)
        self._record_metric(name, value, tags or {}, metric_type='histogram')
        
        # Keep only last 1000 observations
        if len(self.histograms[name]) > 1000:
            self.histograms[name] = self.histograms[name][-1000:]
    
    def get_histogram_stats(self, name: str) -> dict:
        """Get histogram statistics."""
        values = self.histograms.get(name, [])
        if not values:
            return {'count': 0, 'min': 0, 'max': 0, 'avg': 0, 'p50': 0, 'p95': 0, 'p99': 0}
        
        sorted_values = sorted(values)
        count = len(sorted_values)
        
        return {
            'count': count,
            'min': sorted_values[0],
            'max': sorted_values[-1],
            'avg': sum(sorted_values) / count,
            'p50': sorted_values[int(count * 0.5)],
            'p95': sorted_values[int(count * 0.95)],
            'p99': sorted_values[int(count * 0.99)]
        }
    
    # --- Timer Metrics ---
    
    def record_timer(self, name: str, duration: float, tags: Optional[dict] = None):
        """Record a timer duration."""
        self.timers[name].append(duration)
        self._record_metric(name, duration, tags or {}, metric_type='timer')
        
        # Keep only last 1000 timings
        if len(self.timers[name]) > 1000:
            self.timers[name] = self.timers[name][-1000:]
    
    def timer(self, name: str, tags: Optional[dict] = None):
        """Context manager/decorator for timing code execution."""
        return TimerContext(self, name, tags or {})
    
    # --- Internal Methods ---
    
    def _record_metric(self, name: str, value: float, tags: dict, metric_type: str = 'gauge'):
        """Record a metric point."""
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags
        )
        self.metrics[name].append(point)
        
        # Keep only last 1000 points per metric
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]
        
        # Feed to rule engine
        self.rule_engine.record_metric(name, value)
    
    def get_metric_history(self, name: str, limit: int = 100) -> list[MetricPoint]:
        """Get recent metric history."""
        return self.metrics.get(name, [])[-limit:]
    
    def get_all_metrics_summary(self) -> dict:
        """Get summary of all metrics."""
        return {
            'counters': dict(self.counters),
            'gauges': dict(self.gauges),
            'histograms': {
                name: self.get_histogram_stats(name)
                for name in self.histograms.keys()
            },
            'timers': {
                name: self.get_histogram_stats(name)
                for name in self.timers.keys()
            }
        }


class TimerContext:
    """Context manager for timing code execution."""
    
    def __init__(self, collector: MetricsCollector, name: str, tags: dict):
        self.collector = collector
        self.name = name
        self.tags = tags
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.collector.record_timer(self.name, duration, self.tags)


# === Global Instances ===

_unified_logger = UnifiedLogger()
_alert_manager = AlertManager()
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics_collector
