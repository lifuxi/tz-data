# -*- coding: utf-8 -*-
"""
CFFEX data downloader base class.

Handles network requests, retry logic, logging, checksum verification,
and SQLite storage.
"""

import requests
import sqlite3
import json
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from tzdata_pkg.download.download_result import DownloadResult
from tzdata_pkg.download.cffex.url_builder import CFFEXURLBuilder, CFFEXURLInfo
from tzdata_pkg.download.cffex.csv_parser import CFFEXCSVParser, CFFEXParseResult


class CFFEXDownloader(ABC):
    """CFFEX downloader base class."""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.url_builder = CFFEXURLBuilder(self.config.get("base_url", "http://www.cffex.com.cn/sj/"))
        self.csv_parser = CFFEXCSVParser()

        storage = self.config["storage"]
        self.csv_dir = Path(storage["csv_dir"])
        self.db_path = Path(storage["db_path"])
        self.log_dir = Path(storage["log_dir"])
        self.checksum_file = Path(storage["checksum_file"])

        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._setup_logging()
        self._init_database()
        self.checksums = {}
        self._load_checksums()

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.config.get("download", {}).get(
                "user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
        })

    def _setup_logging(self):
        log_file = self.log_dir / "cffex_download.log"
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.handlers = []
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _init_database(self):
        self.conn = sqlite3.connect(str(self.db_path), timeout=30)
        self.logger.info(f"Database connected: {self.db_path}")

    def _load_checksums(self):
        if self.checksum_file.exists():
            try:
                with open(self.checksum_file, "r", encoding="utf-8") as f:
                    self.checksums = json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load checksums: {e}")
                self.checksums = {}

    def _save_checksums(self):
        try:
            with open(self.checksum_file, "w", encoding="utf-8") as f:
                json.dump(self.checksums, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save checksums: {e}")

    def calculate_checksum(self, content: bytes) -> str:
        return hashlib.md5(content).hexdigest()

    def download_csv(self, url_info: CFFEXURLInfo, save_file: bool = True) -> DownloadResult:
        download_config = self.config.get("download", {})
        max_retries = download_config.get("max_retries", 3)
        retry_delays = download_config.get("retry_delays", [1, 2, 4])
        timeout = download_config.get("timeout", 30)

        for attempt in range(max_retries):
            try:
                self.logger.info(f"Downloading: {url_info.url}")
                response = self.session.get(url_info.url, timeout=timeout, stream=True)

                if response.status_code == 404:
                    return DownloadResult(
                        success=True, url=url_info.url, file_path=None,
                        error=None, data_type=url_info.data_type,
                        trade_date=url_info.trade_date, record_count=0,
                    )

                response.raise_for_status()
                content = response.content
                checksum = self.calculate_checksum(content)
                cache_key = f"{url_info.data_type}_{url_info.trade_date}"

                if self.checksums.get(cache_key) == checksum:
                    self.logger.info(f"File unchanged, skip: {cache_key}")

                self.checksums[cache_key] = checksum
                self._save_checksums()

                file_path = None
                if save_file and url_info.filename:
                    subdir = self.csv_dir / url_info.data_type
                    subdir.mkdir(parents=True, exist_ok=True)
                    file_path = subdir / url_info.filename
                    with open(file_path, "wb") as f:
                        f.write(content)
                    self.logger.info(f"Saved file: {file_path}")

                return DownloadResult(
                    success=True, url=url_info.url,
                    file_path=str(file_path) if file_path else None,
                    error=None, data_type=url_info.data_type,
                    trade_date=url_info.trade_date, record_count=0,
                )

            except requests.exceptions.Timeout:
                error = "Request timeout"
                self.logger.warning(f"Download failed (attempt {attempt+1}/{max_retries}): {error}")
            except requests.exceptions.ConnectionError as e:
                error = f"Connection error: {e}"
                self.logger.warning(f"Download failed (attempt {attempt+1}/{max_retries}): {error}")
            except requests.exceptions.HTTPError as e:
                error = f"HTTP error: {e}"
                self.logger.warning(f"Download failed (attempt {attempt+1}/{max_retries}): {error}")
            except Exception as e:
                error = f"Unknown error: {e}"
                self.logger.error(f"Download failed (attempt {attempt+1}/{max_retries}): {error}")

            if attempt < max_retries - 1:
                delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                self.logger.info(f"Waiting {delay}s before retry...")
                time.sleep(delay)

        return DownloadResult(
            success=False, url=url_info.url, file_path=None,
            error=error, data_type=url_info.data_type,
            trade_date=url_info.trade_date,
        )

    def parse_and_save(self, file_path: str, data_type: str, **kwargs) -> Tuple[int, Dict]:
        if not file_path or not Path(file_path).exists():
            return 0, {}
        result = self.csv_parser.parse_csv(file_path, data_type, **kwargs)
        if result.record_count == 0:
            return 0, result.stats
        count = self.save_to_database(result)
        return count, result.stats

    @abstractmethod
    def save_to_database(self, parse_result: CFFEXParseResult) -> int:
        pass

    @abstractmethod
    def create_tables(self, year: int):
        pass

    def get_latest_date(self, data_type: str, year: int = None) -> Optional[str]:
        table_name = self._get_table_name(data_type, year)
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT MAX(trade_date) FROM {table_name}")
            result = cursor.fetchone()
            if result and result[0]:
                return result[0]
        except Exception as e:
            self.logger.warning(f"Failed to get latest date: {e}")
        return None

    @abstractmethod
    def _get_table_name(self, data_type: str, year: int = None) -> str:
        pass

    def download_batch(self, data_type: str, start_date: date, end_date: date,
                       product: str = None, save_csv: bool = True) -> List[DownloadResult]:
        results = []
        if data_type == "monthly":
            year_month = start_date.strftime("%Y%m")
            url_info = self.url_builder.build_monthly_url(year_month)
            urls = [url_info]
        else:
            urls = self.url_builder.build_batch_urls(data_type, start_date, end_date, product)

        empty_count = 0
        empty_threshold = self.config.get("batch", {}).get("empty_file_threshold", 5)
        request_delay = self.config.get("download", {}).get("request_delay", 0.5)

        for i, url_info in enumerate(urls, 1):
            self.logger.info(f"[{i}/{len(urls)}] {url_info.trade_date}")
            result = self.download_csv(url_info, save_csv)

            if result.success:
                if result.file_path:
                    count, stats = self.parse_and_save(result.file_path, data_type, product=product)
                    result.record_count = count
                    empty_count = 0
                else:
                    empty_count += 1
                    if empty_count >= empty_threshold:
                        self.logger.warning(f"Consecutive {empty_count} empty files, stopping")
                        break
            else:
                empty_count += 1

            results.append(result)
            time.sleep(request_delay)

        return results

    def download_full(self, data_type: str, start_year: int, end_year: int = None,
                      product: str = None) -> Dict[str, Any]:
        end_year = end_year or datetime.now().year
        self.logger.info(f"Full download: {data_type}, {start_year}-{end_year}")

        for year in range(start_year, end_year + 1):
            self.create_tables(year)

        total_results = []
        for year in range(start_year, end_year + 1):
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
            if year == datetime.now().year:
                end_date = min(end_date, date.today())
            results = self.download_batch(data_type, start_date, end_date, product)
            total_results.extend(results)

        success_count = sum(1 for r in total_results if r.success)
        fail_count = sum(1 for r in total_results if not r.success)
        total_records = sum(r.record_count for r in total_results)

        stats = {
            "data_type": data_type, "start_year": start_year, "end_year": end_year,
            "total_files": len(total_results), "success_count": success_count,
            "fail_count": fail_count, "total_records": total_records,
        }
        self.logger.info(f"Full download complete: {stats}")
        return stats

    def download_incremental(self, data_type: str, product: str = None) -> Dict[str, Any]:
        self.logger.info(f"Incremental download: {data_type}")
        current_year = datetime.now().year
        self.create_tables(current_year)

        latest_date = self.get_latest_date(data_type, current_year)
        if latest_date:
            start_date = datetime.strptime(latest_date, "%Y-%m-%d").date() + timedelta(days=1)
        else:
            start_date = date(current_year, 1, 1)

        end_date = date.today()
        if start_date > end_date:
            self.logger.info("Data is up to date")
            return {"data_type": data_type, "status": "up_to_date", "total_files": 0, "total_records": 0}

        results = self.download_batch(data_type, start_date, end_date, product)
        success_count = sum(1 for r in results if r.success)
        total_records = sum(r.record_count for r in results)

        stats = {
            "data_type": data_type, "start_date": str(start_date), "end_date": str(end_date),
            "total_files": len(results), "success_count": success_count, "total_records": total_records,
        }
        self.logger.info(f"Incremental download complete: {stats}")
        return stats

    def close(self):
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed")
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
