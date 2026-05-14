"""Tushare option data downloader.

Fetches option daily data with Greeks and IV from Tushare and stores in:
  - tzdata_analysis.db → tushare_option (raw Tushare option data)
  - tzdata_analysis.db → option_features (unified option features)
"""

import logging
import re
from datetime import date, datetime
from typing import List, Dict, Any, Optional

import pandas as pd

from tzdata_pkg.download.base import BaseExchangeDownloader
from tzdata_pkg.download.download_result import DownloadResult
from tzdata_pkg.download.tushare.client import TushareClient
from tzdata_pkg.core.db import SQLitePool
from tzdata_pkg.config import TZDATA_ANALYSIS_DB
from tzdata_pkg.config import get_tushare_config

logger = logging.getLogger(__name__)


class TushareOptionDownloader(BaseExchangeDownloader):
    """Tushare option data downloader.

    Args:
        config: Tushare config
        ts_code: Option contract code (e.g. "MO2505C8500.CFFEX")
        underlying: Underlying product (MO, IO, HO) — if set, downloads all options
    """

    SOURCE_NAME = "tushare_option"

    def __init__(self, config: dict = None, ts_code: str = None, underlying: str = "MO"):
        self.config = config or get_tushare_config()
        token = self.config.get("token", "")
        if not token:
            raise ValueError("TUSHARE_TOKEN not configured")

        self._client = TushareClient(token=token, rate_limit=0.5)  # Slower for options
        self.ts_code = ts_code
        self.underlying = underlying

        self._analysis_pool = SQLitePool(str(TZDATA_ANALYSIS_DB))
        self._ensure_tables()

        super().__init__(self.config)

    def _ensure_tables(self):
        with self._analysis_pool.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tushare_option (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    pre_settle REAL, settle REAL,
                    open REAL, high REAL, low REAL, close REAL,
                    volume REAL, amount REAL, oi REAL,
                    delta REAL, gamma REAL, theta REAL, vega REAL, iv REAL,
                    source TEXT DEFAULT 'tushare',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ts_code, trade_date)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tushare_option_date ON tushare_option(trade_date)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS option_features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date TEXT NOT NULL,
                    contract_code TEXT NOT NULL,
                    underlying TEXT,
                    expiry TEXT,
                    strike REAL,
                    option_type TEXT,
                    iv REAL, iv_percentile REAL, iv_rank REAL,
                    delta REAL, gamma REAL, theta REAL, vega REAL, rho REAL,
                    hv_5 REAL, hv_10 REAL, hv_20 REAL, iv_hv_spread_20 REAL,
                    volume INTEGER, open_interest INTEGER, volume_oi_ratio REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_option_features_date ON option_features(trade_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_option_features_contract ON option_features(contract_code)")

    def download(self, start_date: date, end_date: date, **kwargs) -> List[DownloadResult]:
        """Download option data from Tushare."""
        results = []
        sd = start_date.strftime("%Y%m%d")
        ed = end_date.strftime("%Y%m%d")

        if self.ts_code:
            # Single option
            df = self._client.opt_daily(self.ts_code, start_date=sd, end_date=ed)
            if df is not None and not df.empty:
                results.append(DownloadResult(
                    success=True, url=f"tushare://opt_daily/{self.ts_code}",
                    file_path=None, error=None, data_type="option",
                    trade_date=f"{sd}-{ed}", record_count=len(df),
                ))
        elif self.underlying:
            # All options for underlying — first get contract list
            opt_list = self._client.opt_basic(exchange="CFFEX")
            if opt_list is not None and not opt_list.empty:
                # Filter by underlying
                contracts = opt_list[opt_list.get("underlying", "").str.startswith(self.underlying, na=False)]
                for _, opt in contracts.iterrows():
                    code = opt.get("ts_code", "")
                    if not code:
                        continue
                    self.logger.info(f"Downloading option: {code}")
                    opt_df = self._client.opt_daily(code, start_date=sd, end_date=ed)
                    if opt_df is not None and not opt_df.empty:
                        results.append(DownloadResult(
                            success=True, url=f"tushare://opt_daily/{code}",
                            file_path=None, error=None, data_type="option",
                            trade_date=f"{sd}-{ed}", record_count=len(opt_df),
                        ))
            # Rate limit: wait between contracts
            import time
            time.sleep(0.5)

        return results

    def store(self, results: List[DownloadResult], **kwargs) -> int:
        """Store option data to analysis DB."""
        total_stored = 0
        for result in results:
            if not result.success or result.record_count == 0:
                continue
            # Parse ts_code from URL
            ts_code = result.url.split("/")[-1]
            sd, ed = self._parse_date_range(result.trade_date)
            df = self._client.opt_daily(ts_code, start_date=sd, end_date=ed)
            if df is not None and not df.empty:
                total_stored += self._store_data(df, ts_code)
        return total_stored

    def _store_data(self, df: pd.DataFrame, ts_code: str) -> int:
        """Store to both tushare_option and option_features."""
        count = 0

        with self._analysis_pool.transaction() as conn:
            for _, row in df.iterrows():
                try:
                    # Store to tushare_option
                    conn.execute("""
                        INSERT OR REPLACE INTO tushare_option
                        (ts_code, trade_date, pre_settle, settle, open, high, low, close,
                         volume, amount, oi, delta, gamma, theta, vega, iv)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ts_code,
                        str(row.get("trade_date", "")),
                        self._safe_float(row.get("pre_settle")),
                        self._safe_float(row.get("settle")),
                        self._safe_float(row.get("open")),
                        self._safe_float(row.get("high")),
                        self._safe_float(row.get("low")),
                        self._safe_float(row.get("close")),
                        self._safe_float(row.get("vol")),
                        self._safe_float(row.get("amount")),
                        self._safe_float(row.get("oi")),
                        self._safe_float(row.get("delta")),
                        self._safe_float(row.get("gamma")),
                        self._safe_float(row.get("theta")),
                        self._safe_float(row.get("vega")),
                        self._safe_float(row.get("iv")),
                    ))

                    # Also store to option_features (unified)
                    contract_code = self._extract_contract(ts_code)
                    strike, option_type = self._parse_option_details(ts_code)
                    conn.execute("""
                        INSERT OR REPLACE INTO option_features
                        (trade_date, contract_code, underlying, strike, option_type,
                         iv, delta, gamma, theta, vega, rho,
                         volume, open_interest)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(row.get("trade_date", "")),
                        contract_code,
                        self.underlying,
                        strike,
                        option_type,
                        self._safe_float(row.get("iv")),
                        self._safe_float(row.get("delta")),
                        self._safe_float(row.get("gamma")),
                        self._safe_float(row.get("theta")),
                        self._safe_float(row.get("vega")),
                        self._safe_float(row.get("rho")),
                        self._safe_int(row.get("vol")),
                        self._safe_int(row.get("oi")),
                    ))
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to store option data: {e}")

        self.logger.info(f"Stored {count} option records for {ts_code}")
        return count

    @staticmethod
    def _extract_contract(ts_code: str) -> str:
        """Extract contract code from Tushare format (e.g. 'MO2505C8500.CFFEX' -> 'MO2505-C-8500')."""
        base = ts_code.split(".")[0] if "." in ts_code else ts_code
        # Match pattern: PRODUCT + YYMM + (C|P) + STRIKE
        match = re.match(r"^([A-Z]+)(\d{4,6})([CP])(\d+)$", base)
        if match:
            return f"{match.group(1)}{match.group(2)}-{match.group(3)}-{match.group(4)}"
        return base

    @staticmethod
    def _parse_option_details(ts_code: str) -> tuple:
        """Parse strike and option type from Tushare code."""
        base = ts_code.split(".")[0] if "." in ts_code else ts_code
        match = re.match(r"^[A-Z]+\d{4,6}([CP])(\d+)$", base)
        if match:
            strike = float(match.group(2)) / 100.0 if match.group(2) else 0.0
            return strike, match.group(1)
        return 0.0, None

    @staticmethod
    def _parse_date_range(date_str: str) -> tuple:
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
        self._analysis_pool.close()
        super().close()
