"""
ETF daily bar downloader for MO signal data.

Downloads CSI 1000 ETF (512100) daily data via akshare,
stores into bills.db option_sim_underlying_daily table.
"""
import logging
import os
import sqlite3
from datetime import date
from typing import List

import pandas as pd

from tzdata_pkg.download.base import BaseExchangeDownloader
from tzdata_pkg.download.download_result import DownloadResult
from tzdata_pkg.download.akshare.client import AkshareClient

logger = logging.getLogger(__name__)

BILLS_DB_PATH = os.environ.get("BILLS_DB_PATH", "C:/myspace/tz-data/data/bills.db")

# ETF Chinese column names → standard names
ETF_COL_MAP = {
    '日期': 'date',
    '开盘': 'open',
    '最高': 'high',
    '最低': 'low',
    '收盘': 'close',
    '成交量': 'volume',
    '成交额': 'amount',
}


class EtfDailyDownloader(BaseExchangeDownloader):
    """
    Download ETF daily bar data and store to option_sim_underlying_daily.

    Args:
        etf_code: ETF code (e.g. '512100' for CSI 1000 ETF)
    """

    SOURCE_NAME = "etf_daily"

    def __init__(self, etf_code: str = '512100', config: dict = None):
        self.etf_code = etf_code
        self.config = config or {}
        self._client = AkshareClient()
        self._pool = None
        super().__init__(self.config)

    def _get_pool(self):
        if self._pool is None:
            self._pool = sqlite3.connect(BILLS_DB_PATH)
        return self._pool

    def download(self, start_date: date, end_date: date, **kwargs) -> List[DownloadResult]:
        """Download ETF daily bars from akshare."""
        results = []
        sd = start_date.strftime("%Y%m%d")
        ed = end_date.strftime("%Y%m%d")

        self.logger.info(f"Downloading {self.etf_code} ETF daily: {sd} -> {ed}")
        df = self._client.fetch_etf_daily(self.etf_code, start_date=sd, end_date=ed)

        if df is not None and not df.empty:
            results.append(DownloadResult(
                success=True,
                url=f"akshare://etf_daily/{self.etf_code}",
                file_path=None,
                error=None,
                data_type="etf_daily",
                trade_date=f"{sd}-{ed}",
                record_count=len(df),
            ))
        else:
            results.append(DownloadResult(
                success=True,
                url=f"akshare://etf_daily/{self.etf_code}",
                file_path=None,
                error=None,
                data_type="etf_daily",
                trade_date=f"{sd}-{ed}",
                record_count=0,
            ))

        return results

    def store(self, results: List[DownloadResult], **kwargs) -> int:
        """Store ETF daily data to option_sim_underlying_daily."""
        total_stored = 0
        for result in results:
            if not result.success or result.record_count == 0:
                continue

            sd, ed = self._parse_date_range(result.trade_date)
            df = self._client.fetch_etf_daily(self.etf_code, start_date=sd, end_date=ed)
            if df is not None and not df.empty:
                total_stored += self._store_data(df)

        return total_stored

    def _store_data(self, df: pd.DataFrame) -> int:
        """Write ETF daily bars to option_sim_underlying_daily."""
        count = 0
        conn = self._get_pool()

        # Normalize column names (Chinese → English)
        df = df.rename(columns=ETF_COL_MAP)

        for _, row in df.iterrows():
            try:
                trade_date = str(row.get('date', ''))[:10]
                if not trade_date:
                    continue

                conn.execute("""
                    INSERT OR REPLACE INTO option_sim_underlying_daily
                    (underlying, trade_date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.etf_code,
                    trade_date,
                    self._safe_float(row.get('open')),
                    self._safe_float(row.get('high')),
                    self._safe_float(row.get('low')),
                    self._safe_float(row.get('close')),
                    self._safe_float(row.get('volume')),
                ))
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to store ETF daily: {e}")

        conn.commit()
        self.logger.info(f"Stored {count} ETF bars for {self.etf_code}")
        return count

    def close(self):
        if self._pool:
            self._pool.close()
        super().close()

    @staticmethod
    def _parse_date_range(date_str: str) -> tuple:
        # Format: "YYYYMMDD-YYYYMMDD" or "YYYY-MM-DD-YYYY-MM-DD"
        parts = str(date_str).split("-")
        if len(parts) == 6:
            return f"{parts[0]}-{parts[1]}-{parts[2]}", f"{parts[3]}-{parts[4]}-{parts[5]}"
        elif len(parts) == 3 and len(parts[0]) == 8:
            # YYYYMMDD-YYYYMMDD → the middle - splits into 3 parts
            # Actually: "20250101-20250131" splits into ["20250101", "20250131"]
            pass
        # For YYYYMMDD-YYYYMMDD format (2 parts after split)
        if len(parts) == 2:
            return parts[0], parts[1]
        return date_str, date_str

    @staticmethod
    def _safe_float(val):
        try:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            return float(val)
        except Exception:
            return None
