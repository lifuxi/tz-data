"""SHFE position ranking data downloader using AkShare."""

import pandas as pd
from datetime import date, timedelta
from typing import Optional
from tzdata_pkg.download.shfe.base import SHFEDownloader


def safe_int(val):
    try:
        if pd.isna(val) or val in ("", None):
            return None
        return int(float(val))
    except Exception:
        return None


class SHFEPositionDownloader(SHFEDownloader):
    """SHFE position ranking data downloader."""

    def __init__(self, db_path: str = None, data_dir: str = None):
        super().__init__(db_path, data_dir)
        self._init_table()

    def _init_table(self):
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS position_detail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date TEXT NOT NULL, product TEXT NOT NULL,
                    instrument_id TEXT, member_name TEXT,
                    long_position INTEGER, short_position INTEGER,
                    long_change INTEGER, short_change INTEGER,
                    UNIQUE(trade_date, product, instrument_id, member_name)
                )
            """)
            conn.commit()
        finally:
            self._release_connection(conn)

    def download(self, date_str: str, variety: str = None):
        self._download_position(variety or "all", date_str)

    def _download_position(self, product: str, date_str: str):
        import akshare as ak
        try:
            date_formatted = date_str.replace("-", "")
            df = ak.futures_shfe_position_summary(date=date_formatted)
            if df is None or df.empty:
                self.logger.info(f"No position data for {date_str}")
                return
            self._save_to_db(df, product, date_str)
        except Exception as e:
            self.logger.error(f"Failed to download position for {product}: {e}")

    def _resolve_instrument(self, row: pd.Series, product: str) -> str:
        for col in ["variety", "contract", "symbol", "instrument"]:
            if col in row.index and pd.notna(row[col]):
                return str(row[col])
        return product

    def _save_to_db(self, df: pd.DataFrame, product: str, date_str: str):
        conn = self._get_connection()
        try:
            for _, row in df.iterrows():
                try:
                    instrument_id = self._resolve_instrument(row, product)
                    conn.execute("""
                        INSERT OR REPLACE INTO position_detail
                        (trade_date, product, instrument_id, member_name,
                         long_position, short_position, long_change, short_change)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        date_str, product, instrument_id,
                        str(row.get("member", row.get("broker", ""))),
                        safe_int(row.get("long")), safe_int(row.get("short")),
                        safe_int(row.get("long_change")), safe_int(row.get("short_change")),
                    ))
                except Exception as e:
                    self.logger.warning(f"Failed to save position: {e}")
            conn.commit()
            self.logger.info(f"Saved position data for {date_str}")
        finally:
            self._release_connection(conn)

        # Dual-write: unified tzdata_market.db
        self._save_positions_to_unified(df, product, date_str)

    def incremental_download(self, variety: str = "all", max_days: int = 30):
        last_date = self._get_last_downloaded_date(variety)
        if last_date:
            start = pd.to_datetime(last_date) + timedelta(days=1)
        else:
            start = date.today() - timedelta(days=max_days)
        end = date.today()
        current = start
        while current <= end:
            self._download_position(variety, current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

    def _get_last_downloaded_date(self, variety: str) -> Optional[str]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT MAX(trade_date) FROM position_detail WHERE product = ?", (variety,))
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        finally:
            self._release_connection(conn)
