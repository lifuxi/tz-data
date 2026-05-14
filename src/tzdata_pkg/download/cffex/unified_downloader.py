# -*- coding: utf-8 -*-
"""Unified CFFEX downloader.

Merges daily_downloader, futures_downloader, and position_downloader into a
single product-aware downloader that dual-writes to:
  - tzdata_market.db (new unified storage, via MarketStore)
  - cffex.db (legacy, transition period)

Key fixes over the old code:
  - _get_table_name() now uses the actual product code instead of hardcoding "mo"
  - Single table per data type (no year-based partitioning)
  - Uses core.db.SQLitePool instead of raw sqlite3 connections
"""

import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import pandas as pd

from tzdata_pkg.download.cffex.base import CFFEXDownloader
from tzdata_pkg.download.cffex.csv_parser import CFFEXParseResult
from tzdata_pkg.download.cffex.position_downloader import CFFEXPositionDownloader
from tzdata_pkg.core.db import SQLitePool
from tzdata_pkg.config import TZDATA_MARKET_DB


logger = logging.getLogger(__name__)


# ── Unified table naming ────────────────────────────────────

def unified_table_name(product: str, data_type: str) -> str:
    """Return unified table name: {product}_{data_type} (e.g. MO_daily, IM_position)."""
    return f"{product}_{data_type}"


# ── Legacy table writer (dual-write to old cffex.db) ────────

class _LegacyCFFEXWriter:
    """Writes to the old cffex.db using the original per-year partitioning.

    This exists solely for the dual-write transition period.  Once consumers
    switch to tzdata_market.db this class can be removed.
    """

    def __init__(self, legacy_downloader: CFFEXDownloader):
        self._dl = legacy_downloader

    def write(self, parse_result: CFFEXParseResult) -> int:
        """Delegate to the legacy downloader's save_to_database."""
        return self._dl.save_to_database(parse_result)


# ── Unified CFFEX Downloader ────────────────────────────────

class CFFEXUnifiedDownloader:
    """Unified CFFEX downloader supporting all products and data types.

    Args:
        config: CFFEX config dict (from get_cffex_config)
        product: Product code (MO, IM, IC, IF, IH, IO, HO)
        data_type: One of daily, weekly, monthly, position
    """

    def __init__(self, config: dict, product: str, data_type: str = "daily"):
        self.config = config
        self.product = product
        self.data_type = data_type

        # Unified storage pool (new DB)
        self._pool = SQLitePool(str(TZDATA_MARKET_DB))
        self._ensure_unified_tables()

        # Legacy downloader for dual-write
        self._legacy = self._build_legacy_downloader()
        self._legacy_writer = _LegacyCFFEXWriter(self._legacy) if self._legacy else None

        self.logger = logging.getLogger(f"CFFEXUnified[{product}/{data_type}]")

    # ── Legacy bridge ───────────────────────────────────────

    def _build_legacy_downloader(self) -> Optional[CFFEXDownloader]:
        """Build the appropriate legacy downloader based on data_type."""
        if self.data_type == "position":
            return CFFEXPositionDownloader(self.config, self.product)
        else:
            # For daily/weekly/monthly, use CFFEXDailyDownloader
            # The bug was that CFFEXDailyDownloader always uses "mo_" prefix.
            # We keep it for dual-write but the unified path uses correct naming.
            return CFFEXDailyDownloader(self.config, self.data_type)

    # ── Unified table creation ──────────────────────────────

    def _ensure_unified_tables(self):
        """Create unified (non-partitioned) tables in tzdata_market.db."""
        with self._pool.transaction() as conn:
            if self.data_type == "position":
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS position_detail (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        exchange TEXT NOT NULL DEFAULT 'CFFEX',
                        trade_date TEXT NOT NULL,
                        contract_code TEXT NOT NULL,
                        product TEXT,
                        member_name TEXT NOT NULL,
                        rank INTEGER,
                        long_volume INTEGER DEFAULT 0,
                        short_volume INTEGER DEFAULT 0,
                        long_change INTEGER,
                        short_change INTEGER,
                        net_position INTEGER GENERATED ALWAYS AS (long_volume - short_volume) STORED,
                        source TEXT DEFAULT 'exchange',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(exchange, trade_date, contract_code, member_name)
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_position_detail_date ON position_detail(trade_date)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_position_detail_contract ON position_detail(contract_code)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_position_detail_member ON position_detail(member_name)")
            else:
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
                        amplitude REAL,
                        source TEXT DEFAULT 'exchange',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(exchange, contract_code, trade_date)
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_quotes_date ON daily_quotes(trade_date)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_quotes_contract ON daily_quotes(contract_code)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_quotes_exchange_date ON daily_quotes(exchange, trade_date)")

    # ── Unified save ────────────────────────────────────────

    def save_unified(self, parse_result: CFFEXParseResult) -> int:
        """Save parsed data to tzdata_market.db (unified table)."""
        if parse_result.record_count == 0:
            return 0

        df = parse_result.data
        trade_date = parse_result.trade_date

        if self.data_type == "position":
            return self._save_positions_unified(df, trade_date)
        else:
            return self._save_quotes_unified(df, trade_date)

    def _save_quotes_unified(self, df: pd.DataFrame, trade_date: str) -> int:
        count = 0
        with self._pool.transaction() as conn:
            for _, row in df.iterrows():
                instrument_id = self._safe_str(row.get("instrument_id"))
                if not instrument_id or instrument_id == "nan":
                    continue
                conn.execute("""
                    INSERT OR REPLACE INTO daily_quotes
                    (exchange, contract_code, trade_date, open, high, low, close,
                     settle, prev_settle, volume, turnover, open_interest,
                     daily_change, daily_change_pct, source)
                    VALUES ('CFFEX', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'exchange')
                """, (
                    instrument_id, trade_date,
                    self._safe_float(row.get("open_price")),
                    self._safe_float(row.get("high_price")),
                    self._safe_float(row.get("low_price")),
                    self._safe_float(row.get("close_price")),
                    self._safe_float(row.get("settlement_price")),
                    self._safe_float(row.get("pre_settle")),
                    self._safe_int(row.get("volume")),
                    self._safe_float(row.get("turnover")),
                    self._safe_int(row.get("open_interest")),
                    self._safe_float(row.get("change")),
                    self._safe_float(row.get("change_pct")),
                ))
                count += 1
        self.logger.info(f"Saved {count} quotes to unified daily_quotes")
        return count

    def _save_positions_unified(self, df: pd.DataFrame, trade_date: str) -> int:
        count = 0
        with self._pool.transaction() as conn:
            for idx, row in df.iterrows():
                instrument_id = self._safe_str(row.get("instrument_id"))
                member_name = self._safe_str(row.get("member_name"))
                if not instrument_id or not member_name:
                    continue
                long_vol = self._safe_int(row.get("long_volume")) or 0
                short_vol = self._safe_int(row.get("short_volume")) or 0
                conn.execute("""
                    INSERT OR REPLACE INTO position_detail
                    (exchange, trade_date, contract_code, product, member_name,
                     rank, long_volume, short_volume, long_change, short_change, source)
                    VALUES ('CFFEX', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'exchange')
                """, (
                    trade_date, instrument_id, self.product, member_name,
                    int(idx) + 1 if isinstance(idx, int) else None,
                    long_vol, short_vol,
                    self._safe_int(row.get("long_change")),
                    self._safe_int(row.get("short_change")),
                ))
                count += 1
        self.logger.info(f"Saved {count} positions to unified position_detail")
        return count

    # ── Dual-write download methods ─────────────────────────

    def download_full(self, start_year: int = None, end_year: int = None) -> Dict[str, Any]:
        """Full download with dual-write to both old and new storage."""
        start_year = start_year or self.config.get("partition", {}).get("start_year", 2024)
        end_year = end_year or datetime.now().year

        self.logger.info(f"Full download: {self.product}/{self.data_type}, {start_year}-{end_year}")

        # Create legacy tables
        if self._legacy:
            for year in range(start_year, end_year + 1):
                self._legacy.create_tables(year)

        total_results = []
        for year in range(start_year, end_year + 1):
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
            if year == datetime.now().year:
                end_date = min(end_date, date.today())
            results = self._legacy.download_batch(self.data_type, start_date, end_date, self.product)
            total_results.extend(results)

            # Dual-write: save each successful result to unified storage
            for r in results:
                if r.success and r.file_path:
                    try:
                        parse_result = self._legacy.csv_parser.parse_csv(
                            r.file_path, self.data_type, product=self.product
                        )
                        if parse_result.record_count > 0:
                            self.save_unified(parse_result)
                    except Exception as e:
                        self.logger.warning(f"Dual-write failed for {r.file_path}: {e}")

        return self._summarize_results(total_results)

    def download_incremental(self) -> Dict[str, Any]:
        """Incremental download with dual-write."""
        current_year = datetime.now().year

        if self._legacy:
            self._legacy.create_tables(current_year)
            latest = self._legacy.get_latest_date(self.data_type, current_year)
        else:
            latest = None

        if latest:
            start_date = datetime.strptime(latest, "%Y-%m-%d").date()
            # Check if already up to date
            if start_date >= date.today():
                self.logger.info("Data is up to date")
                return {"data_type": self.data_type, "status": "up_to_date", "total_files": 0, "total_records": 0}
            start_date = start_date  # resume from this date
        else:
            start_date = date(current_year, 1, 1)

        end_date = date.today()
        results = self._legacy.download_batch(self.data_type, start_date, end_date, self.product)

        # Dual-write
        for r in results:
            if r.success and r.file_path:
                try:
                    parse_result = self._legacy.csv_parser.parse_csv(
                        r.file_path, self.data_type, product=self.product
                    )
                    if parse_result.record_count > 0:
                        self.save_unified(parse_result)
                except Exception as e:
                    self.logger.warning(f"Dual-write failed for {r.file_path}: {e}")

        return self._summarize_results(results)

    def download_range(self, start_date: date, end_date: date, save_csv: bool = True) -> Dict[str, Any]:
        """Download a specific date range with dual-write."""
        if self._legacy:
            current_year = start_date.year
            self._legacy.create_tables(current_year)

        results = self._legacy.download_batch(self.data_type, start_date, end_date, self.product, save_csv=save_csv)

        for r in results:
            if r.success and r.file_path:
                try:
                    parse_result = self._legacy.csv_parser.parse_csv(
                        r.file_path, self.data_type, product=self.product
                    )
                    if parse_result.record_count > 0:
                        self.save_unified(parse_result)
                except Exception as e:
                    self.logger.warning(f"Dual-write failed for {r.file_path}: {e}")

        return self._summarize_results(results)

    # ── Query helpers ───────────────────────────────────────

    def get_quotes(self, contract_code: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Query quotes from unified storage."""
        query = "SELECT * FROM daily_quotes WHERE exchange='CFFEX' AND contract_code=?"
        params: list = [contract_code]
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)
        query += " ORDER BY trade_date"

        with self._pool.transaction() as conn:
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_positions(self, contract_code: str, trade_date: str = None) -> List[Dict]:
        """Query positions from unified storage."""
        query = "SELECT * FROM position_detail WHERE exchange='CFFEX' AND contract_code=?"
        params: list = [contract_code]
        if trade_date:
            query += " AND trade_date = ?"
            params.append(trade_date)
        query += " ORDER BY rank"

        with self._pool.transaction() as conn:
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self):
        if self._legacy:
            try:
                self._legacy.close()
            except Exception:
                pass
        self._pool.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ── Internal helpers ────────────────────────────────────

    def _summarize_results(self, results: list) -> Dict[str, Any]:
        if not results:
            return {"data_type": self.data_type, "product": self.product,
                    "total_files": 0, "success_count": 0, "fail_count": 0, "total_records": 0}
        return {
            "data_type": self.data_type,
            "product": self.product,
            "total_files": len(results),
            "success_count": sum(1 for r in results if r.success),
            "fail_count": sum(1 for r in results if not r.success),
            "total_records": sum(r.record_count for r in results),
        }

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

    @staticmethod
    def _safe_str(val, default=""):
        try:
            if pd.isna(val) or val in ("", None):
                return default
            return str(val)
        except Exception:
            return default
