"""
Celery tasks for data synchronization.
"""
import logging
from datetime import date
from tzdata_pkg.scheduler.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def sync_catalog_task(self, catalog_id: int, mode: str = 'incremental'):
    """
    Sync a specific data catalog.

    Args:
        catalog_id: ID of the data catalog to sync
        mode: 'incremental' or 'full'
    """
    from tzdata_pkg.maintenance.sync.audit_logger import get_audit_logger

    task_id = self.request.id
    audit = get_audit_logger()

    try:
        from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

        catalog = CatalogManager.get_catalog(catalog_id)
        catalog_name = catalog.get('catalog_name', f'catalog-{catalog_id}') if catalog else ''

        audit.log_start(
            task_id=task_id,
            task_name=f"sync_catalog_task (id={catalog_id})",
            sync_mode=mode,
            exchange=catalog.get('exchange_code', '') if catalog else '',
            product=catalog.get('product_code', '') if catalog else '',
        )

        from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine

        # Create engine with task_id for checkpoint management
        engine = SyncEngine(
            catalog_id=catalog_id,
            mode=mode,
            task_id=task_id
        )

        result = engine.execute()

        if result.success:
            audit.log_success(task_id, records_fetched=result.records_fetched)
        else:
            audit.log_failure(task_id, Exception(result.error_message or 'Unknown error'),
                            records_fetched=result.records_fetched)

        return {
            'success': result.success,
            'catalog_id': result.catalog_id,
            'records_fetched': result.records_fetched,
            'batches_completed': result.batches_completed,
            'total_batches': result.total_batches,
            'progress_pct': result.progress_pct,
            'duration_seconds': result.duration_seconds,
            'error_message': result.error_message
        }

    except Exception as exc:
        audit.log_failure(task_id, exc)
        logger.error(f"Sync task failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task
def daily_incremental_sync():
    """
    Daily incremental sync for all enabled catalogs.
    Executes at 18:00 daily via Celery Beat.
    """
    from tzdata_pkg.maintenance.sync.audit_logger import get_audit_logger

    audit = get_audit_logger()
    task_id = daily_incremental_sync.request.id if daily_incremental_sync.request else 'daily-incremental'

    try:
        from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

        catalogs = CatalogManager.get_enabled_catalogs()
        if not catalogs:
            audit.log_start(task_id=task_id, task_name='daily_incremental_sync', sync_mode='incremental')
            audit.log_success(task_id, records_fetched=0)
            return {
                'status': 'completed',
                'message': 'No enabled catalogs to sync',
                'synced': 0
            }

        audit.log_start(
            task_id=task_id,
            task_name='daily_incremental_sync',
            sync_mode='incremental',
        )

        task_ids = []
        for catalog in catalogs:
            task = sync_catalog_task.delay(catalog['id'], mode='incremental')
            task_ids.append(task.id)
            logger.info(f"Queued incremental sync for catalog {catalog['id']}: {catalog['catalog_name']}")

        audit.log_success(task_id, records_fetched=len(task_ids))

        return {
            'status': 'queued',
            'synced': len(task_ids),
            'task_ids': task_ids
        }

    except Exception as e:
        audit.log_failure(task_id, e)
        logger.error(f"Daily incremental sync failed: {e}")
        return {
            'status': 'failed',
            'error': str(e)
        }


@celery_app.task(bind=True, max_retries=3)
def full_sync_task(self, catalog_id: int, start_date: str, end_date: str):
    """
    Full sync for a specific date range.

    Args:
        catalog_id: ID of the data catalog
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    from tzdata_pkg.maintenance.sync.audit_logger import get_audit_logger

    task_id = self.request.id
    audit = get_audit_logger()

    try:
        from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

        catalog = CatalogManager.get_catalog(catalog_id)
        catalog_name = catalog.get('catalog_name', f'catalog-{catalog_id}') if catalog else ''

        audit.log_start(
            task_id=task_id,
            task_name=f"full_sync_task (id={catalog_id})",
            sync_mode='full',
            exchange=catalog.get('exchange_code', '') if catalog else '',
            product=catalog.get('product_code', '') if catalog else '',
            trade_date=f"{start_date}~{end_date}",
        )

        from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine
        from datetime import datetime

        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        engine = SyncEngine(
            catalog_id=catalog_id,
            mode='full',
            task_id=task_id
        )

        # Override the date range calculation for full sync
        engine._calculate_full_range = lambda: (start, end)

        result = engine.execute()

        if result.success:
            audit.log_success(task_id, records_fetched=result.records_fetched)
        else:
            audit.log_failure(task_id, Exception(result.error_message or 'Unknown error'),
                            records_fetched=result.records_fetched)

        return {
            'success': result.success,
            'catalog_id': result.catalog_id,
            'records_fetched': result.records_fetched,
            'batches_completed': result.batches_completed,
            'total_batches': result.total_batches,
            'progress_pct': result.progress_pct,
            'duration_seconds': result.duration_seconds,
            'error_message': result.error_message
        }

    except Exception as exc:
        audit.log_failure(task_id, exc)
        logger.error(f"Full sync task failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
