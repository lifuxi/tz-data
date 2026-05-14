# -*- coding: utf-8 -*-
"""MO (CSI 1000 options) specialized downloader."""

import logging
from datetime import date, datetime
from typing import Dict, Any, List, Optional

from tzdata_pkg.download.cffex.daily_downloader import CFFEXDailyDownloader
from tzdata_pkg.download.cffex.position_downloader import CFFEXPositionDownloader
from tzdata_pkg.config import get_cffex_config


class CFFEXMODownloader:
    """MO (CSI 1000 options) specialized downloader."""

    DATA_TYPES = ["daily", "weekly", "monthly", "position"]

    def __init__(self, config: dict = None, product: str = "MO"):
        self.config = config or get_cffex_config()
        self.product = product
        self.daily_downloader = CFFEXDailyDownloader(self.config, "daily", product)
        self.weekly_downloader = CFFEXDailyDownloader(self.config, "weekly", product)
        self.monthly_downloader = CFFEXDailyDownloader(self.config, "monthly", product)
        self.position_downloader = CFFEXPositionDownloader(self.config, product)
        self.logger = logging.getLogger("CFFEXMODownloader")
        self.conn = self.daily_downloader.conn

    def create_all_tables(self, year: int):
        self.logger.info(f"Creating {year} tables...")
        self.daily_downloader.create_tables(year)
        self.weekly_downloader.create_tables(year)
        self.monthly_downloader.create_tables(year)
        self.position_downloader.create_tables(year)
        self.logger.info("Tables created")

    def download_daily(self, start_date: date, end_date: date = None,
                       save_csv: bool = True) -> Dict[str, Any]:
        end_date = end_date or date.today()
        self.logger.info(f"Downloading daily: {start_date} - {end_date}")
        results = self.daily_downloader.download_batch("daily", start_date, end_date, save_csv=save_csv)
        return self._summarize_results(results, "daily")

    def download_weekly(self, start_date: date, end_date: date = None,
                        save_csv: bool = True) -> Dict[str, Any]:
        end_date = end_date or date.today()
        self.logger.info(f"Downloading weekly: {start_date} - {end_date}")
        results = self.weekly_downloader.download_batch("weekly", start_date, end_date, save_csv=save_csv)
        return self._summarize_results(results, "weekly")

    def download_monthly(self, start_year: int, end_year: int = None) -> Dict[str, Any]:
        end_year = end_year or datetime.now().year
        self.logger.info(f"Downloading monthly: {start_year} - {end_year}")
        for year in range(start_year, end_year + 1):
            self.monthly_downloader.create_tables(year)
        results = self.monthly_downloader.download_batch(
            "monthly", date(start_year, 1, 1), date(end_year, 12, 31), save_csv=True
        )
        return self._summarize_results(results, "monthly")

    def download_position(self, start_date: date, end_date: date = None,
                          save_csv: bool = True) -> Dict[str, Any]:
        end_date = end_date or date.today()
        self.logger.info(f"Downloading position: {start_date} - {end_date}")
        results = self.position_downloader.download_batch(
            "position", start_date, end_date, product=self.product, save_csv=save_csv
        )
        return self._summarize_results(results, "position")

    def download_full(self, data_types: List[str] = None, start_year: int = None,
                      end_year: int = None) -> Dict[str, Any]:
        data_types = data_types or self.DATA_TYPES
        start_year = start_year or self.config.get("partition", {}).get("start_year", 2024)
        end_year = end_year or datetime.now().year
        self.logger.info(f"Full download: {data_types}, {start_year}-{end_year}")
        stats = {}
        for data_type in data_types:
            try:
                if data_type == "daily":
                    result = self.daily_downloader.download_full("daily", start_year, end_year)
                elif data_type == "weekly":
                    result = self.weekly_downloader.download_full("weekly", start_year, end_year)
                elif data_type == "monthly":
                    result = self.download_monthly(start_year, end_year)
                elif data_type == "position":
                    result = self.position_downloader.download_incremental("position")
                else:
                    self.logger.warning(f"Unknown data type: {data_type}")
                    continue
                stats[data_type] = result
            except Exception as e:
                self.logger.error(f"{data_type} download failed: {e}")
                stats[data_type] = {"error": str(e)}
        return {
            "data_types": data_types, "start_year": start_year, "end_year": end_year,
            "details": stats,
            "total_records": sum(s.get("total_records", 0) for s in stats.values() if isinstance(s, dict)),
        }

    def download_incremental(self, data_types: List[str] = None) -> Dict[str, Any]:
        data_types = data_types or self.DATA_TYPES
        self.logger.info(f"Incremental download: {data_types}")
        stats = {}
        for data_type in data_types:
            try:
                if data_type in ("daily", "weekly"):
                    result = getattr(self, f"{data_type}_downloader").download_incremental(data_type)
                elif data_type == "monthly":
                    result = self.monthly_downloader.download_batch(
                        "monthly", date.today(), date.today(), save_csv=True
                    )
                    result = self._summarize_results(result, "monthly")
                elif data_type == "position":
                    result = self.position_downloader.download_incremental("position")
                else:
                    continue
                stats[data_type] = result
            except Exception as e:
                self.logger.error(f"{data_type} download failed: {e}")
                stats[data_type] = {"error": str(e)}
        return {
            "data_types": data_types,
            "download_time": datetime.now().isoformat(),
            "details": stats,
            "total_records": sum(s.get("total_records", 0) for s in stats.values() if isinstance(s, dict)),
        }

    def _summarize_results(self, results: list, data_type: str) -> Dict[str, Any]:
        if not results:
            return {"data_type": data_type, "total_files": 0, "success_count": 0, "fail_count": 0, "total_records": 0}
        return {
            "data_type": data_type,
            "total_files": len(results),
            "success_count": sum(1 for r in results if r.success),
            "fail_count": sum(1 for r in results if not r.success),
            "total_records": sum(getattr(r, "record_count", 0) for r in results),
        }

    def get_data_status(self) -> Dict[str, Any]:
        current_year = datetime.now().year
        status = {}
        for data_type in ["daily", "weekly", "monthly", "position"]:
            if data_type == "monthly":
                latest = self.monthly_downloader.get_latest_date("monthly", current_year)
            elif data_type == "position":
                latest = self.position_downloader.get_latest_date("position", current_year)
            else:
                latest = getattr(self, f"{data_type}_downloader").get_latest_date(data_type, current_year)
            status[data_type] = {
                "latest_date": latest,
                "status": "up_to_date" if latest == str(date.today()) else "need_update",
            }
        return status

    def close(self):
        self.daily_downloader.close()
        self.weekly_downloader.close()
        self.monthly_downloader.close()
        self.position_downloader.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def download_mo_data(mode: str = "incremental", data_types: List[str] = None,
                     start_year: int = None) -> Dict[str, Any]:
    with CFFEXMODownloader() as downloader:
        if mode == "full":
            return downloader.download_full(data_types, start_year)
        else:
            return downloader.download_incremental(data_types)
