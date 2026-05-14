# -*- coding: utf-8 -*-
"""CFFEX futures data downloader (IM, IC, IF, IH)."""

import pandas as pd
from datetime import date
from typing import Optional, Dict, Any, List

from tzdata_pkg.download.cffex.base import CFFEXDownloader
from tzdata_pkg.download.cffex.csv_parser import CFFEXParseResult


class CFFEXFuturesDownloader(CFFEXDownloader):
    """CFFEX futures data downloader."""

    FUTURES_PREFIXES = ["IM", "IC", "IF", "IH"]

    def __init__(self, config: dict = None, product: str = "IM", data_type: str = "daily"):
        super().__init__(config)
        self.product = product
        self.data_type = data_type
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
                product TEXT, open_price REAL, high_price REAL, low_price REAL,
                close_price REAL, settlement_price REAL, pre_settle REAL,
                change REAL, change_pct REAL, volume INTEGER, turnover REAL,
                open_interest INTEGER, oi_change INTEGER, delta TEXT,
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
                product TEXT, total_volume INTEGER, total_turnover REAL,
                total_open_interest INTEGER, total_oi_change INTEGER,
                contract_count INTEGER, max_volume INTEGER, min_volume INTEGER,
                mean_volume REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
        self.logger.info(f"Created tables: {table_name}, {stats_table}")

    def filter_futures_data(self, df: pd.DataFrame) -> pd.DataFrame:
        if "instrument_id" not in df.columns:
            return df
        return df[df["instrument_id"].str.startswith(self.product)].copy()

    def save_to_database(self, parse_result: CFFEXParseResult) -> int:
        if parse_result.record_count == 0:
            return 0
        df = self.filter_futures_data(parse_result.data)
        if len(df) == 0:
            self.logger.info(f"No {self.product} futures found")
            return 0
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
                    (trade_date, instrument_id, product, open_price, high_price, low_price,
                     close_price, settlement_price, pre_settle, change, change_pct,
                     volume, turnover, open_interest, oi_change, delta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_date, instrument_id, self.product,
                    safe_float(row.get("open_price")), safe_float(row.get("high_price")),
                    safe_float(row.get("low_price")), safe_float(row.get("close_price")),
                    safe_float(row.get("settlement_price")), safe_float(row.get("pre_settle")),
                    safe_float(row.get("change")), safe_float(row.get("change_pct")),
                    safe_int(row.get("volume")), safe_float(row.get("turnover")),
                    safe_int(row.get("open_interest")), safe_int(row.get("oi_change")),
                    safe_str(row.get("delta")),
                ))
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save record: {e}")

        if count > 0:
            self._save_stats(cursor, df, trade_date, stats_table)
        self.conn.commit()
        self.logger.info(f"Saved {count} records to {table_name}")
        return count

    def _save_stats(self, cursor, df: pd.DataFrame, trade_date: str, stats_table: str):
        try:
            cursor.execute(f"""
                INSERT OR REPLACE INTO {stats_table}
                (trade_date, product, total_volume, total_turnover, total_open_interest,
                 total_oi_change, contract_count, max_volume, min_volume, mean_volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_date, self.product,
                int(df["volume"].sum()) if "volume" in df.columns else None,
                float(df["turnover"].sum()) if "turnover" in df.columns else None,
                int(df["open_interest"].sum()) if "open_interest" in df.columns else None,
                int(df["oi_change"].sum()) if "oi_change" in df.columns else None,
                int(df["instrument_id"].nunique()) if "instrument_id" in df.columns else 0,
                int(df["volume"].max()) if "volume" in df.columns else None,
                int(df["volume"].min()) if "volume" in df.columns else None,
                float(df["volume"].mean()) if "volume" in df.columns else None,
            ))
        except Exception as e:
            self.logger.warning(f"Failed to save stats: {e}")
