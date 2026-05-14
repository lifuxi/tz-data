"""
Celery tasks for MO data daily sync and quality checks.

Scheduled tasks:
- 16:00  MO IV data sync (sync_mo_iv)
- 16:30  Underlying daily data sync (sync_index_daily)
- 18:00  MO data quality check (check_data_freshness)
"""
import logging
from datetime import date, timedelta

from tzdata_pkg.scheduler.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def sync_mo_iv():
    """
    Sync MO/HO/IO IV data from Tushare for the latest trading day.
    Scheduled at 16:00 on trading days.
    """
    try:
        from tzdata_pkg.cli.daily_sync import sync_iv_daily

        trade_date = date.today().isoformat()
        result = sync_iv_daily(
            underlyings=['MO', 'HO', 'IO'],
            trade_date=trade_date,
        )

        total = sum(v.get('count', 0) for v in result.values() if isinstance(v, dict))
        errors = [k for k, v in result.items() if isinstance(v, dict) and v.get('status') == 'error']

        logger.info(f"MO IV sync completed: {total} records, errors: {errors}")
        return {
            'status': 'completed',
            'trade_date': trade_date,
            'total_records': total,
            'errors': errors,
            'details': result,
        }
    except Exception as e:
        logger.error(f"MO IV sync failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
        }


@celery_app.task
def sync_underlying_daily():
    """
    Sync underlying daily bar data (000852, IM, 512100, A00) from akshare/sina.
    Scheduled at 16:30 on trading days.
    """
    try:
        from tzdata_pkg.cli.daily_sync import sync_underlying_daily as _sync

        result = _sync(
            underlyings=['000852', 'IM', '512100', 'A00'],
            start_date=(date.today() - timedelta(days=7)).isoformat(),
            end_date=date.today().isoformat(),
        )

        total = sum(v.get('count', 0) for v in result.values() if isinstance(v, dict))
        errors = [k for k, v in result.items() if isinstance(v, dict) and v.get('status') == 'error']

        logger.info(f"Underlying daily sync completed: {total} records, errors: {errors}")
        return {
            'status': 'completed',
            'total_records': total,
            'errors': errors,
            'details': result,
        }
    except Exception as e:
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
    try:
        from tzdata_pkg.cli.sync_mo_contracts import sync_mo_contracts as _sync

        result = _sync(force=False)

        logger.info(f"MO contract sync completed: {result}")
        return {
            'status': 'completed',
            'inserted': result.get('inserted', 0),
            'updated': result.get('updated', 0),
            'total': result.get('total', 0),
        }
    except Exception as e:
        logger.error(f"MO contract sync failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
        }
