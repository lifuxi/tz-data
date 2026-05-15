"""
Celery tasks for MO data daily sync and quality checks.

Scheduled tasks:
- 16:00  MO IV data sync (sync_mo_iv)
- 16:30  Underlying daily data sync (sync_underlying_daily)
- 18:00  MO data quality check (check_data_freshness)
"""
import logging
from datetime import date, timedelta

from tzdata_pkg.scheduler.celery_app import celery_app
from tzdata_pkg.maintenance.sync.audit_logger import get_audit_logger

logger = logging.getLogger(__name__)


def _is_trading_day() -> bool:
    """Check if today is a CFFEX trading day."""
    try:
        from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator
        dc = DateCalculator()
        return dc.is_trading_day(date.today(), exchange_code='CFFEX')
    except (ValueError, Exception) as e:
        logger.warning(f"Trading calendar check failed, assuming trading day: {e}")
        return True


@celery_app.task
def sync_mo_iv():
    """
    Sync MO/HO/IO IV data from Tushare for the latest trading day.
    Scheduled at 16:00 on trading days. Skipped on non-trading days.
    """
    audit = get_audit_logger()
    task_id = sync_mo_iv.request.id if sync_mo_iv.request.id else "sync_mo_iv"

    if not _is_trading_day():
        logger.info(f"Skipping IV sync: {date.today()} is not a CFFEX trading day")
        return {'status': 'skipped', 'reason': 'non-trading day'}

    audit.log_start(task_id, 'mo-iv-sync', sync_mode='calendar-driven',
                    exchange='CFFEX', product='MO,HO,IO')

    try:
        from tzdata_pkg.cli.daily_sync import sync_iv_daily

        result = sync_iv_daily(
            underlyings=['MO', 'HO', 'IO'],
            calendar_driven=True,
        )

        total = sum(v.get('count', 0) for v in result.values() if isinstance(v, dict))
        errors = [k for k, v in result.items() if isinstance(v, dict) and v.get('status') == 'error']

        trade_date = result.get('trade_date', date.today().isoformat())
        audit.log_success(task_id, records_fetched=total)

        if errors:
            from tzdata_pkg.scheduler.tasks.alert_tasks import send_sync_alert
            send_sync_alert(
                task_name='mo-iv-sync', status='warning',
                message=f"IV 同步部分失败: {', '.join(errors)}",
                trade_date=trade_date,
                details={'total_records': total, 'errors': errors},
            )

        logger.info(f"MO IV sync completed: {total} records, errors: {errors}")
        return {
            'status': 'completed',
            'trade_date': trade_date,
            'total_records': total,
            'errors': errors,
            'details': result,
        }
    except Exception as e:
        audit.log_failure(task_id, e)
        from tzdata_pkg.scheduler.tasks.alert_tasks import send_sync_alert
        send_sync_alert(
            task_name='mo-iv-sync', status='error',
            message=f"IV 同步失败: {e}",
            details={'error': str(e)},
        )
        logger.error(f"MO IV sync failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
        }


@celery_app.task
def sync_underlying_daily():
    """
    Sync underlying daily bar data (000852, IM, 512100, A00) from akshare/sina.
    Scheduled at 16:30 on trading days. Skipped on non-trading days.
    """
    audit = get_audit_logger()
    task_id = sync_underlying_daily.request.id if sync_underlying_daily.request.id else "sync_underlying_daily"

    if not _is_trading_day():
        logger.info(f"Skipping underlying sync: {date.today()} is not a CFFEX trading day")
        return {'status': 'skipped', 'reason': 'non-trading day'}

    audit.log_start(task_id, 'mo-underlying-sync', sync_mode='calendar-driven',
                    exchange='CFFEX', product='000852,IM,512100,A00')

    try:
        from tzdata_pkg.cli.daily_sync import sync_underlying_daily as _sync

        result = _sync(
            underlyings=['000852', 'IM', '512100', 'A00'],
            calendar_driven=True,
        )

        total = sum(v.get('count', 0) for v in result.values() if isinstance(v, dict))
        errors = [k for k, v in result.items() if isinstance(v, dict) and v.get('status') == 'error']

        audit.log_success(task_id, records_fetched=total)

        if errors:
            from tzdata_pkg.scheduler.tasks.alert_tasks import send_sync_alert
            send_sync_alert(
                task_name='mo-underlying-sync', status='warning',
                message=f"标的日线同步部分失败: {', '.join(errors)}",
                details={'total_records': total, 'errors': errors},
            )

        logger.info(f"Underlying daily sync completed: {total} records, errors: {errors}")
        return {
            'status': 'completed',
            'total_records': total,
            'errors': errors,
            'details': result,
        }
    except Exception as e:
        audit.log_failure(task_id, e)
        from tzdata_pkg.scheduler.tasks.alert_tasks import send_sync_alert
        send_sync_alert(
            task_name='mo-underlying-sync', status='error',
            message=f"标的日线同步失败: {e}",
            details={'error': str(e)},
        )
        logger.error(f"Underlying daily sync failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
        }


@celery_app.task
def mo_data_quality_check():
    """
    Run MO data quality checks (freshness, consistency, completeness).
    Scheduled at 18:00 daily.
    """
    try:
        from tzdata_pkg.maintenance.monitoring.mo_data_quality import check_data_quality_summary

        result = check_data_quality_summary()

        if result['issue_count'] > 0:
            logger.warning(f"MO data quality issues found ({result['issue_count']}): {result['issues']}")
        else:
            logger.info("MO data quality check passed: all OK")

        return {
            'status': 'completed',
            'overall_status': result['overall_status'],
            'issue_count': result['issue_count'],
            'issues': result['issues'],
            'freshness': result['freshness'],
        }
    except Exception as e:
        logger.error(f"MO data quality check failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
        }


@celery_app.task
def sync_mo_contracts():
    """
    Sync MO contract master from Tushare opt_basic.
    Scheduled weekly on Saturday 10:00.
    """
    audit = get_audit_logger()
    task_id = sync_mo_contracts.request.id if sync_mo_contracts.request.id else "sync_mo_contracts"
    audit.log_start(task_id, 'mo-contract-sync', sync_mode='full',
                    exchange='CFFEX', product='MO')

    try:
        from tzdata_pkg.cli.sync_mo_contracts import sync_mo_contracts as _sync

        result = _sync(force=False)

        total = result.get('inserted', 0) + result.get('updated', 0)
        audit.log_success(task_id, records_fetched=total)

        logger.info(f"MO contract sync completed: {result}")
        return {
            'status': 'completed',
            'inserted': result.get('inserted', 0),
            'updated': result.get('updated', 0),
            'total': total,
        }
    except Exception as e:
        audit.log_failure(task_id, e)
        from tzdata_pkg.scheduler.tasks.alert_tasks import send_sync_alert
        send_sync_alert(
            task_name='mo-contract-sync', status='error',
            message=f"合约同步失败: {e}",
            details={'error': str(e)},
        )
        logger.error(f"MO contract sync failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
        }
