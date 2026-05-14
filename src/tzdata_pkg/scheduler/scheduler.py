"""APScheduler-based download scheduler for tz-data.

Configures and runs periodic download jobs:
  - CFFEX daily quotes at 18:00 (after market close)
  - CFFEX position data at 18:30
  - SHFE daily quotes at 19:00
  - CFMMC bills at 20:00
  - Data quality check at 02:00
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from tzdata_pkg.config import get_cffex_config, get_shfe_config, get_cfmmc_config

logger = logging.getLogger("tzdata.scheduler")


class TzDataScheduler:
    """Scheduler for periodic data downloads.

    Args:
        mode: "blocking" or "background"
        jobs: List of job configs (uses defaults if None)
    """

    DEFAULT_JOBS = [
        {
            "name": "cffex_daily",
            "func": "_job_cffex_daily",
            "trigger": "cron",
            "hour": 18, "minute": 0,
            "day_of_week": "mon-fri",
        },
        {
            "name": "cffex_position",
            "func": "_job_cffex_position",
            "trigger": "cron",
            "hour": 18, "minute": 30,
            "day_of_week": "mon-fri",
        },
        {
            "name": "shfe_daily",
            "func": "_job_shfe_daily",
            "trigger": "cron",
            "hour": 19, "minute": 0,
            "day_of_week": "mon-fri",
        },
        {
            "name": "cfmmc_bills",
            "func": "_job_cfmmc_bills",
            "trigger": "cron",
            "hour": 20, "minute": 0,
            "day_of_week": "mon-fri",
        },
        {
            "name": "data_quality",
            "func": "_job_data_quality",
            "trigger": "cron",
            "hour": 2, "minute": 0,
        },
    ]

    def __init__(self, mode: str = "blocking", jobs: list = None):
        self.mode = mode
        self.jobs = jobs or self.DEFAULT_JOBS

        if mode == "blocking":
            self._scheduler = BlockingScheduler()
        else:
            self._scheduler = BackgroundScheduler()

        self._scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        self._setup_jobs()

    def _setup_jobs(self):
        """Register all scheduled jobs."""
        for job in self.jobs:
            self._add_job(job)

    def _add_job(self, job_config: dict):
        """Add a single job to the scheduler."""
        name = job_config["name"]
        func_name = job_config["func"]

        # Map function names to actual methods
        func_map = {
            "_job_cffex_daily": self._job_cffex_daily,
            "_job_cffex_position": self._job_cffex_position,
            "_job_shfe_daily": self._job_shfe_daily,
            "_job_cfmmc_bills": self._job_cfmmc_bills,
            "_job_data_quality": self._job_data_quality,
        }

        func = func_map.get(func_name)
        if func is None:
            logger.warning(f"Unknown job function: {func_name}")
            return

        trigger = job_config.get("trigger", "cron")

        if trigger == "cron":
            self._scheduler.add_job(
                func,
                trigger="cron",
                id=name,
                name=job_config.get("name", name),
                hour=job_config.get("hour", 0),
                minute=job_config.get("minute", 0),
                day_of_week=job_config.get("day_of_week", "*"),
                replace_existing=True,
                misfire_grace_time=3600,
            )
        elif trigger == "interval":
            self._scheduler.add_job(
                func,
                trigger="interval",
                id=name,
                name=job_config.get("name", name),
                minutes=job_config.get("minutes", 60),
                replace_existing=True,
            )

        logger.info(f"Added job: {name} ({trigger})")

    def _job_listener(self, event):
        """Handle job execution events."""
        if event.exception:
            logger.error(
                f"Job {event.job_id} failed: {event.exception}\n"
                f"Traceback: {event.traceback}"
            )
        else:
            logger.info(f"Job {event.job_id} completed successfully")

    # ── Job implementations ─────────────────────────────────

    def _job_cffex_daily(self):
        """Download CFFEX daily data for all products."""
        logger.info("Starting CFFEX daily download job")
        config = get_cffex_config()
        from datetime import date

        for product in ["MO", "IM", "IC", "IF", "IH"]:
            try:
                from tzdata_pkg.download.cffex.unified_downloader import CFFEXUnifiedDownloader
                with CFFEXUnifiedDownloader(config, product=product, data_type="daily") as dl:
                    result = dl.download_incremental()
                    logger.info(f"CFFEX {product} daily: {result}")
            except Exception as e:
                logger.error(f"CFFEX {product} daily failed: {e}")

    def _job_cffex_position(self):
        """Download CFFEX position ranking data."""
        logger.info("Starting CFFEX position download job")
        config = get_cffex_config()
        from datetime import date

        for product in ["MO", "IM", "IC", "IF", "IH"]:
            try:
                from tzdata_pkg.download.cffex.unified_downloader import CFFEXUnifiedDownloader
                with CFFEXUnifiedDownloader(config, product=product, data_type="position") as dl:
                    result = dl.download_incremental()
                    logger.info(f"CFFEX {product} position: {result}")
            except Exception as e:
                logger.error(f"CFFEX {product} position failed: {e}")

    def _job_shfe_daily(self):
        """Download SHFE daily data."""
        logger.info("Starting SHFE daily download job")
        config = get_shfe_config()

        for product in ["AU", "AG", "CU", "AL", "ZN", "SN"]:
            try:
                from tzdata_pkg.download.shfe.daily_downloader import SHFEDailyDownloader
                dl = SHFEDailyDownloader()
                dl.download_daily([product], date.today() - timedelta(days=7), date.today())
                dl.close()
                logger.info(f"SHFE {product} daily: done")
            except Exception as e:
                logger.error(f"SHFE {product} daily failed: {e}")

    def _job_cfmmc_bills(self):
        """Download CFMMC bills."""
        logger.info("Starting CFMMC bill download job")
        config = get_cfmmc_config()
        from datetime import date

        try:
            from tzdata_pkg.download.cfmmc import CFMMCDownloader
            with CFMMCDownloader(config) as dl:
                result = dl.download_and_store(
                    start_date=date.today(),
                    end_date=date.today(),
                    auto=True,
                )
                logger.info(f"CFMMC bills: {result}")
        except Exception as e:
            logger.error(f"CFMMC bill download failed: {e}")

    def _job_data_quality(self):
        """Run data quality checks."""
        logger.info("Starting data quality check job")
        from tzdata_pkg.storage.db_registry import DBRegistry

        registry = DBRegistry()
        issues = []

        for db_name in ["market", "trading", "analysis"]:
            try:
                pool = registry.get_pool(db_name)
                with pool.connection() as conn:
                    tables = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                    for (table,) in tables:
                        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        if count == 0:
                            issues.append(f"{db_name}/{table}: EMPTY")
            except Exception as e:
                issues.append(f"{db_name}: connection error - {e}")

        if issues:
            logger.warning(f"Data quality issues: {issues}")
        else:
            logger.info("Data quality check passed: no issues")

    # ── Public API ──────────────────────────────────────────

    def start(self):
        """Start the scheduler."""
        logger.info(f"Starting scheduler in {self.mode} mode")
        logger.info(f"Scheduled jobs: {[j['name'] for j in self.jobs]}")
        self._scheduler.start()

    def shutdown(self, wait: bool = True):
        """Shutdown the scheduler."""
        logger.info("Shutting down scheduler")
        try:
            self._scheduler.shutdown(wait=wait)
        except Exception:
            pass  # Already stopped or not started

    def get_jobs(self) -> list:
        """Get list of scheduled jobs."""
        jobs = []
        for job in self._scheduler.get_jobs():
            try:
                nrt = job.next_run_time
            except AttributeError:
                nrt = None
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": str(nrt) if nrt else "pending",
                "trigger": str(job.trigger),
            })
        return jobs

    def run_now(self, job_name: str):
        """Run a specific job immediately."""
        job = self._scheduler.get_job(job_name)
        if job is None:
            raise ValueError(f"Job '{job_name}' not found")
        logger.info(f"Running job '{job_name}' immediately")
        job.func()
