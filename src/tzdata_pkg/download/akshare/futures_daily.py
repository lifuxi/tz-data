"""
IM futures daily bar downloader for MO signal data.

Downloads IM (中证1000股指期货) main contract daily data via akshare,
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


class FuturesDailyDownloader(BaseExchangeDownloader):
    """
    Download IM futures daily bar data and store to option_sim_underlying_daily.

    Args:
        product: Futures product code (e.g. 'IM' — resolves to 'IM0' main contract)
    """

    SOURCE_NAME = "futures_daily"

    # Product → akshare symbol mapping (main contract continuous)
    PRODUCT_SYMBOLS = {
        'IM': 'IM0',    # IM main contract
        'IC': 'IC0',    # IC main contract (for relative strength)
    }

    def __init__(self, product: str = 'IM', config: dict = None):
        self.product = product
        self.config = config or {}
        self._client = AkshareClient()
        self._pool = None
        super().__init__(self.config)

    def _get_pool(self):
        if self._pool is None:
            self._pool = sqlite3.connect(BILLS_DB_PATH)
        return self._pool

    def download(self, start_date: date, end_date: date, **kwargs) -> List[DownloadResult]:
        """Download IM futures daily bars from akshare."""
        results = []
        ak_symbol = self.PRODUCT_SYMBOLS.get(self.product, f"{self.product}0")

        self.logger.info(f"Downloading {self.product} futures daily: {start_date} -> {end_date}")
        df = self._client.fetch_futures_daily(ak_symbol)

        if df is not None and not df.empty:
            if 'date' in df.columns:
                sd = start_date.isoformat()
                ed = end_date.isoformat()
                df = df.copy()
                df['date'] = df['date'].astype(str).str[:10]
                df = df[(df['date'] >= sd) & (df['date'] <= ed)]

            results.append(DownloadResult(
                success=True,
                url=f"akshare://futures_daily/{self.product}",
                file_path=None,
                error=None,
                data_type="futures_daily",
                trade_date=f"{start_date}-{end_date}",
                record_count=len(df),
            ))
        else:
            results.append(DownloadResult(
                success=True,
                url=f"akshare://futures_daily/{self.product}",
                file_path=None,
                error=None,
                data_type="futures_daily",
                trade_date=f"{start_date}-{end_date}",
                record_count=0,
            ))

        return results

    def store(self, results: List[DownloadResult], **kwargs) -> int:
        """Store futures daily data to option_sim_underlying_daily."""
        total_stored = 0
        for result in results:
            if not result.success or result.record_count == 0:
                continue

            ak_symbol = self.PRODUCT_SYMBOLS.get(self.product, f"{self.product}0")
            df = self._client.fetch_futures_daily(ak_symbol)
            if df is not None and not df.empty:
                if 'date' in df.columns:
                    sd, ed = self._parse_date_range(result.trade_date)
                    df = df.copy()
                    df['date'] = df['date'].astype(str).str[:10]
                    df = df[(df['date'] >= sd) & (df['date'] <= ed)]
                total_stored += self._store_data(df)

        return total_stored

    def _store_data(self, df: pd.DataFrame) -> int:
        """Write futures daily bars to option_sim_underlying_daily."""
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
                    self.product,  # e.g. 'IM' (not 'IM0')
                    trade_date,
                    self._safe_float(row.get('open')),
                    self._safe_float(row.get('high')),
                    self._safe_float(row.get('low')),
                    self._safe_float(row.get('close')),
                    self._safe_float(row.get('volume')),
                ))
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to store futures daily: {e}")

        conn.commit()
        self.logger.info(f"Stored {count} futures bars for {self.product}")
        return count

    def close(self):
        if self._pool:
            self._pool.close()
        super().close()

    @staticmethod
    def _parse_date_range(date_str: str) -> tuple:
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
