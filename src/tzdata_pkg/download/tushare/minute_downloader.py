"""Tushare minute bar downloader.

Fetches minute-level bars from Tushare and stores them in:
  - tzdata_market.db → minute_quotes (unified market data)
"""

import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional

import pandas as pd

from tzdata_pkg.download.base import BaseExchangeDownloader
from tzdata_pkg.download.download_result import DownloadResult
from tzdata_pkg.download.tushare.client import TushareClient
from tzdata_pkg.core.db import SQLitePool
from tzdata_pkg.config import TZDATA_MARKET_DB
from tzdata_pkg.config import get_tushare_config

logger = logging.getLogger(__name__)


class TushareMinuteDownloader(BaseExchangeDownloader):
    """Tushare minute bar downloader.

    Args:
        config: Tushare config
        ts_code: Tushare contract code (e.g. "MO2505.CFFEX")
        freq: One of "1min", "5min", "15min", "30min", "60min"
    """

    SOURCE_NAME = "tushare_minute"

    def __init__(self, config: dict = None, ts_code: str = "MO2505.CFFEX", freq: str = "1min"):
        self.config = config or get_tushare_config()
        token = self.config.get("token", "")
        if not token:
            raise ValueError("TUSHARE_TOKEN not configured")

        self._client = TushareClient(token=token, rate_limit=0.3)
        self.ts_code = ts_code
        self.freq = freq

        self._market_pool = SQLitePool(str(TZDATA_MARKET_DB))
        self._ensure_tables()

        super().__init__(self.config)

    def _ensure_tables(self):
        with self._market_pool.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS minute_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exchange TEXT NOT NULL DEFAULT 'CFFEX',
                    contract_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    trade_time TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    open REAL, high REAL, low REAL, close REAL,
                    volume INTEGER, turnover REAL, open_interest INTEGER,
                    vwap REAL,
                    source TEXT DEFAULT 'tushare',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(exchange, contract_code, trade_date, trade_time, frequency)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_minute_quotes_datetime ON minute_quotes(trade_date, trade_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_minute_quotes_contract ON minute_quotes(contract_code)")

    def download(self, start_date: date, end_date: date, **kwargs) -> List[DownloadResult]:
        """Download minute bars from Tushare."""
        results = []
        sd = start_date.strftime("%Y%m%d")
        ed = end_date.strftime("%Y%m%d")

        self.logger.info(f"Downloading {self.ts_code} {self.freq}: {sd} -> {ed}")
        df = self._client.fut_min(self.ts_code, start_date=sd, end_date=ed, freq=self.freq)

        if df is not None and not df.empty:
            results.append(DownloadResult(
                success=True,
                url=f"tushare://fut_mins/{self.ts_code}/{self.freq}",
                file_path=None,
                error=None,
                data_type="minute",
                trade_date=f"{sd}-{ed}",
                record_count=len(df),
            ))
        else:
            results.append(DownloadResult(
                success=True,
                url=f"tushare://fut_mins/{self.ts_code}/{self.freq}",
                file_path=None,
                error=None,
                data_type="minute",
                trade_date=f"{sd}-{ed}",
                record_count=0,
            ))

        return results

    def store(self, results: List[DownloadResult], **kwargs) -> int:
        """Store minute bars to tzdata_market.db."""
        total_stored = 0
        for result in results:
            if not result.success or result.record_count == 0:
                continue
            sd, ed = self._parse_date_range(result.trade_date)
            df = self._client.fut_min(self.ts_code, start_date=sd, end_date=ed, freq=self.freq)
            if df is not None and not df.empty:
                total_stored += self._store_data(df)
        return total_stored

    def _store_data(self, df: pd.DataFrame) -> int:
        """Store minute data to unified minute_quotes table."""
        contract_code = self.ts_code.split(".")[0] if "." in self.ts_code else self.ts_code
        count = 0

        with self._market_pool.transaction() as conn:
            for _, row in df.iterrows():
                try:
                    trade_datetime = str(row.get("trade_time", row.get("time", "")))
                    # Split into date and time
                    if " " in trade_datetime:
                        trade_date, trade_time = trade_datetime.split(" ", 1)
                    elif len(trade_datetime) >= 8:
                        trade_date = trade_datetime[:8]
                        trade_time = trade_datetime[9:17] if len(trade_datetime) > 9 else "00:00:00"
                    else:
                        continue

                    conn.execute("""
                        INSERT OR REPLACE INTO minute_quotes
                        (exchange, contract_code, trade_date, trade_time, frequency,
                         open, high, low, close, volume, turnover, open_interest)
                        VALUES ('CFFEX', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        contract_code, trade_date, trade_time, self.freq,
                        self._safe_float(row.get("open")),
                        self._safe_float(row.get("high")),
                        self._safe_float(row.get("low")),
                        self._safe_float(row.get("close")),
                        self._safe_int(row.get("vol")),
                        self._safe_float(row.get("amount")),
                        self._safe_int(row.get("oi")),
                    ))
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to store minute bar: {e}")

        self.logger.info(f"Stored {count} minute bars for {self.ts_code}")
        return count

    def _parse_date_range(self, date_str: str) -> tuple:
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
        super().close()
