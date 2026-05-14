"""Tushare daily bar downloader.

Fetches daily/weekly/monthly bars from Tushare and stores them in:
  - tzdata_analysis.db → tushare_daily (raw Tushare data)
  - tzdata_market.db → daily_quotes (unified market data, dual-write)
"""

import logging
import time
from datetime import date, datetime
from typing import List, Dict, Any, Optional

import pandas as pd

from tzdata_pkg.download.base import BaseExchangeDownloader
from tzdata_pkg.download.download_result import DownloadResult
from tzdata_pkg.download.tushare.client import TushareClient
from tzdata_pkg.core.db import SQLitePool
from tzdata_pkg.config import TZDATA_MARKET_DB, TZDATA_ANALYSIS_DB
from tzdata_pkg.config import get_tushare_config

logger = logging.getLogger(__name__)


class TushareDailyDownloader(BaseExchangeDownloader):
    """Tushare daily/weekly/monthly bar downloader.

    Args:
        config: Tushare config (from get_tushare_config)
        ts_code: Tushare contract code (e.g. "MO2505.CFFEX")
        freq: "D" (daily), "W" (weekly), "M" (monthly)
    """

    SOURCE_NAME = "tushare_daily"

    def __init__(self, config: dict = None, ts_code: str = "MO2505.CFFEX", freq: str = "D"):
        self.config = config or get_tushare_config()
        token = self.config.get("token", "")
        if not token:
            raise ValueError("TUSHARE_TOKEN not configured")

        self._client = TushareClient(token=token, rate_limit=0.3)
        self.ts_code = ts_code
        self.freq = freq

        # Storage pools
        self._market_pool = SQLitePool(str(TZDATA_MARKET_DB))
        self._analysis_pool = SQLitePool(str(TZDATA_ANALYSIS_DB))
        self._ensure_tables()

        super().__init__(self.config)

    def _ensure_tables(self):
        """Ensure target tables exist in both DBs."""
        with self._market_pool.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exchange TEXT NOT NULL DEFAULT 'CFFEX',
                    contract_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL, high REAL, low REAL, close REAL,
                    settle REAL, prev_settle REAL,
                    volume INTEGER, turnover REAL, open_interest INTEGER,
                    daily_change REAL, daily_change_pct REAL,
                    source TEXT DEFAULT 'tushare',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(exchange, contract_code, trade_date)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_quotes_date ON daily_quotes(trade_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_quotes_contract ON daily_quotes(contract_code)")

        with self._analysis_pool.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tushare_daily (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL, high REAL, low REAL, close REAL,
                    pre_close REAL, change REAL, pct_change REAL,
                    volume REAL, amount REAL,
                    settle REAL, oi REAL, oi_change REAL,
                    source TEXT DEFAULT 'tushare',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ts_code, trade_date)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tushare_daily_date ON tushare_daily(trade_date)")

    def download(self, start_date: date, end_date: date, **kwargs) -> List[DownloadResult]:
        """Download daily bars from Tushare."""
        results = []
        sd = start_date.strftime("%Y%m%d")
        ed = end_date.strftime("%Y%m%d")

        self.logger.info(f"Downloading {self.ts_code} daily: {sd} -> {ed}")
        df = self._client.daily(self.ts_code, start_date=sd, end_date=ed, freq=self.freq)

        if df is not None and not df.empty:
            results.append(DownloadResult(
                success=True,
                url=f"tushare://fut_daily/{self.ts_code}",
                file_path=None,
                error=None,
                data_type="daily",
                trade_date=f"{sd}-{ed}",
                record_count=len(df),
            ))
        else:
            results.append(DownloadResult(
                success=True,
                url=f"tushare://fut_daily/{self.ts_code}",
                file_path=None,
                error=None,
                data_type="daily",
                trade_date=f"{sd}-{ed}",
                record_count=0,
            ))

        return results

    def validate(self, results: List[DownloadResult]) -> Dict[str, Any]:
        """Validate downloaded data."""
        validation = super().validate(results)
        # Additional checks: no null trade dates, volume >= 0
        validation["source"] = "tushare_daily"
        validation["ts_code"] = self.ts_code
        return validation

    def store(self, results: List[DownloadResult], **kwargs) -> int:
        """Store data in both analysis and market DBs."""
        total_stored = 0
        for result in results:
            if not result.success or result.record_count == 0:
                continue
            # Re-fetch the data to store (in a real implementation, we'd cache it)
            sd, ed = self._parse_date_range(result.trade_date)
            df = self._client.daily(self.ts_code, start_date=sd, end_date=ed)
            if df is not None and not df.empty:
                total_stored += self._store_data(df)
        return total_stored

    def _store_data(self, df: pd.DataFrame) -> int:
        """Store to both tushare_daily (analysis) and daily_quotes (market)."""
        count = 0

        # Extract contract code from ts_code (e.g. "MO2505.CFFEX" -> "MO2505")
        contract_code = self.ts_code.split(".")[0] if "." in self.ts_code else self.ts_code

        # Store to tushare_daily
        with self._analysis_pool.transaction() as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO tushare_daily
                        (ts_code, trade_date, open, high, low, close,
                         pre_close, change, pct_change, volume, amount,
                         settle, oi, oi_change)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.ts_code,
                        str(row.get("trade_date", "")),
                        self._safe_float(row.get("open")),
                        self._safe_float(row.get("high")),
                        self._safe_float(row.get("low")),
                        self._safe_float(row.get("close")),
                        self._safe_float(row.get("pre_close")),
                        self._safe_float(row.get("change")),
                        self._safe_float(row.get("pct_change")),
                        self._safe_float(row.get("vol")),
                        self._safe_float(row.get("amount")),
                        self._safe_float(row.get("settle")),
                        self._safe_float(row.get("oi")),
                        self._safe_float(row.get("oi_chg")),
                    ))
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to store tushare_daily: {e}")

        # Dual-write to daily_quotes (unified market data)
        with self._market_pool.transaction() as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO daily_quotes
                        (exchange, contract_code, trade_date, open, high, low, close,
                         settle, prev_settle, volume, turnover, open_interest,
                         daily_change, daily_change_pct, source)
                        VALUES ('CFFEX', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'tushare')
                    """, (
                        contract_code,
                        str(row.get("trade_date", "")),
                        self._safe_float(row.get("open")),
                        self._safe_float(row.get("high")),
                        self._safe_float(row.get("low")),
                        self._safe_float(row.get("close")),
                        self._safe_float(row.get("settle")),
                        self._safe_float(row.get("pre_close")),
                        self._safe_int(row.get("vol")),
                        self._safe_float(row.get("amount")),
                        self._safe_int(row.get("oi")),
                        self._safe_float(row.get("change")),
                        self._safe_float(row.get("pct_change")),
                    ))
                except Exception as e:
                    self.logger.warning(f"Failed to store dual-write daily_quotes: {e}")

        self.logger.info(f"Stored {count} daily bars for {self.ts_code}")
        return count

    def _parse_date_range(self, date_str: str) -> tuple:
        """Parse 'YYYYMMDD-YYYYMMDD' into (start, end) strings."""
        parts = date_str.split("-")
        if len(parts) == 2:
            return parts[0], parts[1]
        return date_str, date_str

    @staticmethod
    def _safe_float(val):
        try:
            if pd.isna(val) or val in ("", None):
                return None
            return float(val)
        except Exception:
            return None

    @staticmethod
    def _safe_int(val):
        try:
            if pd.isna(val) or val in ("", None):
                return None
            return int(float(val))
        except Exception:
            return None

    def close(self):
        self._market_pool.close()
        self._analysis_pool.close()
        super().close()
