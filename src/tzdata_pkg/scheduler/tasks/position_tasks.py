"""
Celery tasks for CFFEX position ranking sync (Top20 持仓).

Syncs daily member position data from CFFEX for MO/HO/IO products.
Data is written to both year-partitioned tables and the unified position_detail table.
"""
import logging
import sqlite3
from datetime import date

from tzdata_pkg.scheduler.celery_app import celery_app
from tzdata_pkg.maintenance.sync.audit_logger import get_audit_logger
from tzdata_pkg.config import TZDATA_MARKET_DB

logger = logging.getLogger(__name__)


def _sync_position_for_product(product: str) -> dict:
    """
    Sync position ranking data for a single product.

    Args:
        product: 'MO', 'HO', or 'IO'

    Returns:
        dict with sync results.
    """
    try:
        from tzdata_pkg.download.cffex.position_downloader import CFFEXPositionDownloader

        downloader = CFFEXPositionDownloader(product=product)
        try:
            result = downloader.download_incremental(save_csv=True)
            total_records = result.get('total_records', 0)

            # Sync latest day's data to unified position_detail table
            count = _sync_to_position_detail(product)

            return {
                'status': 'ok',
                'product': product,
                'partition_records': total_records,
                'unified_records': count,
            }
        finally:
            downloader.close()

    except Exception as e:
        logger.error(f"Position sync failed for {product}: {e}")
        return {'status': 'error', 'product': product, 'error': str(e)}


def _sync_to_position_detail(product: str) -> int:
    """
    Copy latest day's position data from year-partitioned table
    into the unified position_detail table.
    """
    try:
        from tzdata_pkg.download.cffex.position_downloader import CFFEXPositionDownloader

        downloader = CFFEXPositionDownloader(product=product)
        try:
            year = date.today().year
            table = downloader._get_table_name('position', year)

            # Check if table exists
            tables = downloader.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchall()
            if not tables:
                logger.info(f"Position table {table} does not exist, skipping")
                return 0

            # Get latest date from partitioned table
            row = downloader.conn.execute(
                f"SELECT MAX(trade_date) FROM {table}"
            ).fetchone()
            if not row or not row[0]:
                return 0
            latest_date = row[0]

            # Read all records for latest date
            rows = downloader.conn.execute(
                f"SELECT trade_date, instrument_id, product, member_name, rank, "
                f"long_volume, short_volume, long_change, short_change "
                f"FROM {table} WHERE trade_date = ?",
                (latest_date,)
            ).fetchall()

            if not rows:
                return 0

            # Write to unified position_detail table
            conn = sqlite3.connect(str(TZDATA_MARKET_DB))
            count = 0
            for r in rows:
                conn.execute("""
                    INSERT OR REPLACE INTO position_detail
                    (exchange, trade_date, contract_code, product, member_name,
                     rank, long_volume, short_volume, long_change, short_change, source)
                    VALUES ('CFFEX', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'cffex')
                """, (
                    r[0], r[1], r[2], r[3], r[4],
                    r[5] or 0, r[6] or 0, r[7], r[8],
                ))
                count += 1
            conn.commit()
            conn.close()

            logger.info(f"Synced {count} position records for {product} ({latest_date}) to position_detail")
            return count
        finally:
            downloader.close()

    except Exception as e:
        logger.error(f"Failed to sync {product} to position_detail: {e}")
        return 0


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
def sync_mo_position():
    """Sync MO Top20 position ranking. Scheduled at 17:00 on trading days."""
    audit = get_audit_logger()
    task_id = sync_mo_position.request.id if sync_mo_position.request.id else "sync_mo_position"

    if not _is_trading_day():
        logger.info(f"Skipping MO position sync: {date.today()} is not a CFFEX trading day")
        return {'status': 'skipped', 'reason': 'non-trading day'}

    audit.log_start(task_id, 'mo-position-sync', sync_mode='incremental',
                    exchange='CFFEX', product='MO')

    result = _sync_position_for_product('MO')

    if result['status'] == 'error':
        audit.log_failure(task_id, Exception(result.get('error', 'unknown')))
        from tzdata_pkg.scheduler.tasks.alert_tasks import send_sync_alert
        send_sync_alert(
            task_name='mo-position-sync', status='error',
            message=f"MO 持仓同步失败: {result.get('error')}",
            details=result,
        )
    else:
        audit.log_success(task_id, records_fetched=result.get('unified_records', 0))

    return result


@celery_app.task
def sync_ho_position():
    """Sync HO Top20 position ranking. Scheduled at 17:05 on trading days."""
    audit = get_audit_logger()
    task_id = sync_ho_position.request.id if sync_ho_position.request.id else "sync_ho_position"

    if not _is_trading_day():
        logger.info(f"Skipping HO position sync: {date.today()} is not a CFFEX trading day")
        return {'status': 'skipped', 'reason': 'non-trading day'}

    audit.log_start(task_id, 'ho-position-sync', sync_mode='incremental',
                    exchange='CFFEX', product='HO')

    result = _sync_position_for_product('HO')

    if result['status'] == 'error':
        audit.log_failure(task_id, Exception(result.get('error', 'unknown')))
        from tzdata_pkg.scheduler.tasks.alert_tasks import send_sync_alert
        send_sync_alert(
            task_name='ho-position-sync', status='error',
            message=f"HO 持仓同步失败: {result.get('error')}",
            details=result,
        )
    else:
        audit.log_success(task_id, records_fetched=result.get('unified_records', 0))

    return result


@celery_app.task
def sync_io_position():
    """Sync IO Top20 position ranking. Scheduled at 17:10 on trading days."""
    audit = get_audit_logger()
    task_id = sync_io_position.request.id if sync_io_position.request.id else "sync_io_position"

    if not _is_trading_day():
        logger.info(f"Skipping IO position sync: {date.today()} is not a CFFEX trading day")
        return {'status': 'skipped', 'reason': 'non-trading day'}

    audit.log_start(task_id, 'io-position-sync', sync_mode='incremental',
                    exchange='CFFEX', product='IO')

    result = _sync_position_for_product('IO')

    if result['status'] == 'error':
        audit.log_failure(task_id, Exception(result.get('error', 'unknown')))
        from tzdata_pkg.scheduler.tasks.alert_tasks import send_sync_alert
        send_sync_alert(
            task_name='io-position-sync', status='error',
            message=f"IO 持仓同步失败: {result.get('error')}",
            details=result,
        )
    else:
        audit.log_success(task_id, records_fetched=result.get('unified_records', 0))

    return result
