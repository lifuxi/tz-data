"""
DingTalk alert task for data sync monitoring.

Reads DINGTALK_WEBHOOK_URL from .env and registers the handler
with the global AlertManager on module import.
"""
import logging
import os

from tzdata_pkg.core.monitoring import get_alert_manager, dingtalk_webhook_handler

logger = logging.getLogger(__name__)

# Lazily initialized on first use
_initialized = False


def _init_alerts():
    """Register DingTalk webhook handler if configured."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    webhook_url = os.getenv("DINGTALK_WEBHOOK_URL", "")
    if not webhook_url:
        logger.info("DingTalk webhook not configured (set DINGTALK_WEBHOOK_URL in .env)")
        return

    try:
        handler = dingtalk_webhook_handler(webhook_url)
        get_alert_manager().register_handler(handler)
        logger.info("DingTalk alert handler registered")
    except Exception as e:
        logger.error(f"Failed to register DingTalk handler: {e}")


def send_sync_alert(
    task_name: str,
    status: str,
    message: str,
    trade_date: str = "",
    details: dict = None,
):
    """
    Send alert for sync task events.

    Args:
        task_name: e.g. 'mo-iv-sync', 'mo-underlying-sync'
        status: 'error' | 'warning' | 'info'
        message: Human-readable alert message
        trade_date: Target trading date
        details: Optional extra data
    """
    _init_alerts()

    level = status if status in ("error", "warning", "info", "critical") else "warning"
    title = f"数据同步通知: {task_name}"
    body = message
    if trade_date:
        body += f"\n\n**交易日**: {trade_date}"
    if details:
        extra = ", ".join(f"{k}={v}" for k, v in details.items())
        body += f"\n\n**详情**: {extra}"

    get_alert_manager().send_alert(
        title=title,
        message=body,
        level=level,
        category="sync",
        extra_data={"task_name": task_name, "trade_date": trade_date},
    )


def send_bill_alert(account_name: str, missing_days: int, latest_missing: str):
    """
    Send alert for missing bill dates.

    Args:
        account_name: Account display name
        missing_days: Number of missing trading days
        latest_missing: Latest missing date
    """
    _init_alerts()

    get_alert_manager().send_alert(
        title=f"账单缺失告警: {account_name}",
        message=f"账户 **{account_name}** 缺失 **{missing_days}** 个交易日账单，"
                f"最新缺失日期: {latest_missing}。\n\n建议: 登录 CFMMC 补下载账单。",
        level="warning",
        category="bill",
        extra_data={"account_name": account_name, "missing_days": missing_days},
    )
