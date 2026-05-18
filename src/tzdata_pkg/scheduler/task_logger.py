"""Beat task execution logger.

Decorator that records Celery Beat task execution results to beat_task_log table.
Usage: wrap a Celery task function to automatically log start time, duration, status.
"""
import functools
import logging
import time

logger = logging.getLogger(__name__)


def log_beat_task(func):
    """Decorator to log Beat task execution to beat_task_log table."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        task_name = func.__name__
        scheduled_at = time.strftime('%Y-%m-%d %H:%M:%S')
        start_ms = int(time.time() * 1000)
        status = 'success'
        error = None

        try:
            result = func(*args, **kwargs)
            if isinstance(result, dict) and result.get('status') == 'failed':
                status = 'failed'
                error = result.get('error', 'unknown')
            return result
        except Exception as e:
            status = 'failed'
            error = str(e)[:500]
            raise
        finally:
            end_ms = int(time.time() * 1000)
            duration_ms = end_ms - start_ms
            _write_log(task_name, scheduled_at, status, duration_ms, error)

    return wrapper


def _write_log(task_name: str, scheduled_at: str, status: str,
               duration_ms: int, error: str | None):
    """Write execution log to beat_task_log table."""
    try:
        import sqlite3
        from tzdata_pkg.config import TZDATA_TRADING_DB
        conn = sqlite3.connect(str(TZDATA_TRADING_DB))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS beat_task_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms INTEGER,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT INTO beat_task_log
                    (task_name, scheduled_at, status, duration_ms, error)
                VALUES (?, ?, ?, ?, ?)
            """, (task_name, scheduled_at, status, duration_ms, error))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"Failed to write beat_task_log: {e}")
