"""
Celery application configuration for data maintenance tasks.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Celery configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')

# Create Celery app
celery_app = Celery(
    'tzdata_maintenance',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    beat_scheduler_lock='celery_beat_lock',
    beat_max_loop_interval=5,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,

    # Task execution settings
    task_track_started=True,
    task_time_limit=3600,  # 1 hour timeout
    task_soft_time_limit=3000,  # 50 minutes soft timeout

    # Concurrency
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,

    # Auto-discover task modules
    include=[
        'tzdata_pkg.scheduler.tasks.mo_tasks',
        'tzdata_pkg.scheduler.tasks.position_tasks',
        'tzdata_pkg.scheduler.tasks.market_env_tasks',
        'tzdata_pkg.scheduler.tasks.sync_tasks',
        'tzdata_pkg.scheduler.tasks.check_tasks',
        'tzdata_pkg.scheduler.tasks.statement_tasks',
        'tzdata_pkg.scheduler.tasks.bill_tasks',
        'tzdata_pkg.scheduler.tasks.data_tasks',
        'tzdata_pkg.scheduler.tasks.alert_tasks',
        # tz2.0 tasks (shared worker)
        'src.tasks.report_tasks',
        'src.tasks.analysis_tasks',
        'src.tasks.mo_signal_tasks',
        'src.infrastructure.mq.tasks',
    ],

    # ============================================================
    # Beat periodic task schedule
    # ============================================================
    beat_schedule={
        # ============================================================
        # MO 系统数据同步（交易日）
        # ============================================================
        # 交易日 15:30 MO 期权分钟数据同步
        'mo-minute-sync': {
            'task': 'tzdata_pkg.scheduler.tasks.mo_tasks.sync_mo_minute',
            'schedule': crontab(hour=15, minute=30, day_of_week='mon-fri'),
        },

        # 交易日 16:00 同步 MO IV 数据
        'mo-iv-sync': {
            'task': 'tzdata_pkg.scheduler.tasks.mo_tasks.sync_mo_iv',
            'schedule': crontab(hour=16, minute=0, day_of_week='mon-fri'),
        },

        # 交易日 16:30 同步标的日线数据（000852/IM/512100/A00/510050/510300）
        'mo-underlying-sync': {
            'task': 'tzdata_pkg.scheduler.tasks.mo_tasks.sync_underlying_daily',
            'schedule': crontab(hour=16, minute=30, day_of_week='mon-fri'),
        },

        # 交易日 17:00 MO Top20 持仓同步
        'mo-position-sync': {
            'task': 'tzdata_pkg.scheduler.tasks.position_tasks.sync_mo_position',
            'schedule': crontab(hour=17, minute=0, day_of_week='mon-fri'),
        },

        # 交易日 17:05 HO Top20 持仓同步
        'ho-position-sync': {
            'task': 'tzdata_pkg.scheduler.tasks.position_tasks.sync_ho_position',
            'schedule': crontab(hour=17, minute=5, day_of_week='mon-fri'),
        },

        # 交易日 17:10 IO Top20 持仓同步
        'io-position-sync': {
            'task': 'tzdata_pkg.scheduler.tasks.position_tasks.sync_io_position',
            'schedule': crontab(hour=17, minute=10, day_of_week='mon-fri'),
        },

        # 交易日 17:30 MO 市场环境分析
        'mo-market-env': {
            'task': 'tzdata_pkg.scheduler.tasks.market_env_tasks.compute_mo_market_env',
            'schedule': crontab(hour=17, minute=30, day_of_week='mon-fri'),
        },

        # 每日 18:00 MO 数据质量检查
        'mo-quality-check': {
            'task': 'tzdata_pkg.scheduler.tasks.mo_tasks.mo_data_quality_check',
            'schedule': crontab(hour=18, minute=0),
        },

        # 每周六 10:00 MO/HO/IO 合约主表同步
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

        # 每日 18:45 数据量对账（校正 total_records 漂移）
        'daily-reconcile-records': {
            'task': 'tzdata_pkg.scheduler.tasks.check_tasks.reconcile_catalog_records',
            'schedule': crontab(hour=18, minute=45),
        },

        # 每日 18:50 数据缺失检测（对比交易日历 vs 实际数据）
        'daily-gap-detection': {
            'task': 'tzdata_pkg.scheduler.tasks.check_tasks.detect_data_gaps',
            'schedule': crontab(hour=18, minute=50),
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

        # 每日 20:30 交易开平匹配
        'daily-trade-matching': {
            'task': 'tzdata_pkg.scheduler.tasks.statement_tasks.trade_matching_task',
            'schedule': crontab(hour=20, minute=30),
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

        # ============================================================
        # tz2.0 应用层任务
        # ============================================================
        # 每日 20:00 生成日报
        'tz2-generate-daily-report': {
            'task': 'src.tasks.report_tasks.generate_daily_report',
            'schedule': crontab(hour=20, minute=0),
        },
        # 每周五 20:00 生成周报
        'tz2-generate-weekly-report': {
            'task': 'src.tasks.report_tasks.generate_weekly_report',
            'schedule': crontab(hour=20, minute=0, day_of_week=5),
        },
        # 每日 08:00 数据质量报告
        'tz2-data-quality-daily': {
            'task': 'src.tasks.report_tasks.generate_data_quality_report',
            'schedule': crontab(hour=8, minute=0),
        },
        # 每日 02:00 清理过期缓存
        'tz2-cleanup-cache': {
            'task': 'src.tasks.analysis_tasks.cleanup_expired_cache',
            'schedule': crontab(hour=2, minute=0),
        },
        # 交易日 15:30 MO 每日信号 pipeline
        'tz2-mo-daily-pipeline': {
            'task': 'src.tasks.mo_signal_tasks.run_mo_daily_pipeline',
            'schedule': crontab(hour=15, minute=30, day_of_week='1-5'),
        },
        # 每周五 16:00 MO 周度回顾
        'tz2-mo-weekly-review': {
            'task': 'src.tasks.mo_signal_tasks.run_mo_weekly_review',
            'schedule': crontab(hour=16, minute=0, day_of_week=5),
        },
    },
)


def get_celery_app():
    """Get the Celery application instance."""
    return celery_app


# Import signal handlers (must be after celery_app is created so @task_failure.connect works)
import tzdata_pkg.scheduler.task_failure_handler  # noqa: E402, F401
