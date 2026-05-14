"""SHFE downloader base class.

Refactored to use core.db.SQLitePool and dual-write to tzdata_market.db.
"""

import logging
import pandas as pd
from pathlib import Path
from tzdata_pkg.core.db import SQLitePool
from tzdata_pkg.config import get_shfe_config, TZDATA_MARKET_DB


class SHFEDownloader:
    """Base class for SHFE data downloaders."""

    def __init__(self, db_path: str = None, data_dir: str = None):
        config = get_shfe_config()
        self.config = config
        storage = config["storage"]
        self.db_path = db_path or storage["db_path"]
        self.data_dir = Path(data_dir or storage.get("csv_dir", "./data/shfe/raw"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._empty_count = 0
        self._empty_threshold = config.get("download", {}).get("empty_threshold", 5)

        # Unified storage pool (new DB)
        self._unified_pool = SQLitePool(str(TZDATA_MARKET_DB))
        self._ensure_unified_tables()

    def _ensure_unified_tables(self):
        """Create unified tables in tzdata_market.db."""
        with self._unified_pool.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exchange TEXT NOT NULL DEFAULT 'SHFE',
                    contract_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL, high REAL, low REAL, close REAL,
                    settle REAL, prev_settle REAL,
                    volume INTEGER, turnover REAL, open_interest INTEGER,
                    daily_change REAL, daily_change_pct REAL,
                    amplitude REAL,
                    source TEXT DEFAULT 'akshare',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(exchange, contract_code, trade_date)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_quotes_date ON daily_quotes(trade_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_quotes_contract ON daily_quotes(contract_code)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_quotes_exchange_date ON daily_quotes(exchange, trade_date)")

    def _get_connection(self):
        """Get connection to legacy SHFE DB (for dual-write transition)."""
        return self._legacy_pool.acquire()

    def _release_connection(self, conn):
        self._legacy_pool.release(conn)

    @property
    def _legacy_pool(self):
        """Lazy-create legacy pool on first access."""
        if not hasattr(self, '_legacy_pool_instance'):
            self._legacy_pool_instance = SQLitePool(self.db_path)
        return self._legacy_pool_instance

    def _save_csv(self, df: pd.DataFrame, filename: str):
        path = self.data_dir / filename
        df.to_csv(path, index=False)
        self.logger.info(f"Saved CSV: {path}")

    def _check_empty(self, df: pd.DataFrame) -> bool:
        if df is None or df.empty:
            self._empty_count += 1
            if self._empty_count >= self._empty_threshold:
                self.logger.warning(f"Consecutive {self._empty_count} empty results")
                return True
        else:
            self._empty_count = 0
        return False

    def _save_to_unified(self, df: pd.DataFrame, product: str, date_col: str = "trade_date"):
        """Save SHFE data to unified tzdata_market.db."""
        count = 0
        with self._unified_pool.transaction() as conn:
            for _, row in df.iterrows():
                try:
                    trade_date = str(row.get(date_col, ""))[:10]
                    contract_code = str(row.get("symbol", row.get("instrument_id", "")))
                    conn.execute("""
                        INSERT OR REPLACE INTO daily_quotes
                        (exchange, contract_code, trade_date, open, high, low, close,
                         settle, volume, turnover, open_interest, source)
                        VALUES ('SHFE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'akshare')
                    """, (
                        contract_code, trade_date,
                        self._safe_float(row.get("open")),
                        self._safe_float(row.get("high")),
                        self._safe_float(row.get("low")),
                        self._safe_float(row.get("close")),
                        self._safe_float(row.get("settle")),
                        self._safe_int(row.get("volume")),
                        self._safe_float(row.get("turnover")),
                        self._safe_int(row.get("open_interest")),
                    ))
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to save unified SHFE record: {e}")
        self.logger.info(f"Saved {count} SHFE records to unified storage")

    def _save_positions_to_unified(self, df: pd.DataFrame, product: str, date_str: str):
        """Save SHFE position data to unified tzdata_market.db."""
        count = 0
        with self._unified_pool.transaction() as conn:
            for _, row in df.iterrows():
                try:
                    contract_code = str(row.get("variety", row.get("contract", product)))
                    member_name = str(row.get("member", row.get("broker", "")))
                    if not contract_code or not member_name:
                        continue
                    long_vol = self._safe_int(row.get("long")) or 0
                    short_vol = self._safe_int(row.get("short")) or 0
                    conn.execute("""
                        INSERT OR REPLACE INTO position_detail
                        (exchange, trade_date, contract_code, product, member_name,
                         long_volume, short_volume, long_change, short_change, source)
                        VALUES ('SHFE', ?, ?, ?, ?, ?, ?, ?, ?, 'akshare')
                    """, (
                        date_str, contract_code, product, member_name,
                        long_vol, short_vol,
                        self._safe_int(row.get("long_change")),
                        self._safe_int(row.get("short_change")),
                    ))
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to save unified SHFE position: {e}")
        self.logger.info(f"Saved {count} SHFE positions to unified storage")

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
        if hasattr(self, '_legacy_pool_instance'):
            self._legacy_pool_instance.close()
        self._unified_pool.close()
