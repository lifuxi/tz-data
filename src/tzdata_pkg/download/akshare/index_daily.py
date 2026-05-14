"""
Index daily bar downloader for MO signal data.

Downloads CSI 1000 (000852) and CSI 500 (000905) index daily data via akshare,
stores into bills.db option_sim_underlying_daily table.
"""
import logging
import os
import sqlite3
from datetime import date
from typing import List, Dict, Any, Optional

import pandas as pd

from tzdata_pkg.download.base import BaseExchangeDownloader
from tzdata_pkg.download.download_result import DownloadResult
from tzdata_pkg.download.akshare.client import AkshareClient

logger = logging.getLogger(__name__)

# bills.db path — MO signal data uses bills.db, not tzdata_trading.db
BILLS_DB_PATH = os.environ.get("BILLS_DB_PATH", "C:/myspace/tz-data/data/bills.db")


class IndexDailyDownloader(BaseExchangeDownloader):
    """
    Download index daily bar data and store to option_sim_underlying_daily.

    Args:
        index_code: Index code without exchange prefix (e.g. '000852', '000905')
    """

    SOURCE_NAME = "index_daily"

    # Index code → akshare symbol mapping
    INDEX_SYMBOLS = {
        '000852': 'sh000852',  # CSI 1000
        '000905': 'sh000905',  # CSI 500
    }

    def __init__(self, index_code: str = '000852', config: dict = None):
        self.index_code = index_code
        self.config = config or {}
        self._client = AkshareClient()
        self._pool = None
        super().__init__(self.config)

    def _get_pool(self):
        """Lazy-init SQLite connection to bills.db."""
        if self._pool is None:
            self._pool = sqlite3.connect(BILLS_DB_PATH)
        return self._pool

    def download(self, start_date: date, end_date: date, **kwargs) -> List[DownloadResult]:
        """Download index daily bars from akshare."""
        results = []
        ak_symbol = self.INDEX_SYMBOLS.get(self.index_code, f"sh{self.index_code}")

        self.logger.info(f"Downloading {self.index_code} index daily: {start_date} -> {end_date}")
        df = self._client.fetch_index_daily(ak_symbol)

        if df is not None and not df.empty:
            # Filter by date range if applicable
            if 'date' in df.columns:
                sd = start_date.isoformat()
                ed = end_date.isoformat()
                # Ensure date column is string for comparison
                df = df.copy()
                df['date'] = df['date'].astype(str).str[:10]
                df = df[(df['date'] >= sd) & (df['date'] <= ed)]

            results.append(DownloadResult(
                success=True,
                url=f"akshare://index_daily/{self.index_code}",
                file_path=None,
                error=None,
                data_type="index_daily",
                trade_date=f"{start_date}-{end_date}",
                record_count=len(df),
            ))
        else:
            results.append(DownloadResult(
                success=True,
                url=f"akshare://index_daily/{self.index_code}",
                file_path=None,
                error=None,
                data_type="index_daily",
                trade_date=f"{start_date}-{end_date}",
                record_count=0,
            ))

        return results

    def store(self, results: List[DownloadResult], **kwargs) -> int:
        """Store index daily data to option_sim_underlying_daily."""
        total_stored = 0
        for result in results:
            if not result.success or result.record_count == 0:
                continue

            # Re-fetch data to store
            ak_symbol = self.INDEX_SYMBOLS.get(self.index_code, f"sh{self.index_code}")
            df = self._client.fetch_index_daily(ak_symbol)
            if df is not None and not df.empty:
                if 'date' in df.columns:
                    sd, ed = self._parse_date_range(result.trade_date)
                    df = df.copy()
                    df['date'] = df['date'].astype(str).str[:10]
                    df = df[(df['date'] >= sd) & (df['date'] <= ed)]
                total_stored += self._store_data(df)

        return total_stored

    def _store_data(self, df: pd.DataFrame) -> int:
        """Write index daily bars to option_sim_underlying_daily."""
        count = 0
        conn = self._get_pool()

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
                    self.index_code,
                    trade_date,
                    self._safe_float(row.get('open')),
                    self._safe_float(row.get('high')),
                    self._safe_float(row.get('low')),
                    self._safe_float(row.get('close')),
                    self._safe_float(row.get('volume')),
                ))
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to store index daily: {e}")

        conn.commit()
        self.logger.info(f"Stored {count} index bars for {self.index_code}")
        return count

    def close(self):
        if self._pool:
            self._pool.close()
        super().close()

    @staticmethod
    def _parse_date_range(date_str: str) -> tuple:
        # Format: "YYYY-MM-DD-YYYY-MM-DD" (from DownloadResult.trade_date)
        parts = str(date_str).split("-")
        if len(parts) == 6:
            return f"{parts[0]}-{parts[1]}-{parts[2]}", f"{parts[3]}-{parts[4]}-{parts[5]}"
        return date_str, date_str

    @staticmethod
    def _safe_float(val):
        try:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            return float(val)
        except Exception:
            return None
