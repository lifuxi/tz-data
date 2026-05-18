"""
Index daily bar downloader for MO signal data.

Downloads CSI 1000 (000852) and CSI 500 (000905) index daily data via akshare,
stores into bills.db option_sim_underlying_daily table.
"""
import logging
import os
import sqlite3
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd

from tzdata_pkg.download.base import BaseExchangeDownloader
from tzdata_pkg.download.download_result import DownloadResult
from tzdata_pkg.download.akshare.client import AkshareClient

logger = logging.getLogger(__name__)

# bills.db path — MO signal data uses tzdata_trading.db (bills table)
BILLS_DB_PATH = os.environ.get("BILLS_DB_PATH", "C:/myspace/tz-data/data/tzdata_trading.db")


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

    def _fetch_with_fallback(self, ak_symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Try Tushare first, fallback to akshare on failure."""
        # Primary: Tushare index_daily
        try:
            from tzdata_pkg.config import get_tushare_config
            from tzdata_pkg.download.tushare.client import TushareClient

            tushare_cfg = get_tushare_config()
            client = TushareClient(token=tushare_cfg["token"])
            ts_code = f"{self.index_code}.SH"

            self.logger.info(f"Trying Tushare for {self.index_code}...")
            sd = start_date.strftime("%Y%m%d")
            ed = end_date.strftime("%Y%m%d")

            # Tushare doesn't have a direct index_daily API for SH/SZ indices,
            # so we use the fut_daily for futures indices or fall through to akshare.
            # For index codes like 000852, we need to use index_daily from Tushare Pro.
            df = client.pro.index_daily(
                ts_code=ts_code,
                start_date=sd,
                end_date=ed,
                fields="ts_code,trade_date,open,high,low,close,vol"
            )
            if df is not None and not df.empty:
                # Normalize column names
                df = df.rename(columns={"vol": "volume", "trade_date": "date"})
                self.logger.info(f"Tushare returned {len(df)} rows for {self.index_code}")
                return df
            self.logger.warning(f"Tushare returned empty data for {self.index_code}")
        except Exception as e:
            self.logger.warning(f"Tushare failed for {self.index_code}: {e}, falling back to akshare")

        # Fallback: akshare
        self.logger.info(f"Fallback to akshare for {self.index_code}...")
        return self._client.fetch_index_daily(ak_symbol)

    def download(self, start_date: date, end_date: date, **kwargs) -> List[DownloadResult]:
        """Download index daily bars, Tushare primary with akshare fallback."""
        results = []
        ak_symbol = self.INDEX_SYMBOLS.get(self.index_code, f"sh{self.index_code}")

        self.logger.info(f"Downloading {self.index_code} index daily: {start_date} -> {end_date}")

        # Try Tushare first, fallback to akshare
        df = self._fetch_with_fallback(ak_symbol, start_date, end_date)

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

            # Re-fetch data to store (using same fallback logic)
            ak_symbol = self.INDEX_SYMBOLS.get(self.index_code, f"sh{self.index_code}")
            sd_str, ed_str = self._parse_date_range(result.trade_date)
            # Convert strings back to date objects for _fetch_with_fallback
            try:
                sd = date.fromisoformat(sd_str) if sd_str else date.today() - timedelta(days=30)
                ed = date.fromisoformat(ed_str) if ed_str else date.today()
            except Exception:
                sd, ed = date.today() - timedelta(days=30), date.today()
            df = self._fetch_with_fallback(ak_symbol, sd, ed)
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
