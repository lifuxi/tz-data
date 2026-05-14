# -*- coding: utf-8 -*-
"""CFFEX daily/weekly/monthly data downloader."""

import sqlite3
import pandas as pd
from datetime import date
from typing import Optional, Dict, Any

from tzdata_pkg.download.cffex.base import CFFEXDownloader
from tzdata_pkg.download.cffex.csv_parser import CFFEXParseResult


class CFFEXDailyDownloader(CFFEXDownloader):
    """CFFEX daily/weekly/monthly data downloader."""

    def __init__(self, config: dict = None, data_type: str = "daily", product: str = None):
        super().__init__(config)
        if product is None:
            raise ValueError("product must be specified (e.g. MO, IM, IC, IF, IH, IO, HO)")
        self.data_type = data_type
        self.product = product
        if data_type not in ["daily", "weekly", "monthly"]:
            raise ValueError(f"Unsupported data type: {data_type}")

    def _get_table_name(self, data_type: str = None, year: int = None) -> str:
        data_type = data_type or self.data_type
        prefix = {
            "daily": f"{self.product.lower()}_daily",
            "weekly": f"{self.product.lower()}_weekly",
            "monthly": f"{self.product.lower()}_monthly",
        }.get(data_type, f"{self.product.lower()}_daily")
        if year:
            return f"{prefix}_{year}"
        return prefix

    def _get_stats_table_name(self, year: int) -> str:
        return f"{self.product.lower()}_stats_{year}"

    def create_tables(self, year: int):
        cursor = self.conn.cursor()
        table_name = self._get_table_name(self.data_type, year)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL, instrument_id TEXT NOT NULL,
                product TEXT, underlying TEXT, contract_month TEXT,
                option_type TEXT, strike_price REAL, open_price REAL,
                high_price REAL, low_price REAL, close_price REAL,
                settlement_price REAL, pre_settle REAL, change REAL,
                change_pct REAL, volume INTEGER, turnover REAL,
                open_interest INTEGER, oi_change INTEGER, expire_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_date, instrument_id)
            )
        """)
        if self.config.get("partition", {}).get("index_on_create"):
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_date ON {table_name}(trade_date)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_instrument ON {table_name}(instrument_id)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_product ON {table_name}(product)")
        stats_table = self._get_stats_table_name(year)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {stats_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT, trade_date TEXT NOT NULL UNIQUE,
                total_volume INTEGER, total_turnover REAL, total_open_interest INTEGER,
                total_oi_change INTEGER, contract_count INTEGER,
                max_volume INTEGER, min_volume INTEGER, mean_volume REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
        self.logger.info(f"Created tables: {table_name}, {stats_table}")

    def save_to_database(self, parse_result: CFFEXParseResult) -> int:
        if parse_result.record_count == 0:
            return 0
        df = parse_result.data
        trade_date = parse_result.trade_date
        year = int(trade_date[:4]) if trade_date and len(trade_date) >= 4 else date.today().year
        self.create_tables(year)
        table_name = self._get_table_name(self.data_type, year)
        stats_table = self._get_stats_table_name(year)
        cursor = self.conn.cursor()
        count = 0

        def safe_float(val):
            try:
                if pd.isna(val) or val in ("", None):
                    return None
                return float(val)
            except Exception:
                return None

        def safe_int(val):
            try:
                if pd.isna(val) or val in ("", None):
                    return None
                return int(float(val))
            except Exception:
                return None

        def safe_str(val, default=""):
            try:
                if pd.isna(val) or val in ("", None):
                    return default
                return str(val)
            except Exception:
                return default

        for _, row in df.iterrows():
            try:
                instrument_id = safe_str(row.get("instrument_id"))
                if not instrument_id or instrument_id == "nan":
                    continue
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {table_name}
                    (trade_date, instrument_id, product, underlying, contract_month,
                     option_type, strike_price, open_price, high_price, low_price,
                     close_price, settlement_price, pre_settle, change, change_pct,
                     volume, turnover, open_interest, oi_change, expire_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_date, instrument_id, safe_str(row.get("product"), self.product),
                    safe_str(row.get("underlying")), safe_str(row.get("contract_month")),
                    safe_str(row.get("option_type")), safe_float(row.get("strike_price")),
                    safe_float(row.get("open_price")), safe_float(row.get("high_price")),
                    safe_float(row.get("low_price")), safe_float(row.get("close_price")),
                    safe_float(row.get("settlement_price")), safe_float(row.get("pre_settle")),
                    safe_float(row.get("change")), safe_float(row.get("change_pct")),
                    safe_int(row.get("volume")), safe_float(row.get("turnover")),
                    safe_int(row.get("open_interest")), safe_int(row.get("oi_change")),
                    safe_str(row.get("expire_date")),
                ))
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save record: {e}")

        stats = parse_result.stats
        if stats:
            try:
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {stats_table}
                    (trade_date, total_volume, total_turnover, total_open_interest,
                     total_oi_change, contract_count, max_volume, min_volume, mean_volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_date,
                    int(stats.get("total_volume", 0)) if stats.get("total_volume") else None,
                    float(stats.get("total_turnover", 0)) if stats.get("total_turnover") else None,
                    int(stats.get("total_open_interest", 0)) if stats.get("total_open_interest") else None,
                    int(stats.get("total_oi_change", 0)) if stats.get("total_oi_change") else None,
                    int(stats.get("contract_count", 0)) if stats.get("contract_count") else None,
                    int(stats.get("max_volume", 0)) if stats.get("max_volume") else None,
                    int(stats.get("min_volume", 0)) if stats.get("min_volume") else None,
                    float(stats.get("mean_volume", 0)) if stats.get("mean_volume") else None,
                ))
            except Exception as e:
                self.logger.warning(f"Failed to save stats: {e}")
        self.conn.commit()
        self.logger.info(f"Saved {count} records to {table_name}")
        return count

    def get_trade_dates(self, year: int = None) -> list:
        table_name = self._get_table_name(self.data_type, year)
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT DISTINCT trade_date FROM {table_name} ORDER BY trade_date")
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            self.logger.warning(f"Failed to get trade dates: {e}")
            return []

    def get_statistics(self, trade_date: str = None, year: int = None) -> Dict[str, Any]:
        stats_table = self._get_stats_table_name(year or date.today().year)
        try:
            cursor = self.conn.cursor()
            if trade_date:
                cursor.execute(f"SELECT * FROM {stats_table} WHERE trade_date = ?", (trade_date,))
            else:
                cursor.execute(f"SELECT * FROM {stats_table} ORDER BY trade_date DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return {
                    "trade_date": row[1], "total_volume": row[2],
                    "total_turnover": row[3], "total_open_interest": row[4],
                    "total_oi_change": row[5], "contract_count": row[6],
                }
        except Exception as e:
            self.logger.warning(f"Failed to get statistics: {e}")
        return {}
