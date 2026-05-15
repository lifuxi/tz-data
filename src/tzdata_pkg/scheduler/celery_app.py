"""
Celery application configuration for data maintenance tasks.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Celery configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Create Celery app
celery_app = Celery(
    'tzdata_maintenance',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,

    # Task execution settings
    task_track_started=True,
    task_time_limit=3600,  # 1 hour timeout
    task_soft_time_limit=3000,  # 50 minutes soft timeout

    # Retry settings
    task_autoretry_for=(Exception,),
    task_retry_backoff=True,
    task_retry_backoff_max=600,  # Max 10 minutes between retries
    task_max_retries=3,

    # Concurrency
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,

    # ============================================================
    # Beat periodic task schedule
    # ============================================================
    beat_schedule={
        # ============================================================
        # MO 系统数据同步（交易日）
        # ============================================================
        # 交易日 16:00 同步 MO IV 数据
        'mo-iv-sync': {
            'task': 'tzdata_pkg.scheduler.tasks.mo_tasks.sync_mo_iv',
            'schedule': crontab(hour=16, minute=0, day_of_week='mon-fri'),
        },

        # 交易日 16:30 同步标的日线数据（000852/IM/512100/A00）
        'mo-underlying-sync': {
            'task': 'tzdata_pkg.scheduler.tasks.mo_tasks.sync_underlying_daily',
            'schedule': crontab(hour=16, minute=30, day_of_week='mon-fri'),
        },

        # 每日 18:00 MO 数据质量检查
        'mo-quality-check': {
            'task': 'tzdata_pkg.scheduler.tasks.mo_tasks.mo_data_quality_check',
            'schedule': crontab(hour=18, minute=0),
        },

        # 每周六 10:00 MO 合约主表同步
        'mo-contract-sync': {
            'task': 'tzdata_pkg.scheduler.tasks.mo_tasks.sync_mo_contracts',
            'schedule': crontab(hour=10, minute=0, day_of_week='sat'),
        },

        # ============================================================
        # 通用数据维护任务
        # ============================================================
        # 每日 18:00 增量同步所有启用的数据目录
        'daily-incremental-sync': {
            'task': 'tzdata_pkg.scheduler.tasks.sync_tasks.daily_incremental_sync',
            'schedule': crontab(hour=18, minute=0),
        },

        # 每日 18:30 刷新本地/远程数据状态
        'daily-status-refresh': {
            'task': 'tzdata_pkg.scheduler.tasks.check_tasks.refresh_status_task',
            'schedule': crontab(hour=18, minute=30),
        },

        # 每日 19:00 数据完整性检查
        'daily-completeness-check': {
            'task': 'tzdata_pkg.scheduler.tasks.check_tasks.completeness_check_task',
            'schedule': crontab(hour=19, minute=0),
        },

        # 每日 20:00 账单缺失检测
        'daily-bill-missing-check': {
            'task': 'tzdata_pkg.scheduler.tasks.statement_tasks.check_missing_bills_task',
            'schedule': crontab(hour=20, minute=0),
        },

        # 交易日 21:00 账单日历驱动检查（新增）
        'daily-bill-calendar-check': {
            'task': 'tzdata_pkg.scheduler.tasks.bill_tasks.daily_bill_calendar_check',
            'schedule': crontab(hour=21, minute=0, day_of_week='mon-fri'),
        },

        # ============================================================
        # tz-data 数据层任务（Phase 5）
        # ============================================================
        # 每日 18:30 同步指数日线（000852/000300）
        'sync-index-daily': {
            'task': 'tzdata_pkg.scheduler.tasks.data_tasks.sync_index_daily',
            'schedule': crontab(hour=18, minute=30, day_of_week='mon-fri'),
        },

        # 每日 18:30 计算日频 VWAP
        'compute-daily-vwap': {
            'task': 'tzdata_pkg.scheduler.tasks.data_tasks.compute_daily_vwap',
            'schedule': crontab(hour=18, minute=35, day_of_week='mon-fri'),
        },

        # 每日 20:00 预计算期权希腊字母
        'compute-option-greeks': {
            'task': 'tzdata_pkg.scheduler.tasks.data_tasks.compute_option_greeks',
            'schedule': crontab(hour=20, minute=0),
        },
    },
)


def get_celery_app():
    """Get the Celery application instance."""
    return celery_app
