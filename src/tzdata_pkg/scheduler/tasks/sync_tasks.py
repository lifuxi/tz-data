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
    try:
        from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine

        # Create engine with task_id for checkpoint management
        task_id = self.request.id
        engine = SyncEngine(
            catalog_id=catalog_id,
            mode=mode,
            task_id=task_id
        )

        result = engine.execute()

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
        logger.error(f"Sync task failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task
def daily_incremental_sync():
    """
    Daily incremental sync for all enabled catalogs.
    Executes at 18:00 daily via Celery Beat.
    """
    try:
        from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager

        catalogs = CatalogManager.get_enabled_catalogs()
        if not catalogs:
            return {
                'status': 'completed',
                'message': 'No enabled catalogs to sync',
                'synced': 0
            }

        task_ids = []
        for catalog in catalogs:
            task = sync_catalog_task.delay(catalog['id'], mode='incremental')
            task_ids.append(task.id)
            logger.info(f"Queued incremental sync for catalog {catalog['id']}: {catalog['catalog_name']}")

        return {
            'status': 'queued',
            'synced': len(task_ids),
            'task_ids': task_ids
        }

    except Exception as e:
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
    try:
        from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine
        from datetime import datetime

        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        engine = SyncEngine(
            catalog_id=catalog_id,
            mode='full',
            task_id=self.request.id
        )

        # Override the date range calculation for full sync
        engine._calculate_full_range = lambda: (start, end)

        result = engine.execute()

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
        logger.error(f"Full sync task failed: {exc}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
