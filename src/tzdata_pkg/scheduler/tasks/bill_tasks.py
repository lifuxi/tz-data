"""
Celery task for calendar-driven bill completeness check.

Checks bills.db against the CFFEX trading calendar to detect
missing bill dates. Triggers DingTalk alert for gaps.
"""
import logging
import sqlite3
from datetime import date, timedelta

from tzdata_pkg.scheduler.celery_app import celery_app
from tzdata_pkg.config import BILLS_DB
from tzdata_pkg.scheduler.task_logger import log_beat_task

logger = logging.getLogger(__name__)


@celery_app.task
@log_beat_task
def daily_bill_calendar_check():
    """
    Check bill completeness against trading calendar.
    Scheduled at 21:00 on trading days.

    For each active account:
    1. Get last 10 CFFEX trading days
    2. Check bills.db for each trading day's records
    3. Alert on missing dates
    """
    try:
        from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator

        dc = DateCalculator()
        today = date.today()

        # Get last 10 trading days
        try:
            latest_trading = dc.get_prev_trading_day(today, n=1, exchange_code='CFFEX')
        except (ValueError, Exception):
            latest_trading = today - timedelta(days=1)

        earliest = dc.get_prev_trading_day(latest_trading, n=9, exchange_code='CFFEX')
        trading_days = dc.get_trading_days_list(earliest, latest_trading, exchange_code='CFFEX')
        trading_day_set = {d.isoformat() for d in trading_days}

        if not trading_days:
            logger.warning("No trading days found in range, skipping bill check")
            return {"status": "skipped", "reason": "no trading days"}

        # Check bills.db for bill dates
        bill_dates = _get_bill_dates_from_db()

        # Find missing trading days
        missing = sorted(trading_day_set - bill_dates)

        result = {
            "status": "completed",
            "check_date": today.isoformat(),
            "trading_days_checked": len(trading_days),
            "bill_dates_found": len(bill_dates),
            "missing_dates": missing[:10],  # Latest 10
            "missing_count": len(missing),
        }

        if missing:
            logger.warning(
                f"Bill calendar check: {len(missing)} missing trading days. "
                f"Latest: {missing[-1]}"
            )
            # Trigger DingTalk alert
            try:
                from tzdata_pkg.scheduler.tasks.alert_tasks import send_bill_alert
                send_bill_alert(
                    account_name="默认账户",
                    missing_days=len(missing),
                    latest_missing=missing[-1],
                )
            except Exception as e:
                logger.error(f"Failed to send bill alert: {e}")
        else:
            logger.info("Bill calendar check passed: all trading days covered")

        return result

    except Exception as e:
        logger.error(f"Bill calendar check failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


def _get_bill_dates_from_db() -> set:
    """Get all distinct bill dates from bills.db."""
    try:
        if not BILLS_DB.exists():
            return set()
        conn = sqlite3.connect(str(BILLS_DB))
        # Try to get dates from common bill table structures
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]

        bill_dates = set()

        # Check for bills table with date column
        if "bills" in tables:
            rows = conn.execute("""
                SELECT DISTINCT bill_date FROM bills
                WHERE bill_date IS NOT NULL
            """).fetchall()
            for row in rows:
                bill_dates.add(str(row[0])[:10])

        # Also check for statement-related tables
        for table in tables:
            if "statement" in table.lower() or "bill" in table.lower():
                try:
                    cols = [row[1] for row in conn.execute(
                        f"PRAGMA table_info({table})"
                    ).fetchall()]
                    for col in ["bill_date", "trade_date", "date", "statement_date"]:
                        if col in cols:
                            rows = conn.execute(f"""
                                SELECT DISTINCT {col} FROM {table}
                                WHERE {col} IS NOT NULL
                            """).fetchall()
                            for row in rows:
                                bill_dates.add(str(row[0])[:10])
                            break
                except Exception:
                    pass

        conn.close()
        return bill_dates
    except Exception as e:
        logger.error(f"Failed to read bill dates: {e}")
        return set()


@celery_app.task
@log_beat_task
def cfmmc_scraper_health_check():
    """
    Weekly health check for CFMMC website accessibility.
    Scheduled at Saturday 09:00.

    Sends DingTalk alert if the site is unreachable or structure changed.
    """
    try:
        from tzdata_pkg.maintenance.statements.cfmmc_scraper import CFMMCScraper

        scraper = CFMMCScraper(headless=True)
        result = scraper.health_check()

        logger.info(f"CFMMC health check: {result}")

        if result['status'] != 'healthy':
            try:
                from tzdata_pkg.scheduler.tasks.alert_tasks import _get_dingtalk_webhook
                from tzdata_pkg.core.monitoring import get_alert_manager, dingtalk_webhook_handler

                webhook = _get_dingtalk_webhook()
                if webhook:
                    handler = dingtalk_webhook_handler(webhook)
                    get_alert_manager().register_handler(handler)

                get_alert_manager().send_alert(
                    title="CFMMC 爬虫健康检查告警",
                    message=f"CFMMC 网站状态: **{result['status']}**\n\n"
                            f"**HTTP 状态**: {result['http_status']}\n"
                            f"**登录表单**: {'已找到' if result['login_form_found'] else '未找到'}\n"
                            f"**错误**: {result.get('error', 'N/A')}\n\n"
                            f"建议: 检查 CFMMC 网站是否可访问，页面结构是否变更。",
                    level="warning" if result['status'] == 'degraded' else "error",
                    category="scraper_health",
                    extra_data=result,
                )
            except Exception as e:
                logger.error(f"Failed to send CFMMC health alert: {e}")

        return result

    except Exception as e:
        logger.error(f"CFMMC health check failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}
