# -*- coding: utf-8 -*-
"""CFFEX position ranking data downloader."""

import pandas as pd
from datetime import date
from typing import Optional, Dict, Any, List

from tzdata_pkg.download.cffex.base import CFFEXDownloader
from tzdata_pkg.download.cffex.csv_parser import CFFEXParseResult


class CFFEXPositionDownloader(CFFEXDownloader):
    """CFFEX position ranking data downloader."""

    def __init__(self, config: dict = None, product: str = None):
        if product is None:
            raise ValueError("product must be specified (e.g. MO, IM, IC, IF, IH, IO, HO)")
        super().__init__(config)
        self.product = product
        self.data_type = "position"

    def _get_table_name(self, data_type: str = None, year: int = None) -> str:
        if year:
            return f"{self.product.lower()}_position_{year}"
        return f"{self.product.lower()}_position"

    def create_tables(self, year: int):
        cursor = self.conn.cursor()
        table_name = self._get_table_name("position", year)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL, instrument_id TEXT NOT NULL,
                product TEXT, member_name TEXT NOT NULL, rank INTEGER,
                long_volume INTEGER, short_volume INTEGER,
                long_change INTEGER, short_change INTEGER,
                net_position INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_date, instrument_id, member_name)
            )
        """)
        if self.config.get("partition", {}).get("index_on_create"):
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_date ON {table_name}(trade_date)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_instrument ON {table_name}(instrument_id)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_member ON {table_name}(member_name)")
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_date_inst ON {table_name}(trade_date, instrument_id)")
        summary_table = f"{self.product.lower()}_position_summary_{year}"
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {summary_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL, instrument_id TEXT NOT NULL,
                product TEXT, member_count INTEGER, total_long INTEGER,
                total_short INTEGER, total_net INTEGER,
                top_long_member TEXT, top_short_member TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_date, instrument_id)
            )
        """)
        self.conn.commit()
        self.logger.info(f"Created tables: {table_name}, {summary_table}")

    def save_to_database(self, parse_result: CFFEXParseResult) -> int:
        if parse_result.record_count == 0:
            return 0
        df = parse_result.data
        trade_date = parse_result.trade_date
        year = int(trade_date[:4]) if trade_date else date.today().year
        self.create_tables(year)
        table_name = self._get_table_name("position", year)
        summary_table = f"{self.product.lower()}_position_summary_{year}"
        cursor = self.conn.cursor()
        count = 0

        for idx, row in df.iterrows():
            try:
                instrument_id = str(row.get("instrument_id", ""))
                member_name = str(row.get("member_name", ""))
                if not instrument_id or not member_name:
                    continue
                long_vol = int(row.get("long_volume", 0)) if row.get("long_volume") else 0
                short_vol = int(row.get("short_volume", 0)) if row.get("short_volume") else 0
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {table_name}
                    (trade_date, instrument_id, product, member_name, rank,
                     long_volume, short_volume, long_change, short_change, net_position)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_date, instrument_id, str(row.get("product", self.product)),
                    member_name, int(idx) + 1 if isinstance(idx, int) else None,
                    long_vol, short_vol,
                    int(row.get("long_change", 0)) if row.get("long_change") else None,
                    int(row.get("short_change", 0)) if row.get("short_change") else None,
                    long_vol - short_vol,
                ))
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to save record: {e}")

        self._save_summary(cursor, df, trade_date, summary_table)
        self.conn.commit()
        self.logger.info(f"Saved {count} records to {table_name}")
        return count

    def _save_summary(self, cursor, df, trade_date: str, summary_table: str):
        if "instrument_id" not in df.columns:
            return
        summary = df.groupby("instrument_id").agg({
            "member_name": "count", "long_volume": "sum", "short_volume": "sum",
        }).reset_index()
        for _, row in summary.iterrows():
            instrument_id = row["instrument_id"]
            total_long = int(row["long_volume"]) if row["long_volume"] else 0
            total_short = int(row["short_volume"]) if row["short_volume"] else 0
            contract_df = df[df["instrument_id"] == instrument_id]
            top_long_member = ""
            top_short_member = ""
            if "long_volume" in contract_df.columns:
                top_long = contract_df.nlargest(1, "long_volume")
                if not top_long.empty:
                    top_long_member = str(top_long.iloc[0].get("member_name", ""))
            if "short_volume" in contract_df.columns:
                top_short = contract_df.nlargest(1, "short_volume")
                if not top_short.empty:
                    top_short_member = str(top_short.iloc[0].get("member_name", ""))
            try:
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {summary_table}
                    (trade_date, instrument_id, product, member_count, total_long,
                     total_short, total_net, top_long_member, top_short_member)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_date, instrument_id, self.product,
                    int(row["member_name"]), total_long, total_short,
                    total_long - total_short, top_long_member, top_short_member,
                ))
            except Exception as e:
                self.logger.warning(f"Failed to save summary: {e}")

    def get_position_by_instrument(self, instrument_id: str, trade_date: str = None,
                                   year: int = None) -> List[Dict]:
        table_name = self._get_table_name("position", year or date.today().year)
        try:
            cursor = self.conn.cursor()
            if trade_date:
                cursor.execute(f"SELECT * FROM {table_name} WHERE instrument_id = ? AND trade_date = ? ORDER BY long_volume DESC",
                               (instrument_id, trade_date))
            else:
                cursor.execute(f"SELECT * FROM {table_name} WHERE instrument_id = ? ORDER BY trade_date DESC, long_volume DESC",
                               (instrument_id,))
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.warning(f"Failed to get positions: {e}")
            return []

    def get_top_members(self, trade_date: str, top_n: int = 20, year: int = None) -> Dict[str, List]:
        table_name = self._get_table_name("position", year or date.today().year)
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT member_name, SUM(long_volume) as total_long FROM {table_name} WHERE trade_date = ? GROUP BY member_name ORDER BY total_long DESC LIMIT ?",
                           (trade_date, top_n))
            long_ranking = cursor.fetchall()
            cursor.execute(f"SELECT member_name, SUM(short_volume) as total_short FROM {table_name} WHERE trade_date = ? GROUP BY member_name ORDER BY total_short DESC LIMIT ?",
                           (trade_date, top_n))
            short_ranking = cursor.fetchall()
            return {"long": long_ranking, "short": short_ranking}
        except Exception as e:
            self.logger.warning(f"Failed to get member rankings: {e}")
            return {"long": [], "short": []}
