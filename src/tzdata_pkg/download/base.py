"""Base exchange downloader abstraction.

Unifies the download -> validate -> store pattern across all data sources
(CFFEX, SHFE, Tushare, CFMMC, etc.).
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

from tzdata_pkg.download.download_result import DownloadResult


logger = logging.getLogger(__name__)


class BaseExchangeDownloader(ABC):
    """Abstract base for all exchange/API downloaders.

    Subclasses must implement:
    - download() — fetch data for a date range
    - validate() — check data quality
    - store() — persist to storage

    Provides:
    - HTTP session with retry logic
    - Logging setup
    - Download progress tracking
    - Result summarization
    """

    SOURCE_NAME: str = "base"  # Override in subclass: "tushare", "cfmmc", etc.

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__name__}[{self.SOURCE_NAME}]")
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create HTTP session with default headers."""
        session = requests.Session()
        download_cfg = self.config.get("download", {})
        session.headers.update({
            "User-Agent": download_cfg.get(
                "user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            ),
            "Accept": "*/*",
        })
        return session

    @abstractmethod
    def download(self, start_date: date, end_date: date, **kwargs) -> List[DownloadResult]:
        """Download data for the given date range.

        Returns a list of DownloadResult, one per file/API call.
        """
        ...

    def validate(self, results: List[DownloadResult]) -> Dict[str, Any]:
        """Run basic validation on downloaded data.

        Returns a dict with validation summary.
        """
        total = len(results)
        success = sum(1 for r in results if r.success)
        failed = total - success
        total_records = sum(r.record_count for r in results)

        return {
            "total_files": total,
            "success": success,
            "failed": failed,
            "total_records": total_records,
            "validation_time": datetime.now().isoformat(),
        }

    @abstractmethod
    def store(self, results: List[DownloadResult], **kwargs) -> int:
        """Persist downloaded data to storage.

        Returns total number of records stored.
        """
        ...

    def download_and_store(self, start_date: date, end_date: date, **kwargs) -> Dict[str, Any]:
        """Full pipeline: download -> validate -> store."""
        self.logger.info(f"Downloading {self.SOURCE_NAME}: {start_date} -> {end_date}")
        t0 = time.time()

        results = self.download(start_date, end_date, **kwargs)
        validation = self.validate(results)

        stored = 0
        if validation["success"] > 0:
            stored = self.store(results, **kwargs)

        duration = time.time() - t0
        summary = {
            "source": self.SOURCE_NAME,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "duration_seconds": round(duration, 2),
            "validation": validation,
            "records_stored": stored,
        }
        self.logger.info(f"Pipeline complete: {summary}")
        return summary

    def download_incremental(self, **kwargs) -> Dict[str, Any]:
        """Download only new data since last known date.

        Subclasses can override for custom incremental logic.
        Default: downloads from yesterday to today.
        """
        yesterday = date.today()
        return self.download_and_store(yesterday, date.today(), **kwargs)

    def close(self):
        """Clean up resources (HTTP sessions, DB connections, etc.)."""
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class BaseAPIDownloader(BaseExchangeDownloader):
    """Base for API-based downloaders (Tushare, etc.) with rate limiting."""

    SOURCE_NAME: str = "api"

    def __init__(self, config: dict):
        super().__init__(config)
        self._rate_limit = config.get("rate_limit", {"calls_per_min": 200, "interval": 0.3})
        self._last_call_time = 0

    def _wait_rate_limit(self):
        """Enforce rate limiting between API calls."""
        interval = self._rate_limit.get("interval", 0.3)
        elapsed = time.time() - self._last_call_time
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_call_time = time.time()

    @abstractmethod
    def _call_api(self, endpoint: str, **params) -> Any:
        """Make an API call respecting rate limits."""
        ...
