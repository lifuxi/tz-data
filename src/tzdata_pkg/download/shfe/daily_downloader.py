"""SHFE daily data downloader using AkShare."""

import pandas as pd
from datetime import date
from typing import List, Optional, Dict
from tzdata_pkg.download.shfe.base import SHFEDownloader
from tzdata_pkg.config import get_shfe_config


def pd_to_datetime_safe(series):
    return pd.to_datetime(series, errors="coerce")


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


class SHFEDailyDownloader(SHFEDownloader):
    """SHFE daily data downloader."""

    def __init__(self, db_path: str = None, data_dir: str = None):
        super().__init__(db_path, data_dir)
        self._init_table()

    def _init_table(self):
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date TEXT NOT NULL, product TEXT NOT NULL,
                    instrument_id TEXT, open_price REAL, high_price REAL,
                    low_price REAL, close_price REAL, volume INTEGER,
                    turnover REAL, open_interest INTEGER, settle_price REAL,
                    UNIQUE(trade_date, product, instrument_id)
                )
            """)
            conn.commit()
        finally:
            self._release_connection(conn)

    def _akshare_symbol(self, product: str) -> str:
        return f"{product}0"

    def download_daily(self, products: List[str], start_date: date, end_date: date):
        for product in products:
            self._download_product_daily(product, start_date, end_date)

    def incremental_download(self, products: List[str]):
        for product in products:
            last_date = self._get_last_downloaded_date(product)
            if last_date:
                start = pd_to_datetime_safe(pd.Series([last_date])).iloc(0)
                if hasattr(start, "date"):
                    start_date = start.date() + pd.Timedelta(days=1)
                else:
                    start_date = date.today()
            else:
                start_date = date(2024, 1, 1)
            self._download_product_daily(product, start_date, date.today())

    def _download_product_daily(self, product: str, start_date: date, end_date: date):
        import akshare as ak
        symbol = self._akshare_symbol(product)
        try:
            df = ak.futures_zh_daily_sina(symbol=symbol)
            if df is None or df.empty:
                self.logger.info(f"No data for {product}")
                return
            df["trade_date"] = pd_to_datetime_safe(df.get("date", df.iloc[:, 0]))
            mask = (df["trade_date"] >= pd.Timestamp(start_date)) & (df["trade_date"] <= pd.Timestamp(end_date))
            filtered = df[mask]
            if not filtered.empty:
                self._save_to_db(filtered, product, "trade_date")
        except Exception as e:
            self.logger.error(f"Failed to download {product}: {e}")

    def _save_to_db(self, df: pd.DataFrame, product: str, date_col: str):
        # Dual-write: legacy SHFE DB
        conn = self._get_connection()
        try:
            for _, row in df.iterrows():
                try:
                    trade_date = str(row.get(date_col, ""))[:10]
                    conn.execute("""
                        INSERT OR REPLACE INTO daily_quotes
                        (trade_date, product, instrument_id, open_price, high_price,
                         low_price, close_price, volume, turnover, open_interest, settle_price)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade_date, product, row.get("symbol", ""),
                        safe_float(row.get("open")), safe_float(row.get("high")),
                        safe_float(row.get("low")), safe_float(row.get("close")),
                        safe_int(row.get("volume")), safe_float(row.get("turnover")),
                        safe_int(row.get("open_interest")), safe_float(row.get("settle")),
                    ))
                except Exception as e:
                    self.logger.warning(f"Failed to save record: {e}")
            conn.commit()
        finally:
            self._release_connection(conn)

        # Dual-write: unified tzdata_market.db
        self._save_to_unified(df, product, date_col)

    def _get_last_downloaded_date(self, product: str) -> Optional[str]:
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT MAX(trade_date) FROM daily_quotes WHERE product = ?", (product,))
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        finally:
            self._release_connection(conn)
