"""
Trade calendar import from Tushare.
Imports trading calendar data from Tushare's trade_cal endpoint.
Supports incremental imports (skips existing dates).
"""
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# Tushare exchange codes -> internal exchange codes
EXCHANGE_MAP = {
    'CFFEX': 'CFFEX',
    'SHFE': 'SHFE',
    'DCE': 'DCE',
    'CZCE': 'CZCE',
    'INE': 'INE',
    'SSE': 'SSE',
    'SZSE': 'SZSE',
}


class CalendarImporter:
    """Import trade calendar from Tushare API."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            from tzdata_pkg.core.db import SQLitePool
            self._pool = SQLitePool(db_path)
        else:
            from tzdata_pkg.storage.db_registry import DBRegistry
            self._pool = DBRegistry().get_pool('market')

        self._client = None  # Lazy init

    def _get_client(self):
        """Lazy-init Tushare client."""
        if self._client is None:
            from tzdata_pkg.config import get_tushare_config
            from tzdata_pkg.download.tushare.client import TushareClient
            tushare_cfg = get_tushare_config()
            self._client = TushareClient(token=tushare_cfg.token)
        return self._client

    def _fetch_from_tushare(
        self, exchange: str, start_date: str, end_date: str
    ) -> Optional[pd.DataFrame]:
        """Fetch trade calendar from Tushare API."""
        client = self._get_client()
        tushare_start = start_date.replace('-', '')
        tushare_end = end_date.replace('-', '')
        tushare_exchange = EXCHANGE_MAP.get(exchange, exchange)
        return client.trade_cal(
            exchange=tushare_exchange,
            start_date=tushare_start,
            end_date=tushare_end,
        )

    def import_calendar(
        self,
        exchange: str = 'CFFEX',
        start_date: str = None,
        end_date: str = None,
    ) -> dict:
        """
        Import trade calendar from Tushare.

        Args:
            exchange: Exchange code (CFFEX, SHFE, etc.)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            dict with 'inserted' count and 'exchange' info
        """
        logger.info(f"Importing calendar for {exchange}: {start_date} to {end_date}")

        df = self._fetch_from_tushare(exchange, start_date, end_date)
        if df is None or df.empty:
            logger.warning("No data returned from Tushare")
            return {'inserted': 0, 'exchange': exchange}

        inserted = 0
        with self._pool.transaction() as conn:
            for _, row in df.iterrows():
                cal_date = str(row['cal_date'])
                is_open = int(row.get('is_open', 1))

                # Convert YYYYMMDD to YYYY-MM-DD
                trade_date = f"{cal_date[:4]}-{cal_date[4:6]}-{cal_date[6:8]}"

                # Check if already exists (incremental import)
                existing = conn.execute(
                    "SELECT 1 FROM trade_calendar WHERE trade_date = ? AND exchange_code = ?",
                    (trade_date, exchange)
                ).fetchone()

                if existing:
                    continue

                # Insert exchange-specific record
                conn.execute("""
                    INSERT INTO trade_calendar
                        (trade_date, exchange_code, product_code, is_holiday)
                    VALUES (?, ?, '', ?)
                """, (trade_date, exchange, 0 if is_open == 1 else 1))

                # Also insert 'ALL' exchange record (for unified queries)
                existing_all = conn.execute(
                    "SELECT 1 FROM trade_calendar WHERE trade_date = ? AND exchange_code = 'ALL'",
                    (trade_date,)
                ).fetchone()

                if not existing_all:
                    conn.execute("""
                        INSERT INTO trade_calendar
                            (trade_date, exchange_code, product_code, is_holiday)
                        VALUES (?, 'ALL', '', ?)
                    """, (trade_date, 0 if is_open == 1 else 1))

                inserted += 1

        logger.info(f"Imported {inserted} calendar records for {exchange}")
        return {'inserted': inserted, 'exchange': exchange}
