"""
Component stock list downloader for MO signal data.

Downloads CSI 1000 component stock list via akshare,
stores into bills.db option_sim_components table.
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


class ComponentDownloader(BaseExchangeDownloader):
    """
    Download index component stock list and store to option_sim_components.

    Args:
        index_code: Index code (e.g. '000852' for CSI 1000)
    """

    SOURCE_NAME = "component"

    def __init__(self, index_code: str = '000852', config: dict = None):
        self.index_code = index_code
        self.config = config or {}
        self._client = AkshareClient()
        self._pool = None
        super().__init__(self.config)

    def _get_pool(self):
        if self._pool is None:
            self._pool = sqlite3.connect(BILLS_DB_PATH)
            self._ensure_table()
        return self._pool

    def _ensure_table(self):
        """Ensure option_sim_components table exists."""
        self._pool.execute("""
            CREATE TABLE IF NOT EXISTS option_sim_components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_code TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                include_date TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(index_code, stock_code)
            )
        """)
        self._pool.execute("CREATE INDEX IF NOT EXISTS idx_components_index ON option_sim_components(index_code)")
        self._pool.execute("CREATE INDEX IF NOT EXISTS idx_components_code ON option_sim_components(stock_code)")
        self._pool.commit()

    def download(self, start_date: date, end_date: date, **kwargs) -> List[DownloadResult]:
        """Fetch component stock list from akshare."""
        results = []

        self.logger.info(f"Fetching components for index: {self.index_code}")
        df = self._client.fetch_component_stocks(self.index_code)

        if df is not None and not df.empty:
            results.append(DownloadResult(
                success=True,
                url=f"akshare://components/{self.index_code}",
                file_path=None,
                error=None,
                data_type="components",
                trade_date=date.today().isoformat(),
                record_count=len(df),
            ))
        else:
            results.append(DownloadResult(
                success=True,
                url=f"akshare://components/{self.index_code}",
                file_path=None,
                error=None,
                data_type="components",
                trade_date=date.today().isoformat(),
                record_count=0,
            ))

        return results

    def store(self, results: List[DownloadResult], **kwargs) -> int:
        """Store component list to option_sim_components."""
        total_stored = 0
        for result in results:
            if not result.success or result.record_count == 0:
                continue

            df = self._client.fetch_component_stocks(self.index_code)
            if df is not None and not df.empty:
                total_stored += self._store_components(df)

        return total_stored

    def _store_components(self, df: pd.DataFrame) -> int:
        """Write component list to option_sim_components."""
        count = 0
        conn = self._get_pool()

        # Clear old data for this index first
        conn.execute("DELETE FROM option_sim_components WHERE index_code = ?", (self.index_code,))

        # Detect column names (may be Chinese or English)
        code_col = None
        name_col = None
        date_col = None

        for col in df.columns:
            if '代码' in col or 'code' in col.lower():
                code_col = col
            elif '名称' in col or 'name' in col.lower():
                name_col = col
            elif '日期' in col or 'date' in col.lower() or '纳入' in col:
                date_col = col

        for _, row in df.iterrows():
            try:
                code = str(row.get(code_col, '')) if code_col else ''
                name = str(row.get(name_col, '')) if name_col else ''
                inc_date = str(row.get(date_col, ''))[:10] if date_col else ''

                if not code:
                    continue

                conn.execute("""
                    INSERT OR REPLACE INTO option_sim_components
                    (index_code, stock_code, stock_name, include_date)
                    VALUES (?, ?, ?, ?)
                """, (self.index_code, code, name, inc_date))
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to store component: {e}")

        conn.commit()
        self.logger.info(f"Stored {count} components for index {self.index_code}")
        return count

    def close(self):
        if self._pool:
            self._pool.close()
        super().close()
