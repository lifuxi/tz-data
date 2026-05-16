"""
Celery signal handlers for task failure alerts.

Sends webhook notifications (WeChat/DingTalk) when sync tasks fail,
and records failures to the market DB for frontend query.
"""
import logging
import os
from datetime import datetime, timezone

from celery.signals import task_failure, task_retry

logger = logging.getLogger(__name__)

# Rate limit: same task name within this window (seconds) → skip duplicate alert
_ALERT_COOLDOWN = 300  # 5 minutes
_last_alerts: dict[str, float] = {}


def _should_alert(task_name: str) -> bool:
    """Rate-limit alerts per task name."""
    import time
    now = time.time()
    last = _last_alerts.get(task_name, 0)
    if now - last < _ALERT_COOLDOWN:
        return False
    _last_alerts[task_name] = now
    return True


def _send_webhook(task_name: str, task_id: str, exc: Exception, traceback_str: str) -> None:
    """Send failure alert via WeChat or DingTalk webhook."""
    webhook_url = os.getenv('WECHAT_WEBHOOK_URL') or os.getenv('DINGTALK_WEBHOOK_URL')
    if not webhook_url:
        return

    short_tb = ''
    if traceback_str:
        lines = traceback_str.strip().split('\n')
        short_tb = '\n'.join(lines[-5:])  # Last 5 lines of traceback

    payload = {
        "msgtype": "text",
        "text": {
            "content": (
                f"[tz-data 同步告警]\n"
                f"任务: {task_name}\n"
                f"Task ID: {task_id}\n"
                f"错误: {type(exc).__name__}: {exc}\n"
                f"时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"{short_tb}"
            )
        },
    }

    try:
        import httpx
        httpx.post(webhook_url, json=payload, timeout=5.0)
        logger.info("Sync failure webhook sent: %s", task_name)
    except Exception as e:
        logger.warning("Webhook send failed: %s", e)


def _record_failure(task_name: str, task_id: str, exc: Exception) -> None:
    """Record task failure to market DB for frontend query."""
    try:
        from tzdata_pkg.storage.db_registry import DBRegistry
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO task_failure_log
                (task_name, task_id, error_type, error_message, failed_at, retries)
                VALUES (?, ?, ?, ?, datetime('now'), 0)
                """,
                (task_name, task_id, type(exc).__name__, str(exc)[:500]),
            )
        logger.info("Task failure recorded: %s", task_name)
    except Exception:
        # Non-critical: don't let alerting break on DB write failure
        pass


@task_failure.connect
def handle_task_failure(sender=None, task_id=None, task=None,
                        exception=None, traceback=None, **kwargs):
    """Handle any Celery task failure: alert + record."""
    if exception is None:
        return

    task_name = getattr(sender, 'name', 'unknown')

    # Only alert for sync/quality-related tasks, not everything
    alert_prefixes = (
        'tzdata_pkg.scheduler.tasks.sync_tasks',
        'tzdata_pkg.scheduler.tasks.mo_tasks',
        'tzdata_pkg.scheduler.tasks.position_tasks',
        'tzdata_pkg.scheduler.tasks.check_tasks',
        'tzdata_pkg.scheduler.tasks.statement_tasks',
        'tzdata_pkg.scheduler.tasks.bill_tasks',
        'tzdata_pkg.scheduler.tasks.data_tasks',
        'tzdata_pkg.scheduler.tasks.market_env_tasks',
        'src.tasks.',
    )
    if not any(task_name.startswith(p) for p in alert_prefixes):
        return

    logger.error("Task failure: %s (id=%s): %s", task_name, task_id, exception)

    if _should_alert(task_name):
        _send_webhook(task_name, task_id, exception, traceback or '')

    _record_failure(task_name, task_id, exception)


@task_retry.connect
def handle_task_retry(sender=None, task_id=None, task=None,
                      exception=None, traceback=None, **kwargs):
    """Log task retry (not alerting, just logging)."""
    if exception is None:
        return
    task_name = getattr(sender, 'name', 'unknown')
    logger.warning("Task retry: %s (id=%s): %s", task_name, task_id, exception)
