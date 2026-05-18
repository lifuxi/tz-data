"""
QuestDB storage module for time-series market data.
Handles insertion and querying of market data in QuestDB.
"""
import logging
from datetime import date, datetime
from typing import Optional
import pandas as pd

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)


def _make_timestamp(trade_date: str, trade_time: str = "00:00:00") -> str:
    """Build QuestDB-compatible UTC timestamp from trade_date + trade_time.

    QuestDB stores timestamps in UTC. Input is Asia/Shanghai local time.
    """
    # Normalize date format: YYYYMMDD or YYYY-MM-DD
    if len(trade_date) == 8 and trade_date.isdigit():
        trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"

    # Normalize time: HH:MM -> HH:MM:SS
    if len(trade_time) == 5:
        trade_time += ":00"

    return f"{trade_date}T{trade_time}.000000Z"


class QuestDBStore:
    """Storage operations for QuestDB time-series database."""

    @staticmethod
    def _get_conn():
        """Get QuestDB connection, returning None if unavailable."""
        try:
            return DBRegistry().get_questdb_connection()
        except Exception as e:
            logger.debug(f"QuestDB connection not available: {e}")
            return None

    @staticmethod
    def insert_daily_quotes(
        exchange: str,
        contract_code: str,
        product_code: str,
        quotes: list[dict]
    ) -> int:
        """Insert daily quotes into QuestDB daily_quotes table."""
        conn = QuestDBStore._get_conn()
        if not conn:
            return 0

        try:
            inserted = 0
            with conn.cursor() as cur:
                for quote in quotes:
                    trade_date_str = quote.get("trade_date", "")
                    if not trade_date_str:
                        continue
                    ts = _make_timestamp(trade_date_str)

                    cur.execute("""
                        INSERT INTO daily_quotes
                            (ts, exchange, contract_code, product_code,
                             open, high, low, close, settle, prev_settle,
                             volume, turnover, open_interest,
                             daily_change, daily_change_pct, amplitude,
                             source)
                        VALUES
                            (CAST(%s AS TIMESTAMP), %s, %s, %s,
                             %s, %s, %s, %s, %s, %s,
                             %s, %s, %s,
                             %s, %s, %s, %s)
                    """, (
                        ts, exchange, contract_code, product_code,
                        quote.get("open"), quote.get("high"),
                        quote.get("low"), quote.get("close"),
                        quote.get("settle"), quote.get("prev_settle"),
                        quote.get("volume", 0), quote.get("turnover", 0.0),
                        quote.get("open_interest", 0),
                        quote.get("daily_change"), quote.get("daily_change_pct"),
                        quote.get("amplitude"), "exchange",
                    ))
                    inserted += 1

            logger.info(f"Inserted {inserted} daily quotes into QuestDB")
            return inserted
        except Exception as e:
            logger.error(f"Failed to insert daily quotes: {e}")
            return 0

    @staticmethod
    def insert_minute_quotes(
        exchange: str,
        contract_code: str,
        product_code: str,
        quotes: list[dict],
        frequency: str = "1min",
    ) -> int:
        """Insert minute quotes into QuestDB future_minute table.

        Each quote dict must contain trade_date and trade_time (or datetime).
        """
        conn = QuestDBStore._get_conn()
        if not conn:
            return 0

        try:
            inserted = 0
            with conn.cursor() as cur:
                for quote in quotes:
                    trade_date = quote.get("trade_date", "")
                    trade_time = quote.get("trade_time", "")
                    if not trade_date:
                        # Fallback: try to parse from datetime field
                        dt = quote.get("datetime", "")
                        if dt and " " in str(dt):
                            trade_date, trade_time = str(dt).split(" ", 1)
                        else:
                            continue

                    ts = _make_timestamp(trade_date, trade_time)

                    cur.execute("""
                        INSERT INTO future_minute
                            (ts, exchange, contract_code, product_code,
                             open, high, low, close,
                             volume, turnover, open_interest,
                             source)
                        VALUES
                            (CAST(%s AS TIMESTAMP), %s, %s, %s,
                             %s, %s, %s, %s,
                             %s, %s, %s, %s)
                    """, (
                        ts, exchange, contract_code, product_code,
                        quote.get("open"), quote.get("high"),
                        quote.get("low"), quote.get("close"),
                        quote.get("volume", 0), quote.get("turnover", 0.0),
                        quote.get("open_interest", 0),
                        quote.get("source", "tushare"),
                    ))
                    inserted += 1

            logger.info(f"Inserted {inserted} minute quotes ({frequency}) into QuestDB")
            return inserted
        except Exception as e:
            logger.error(f"Failed to insert minute quotes: {e}")
            return 0

    @staticmethod
    def insert_top20_holdings(
        exchange: str,
        contract_code: str,
        product_code: str,
        holdings: list[dict]
    ) -> int:
        """Insert top 20 holdings into QuestDB top20_holdings table."""
        conn = QuestDBStore._get_conn()
        if not conn:
            return 0

        try:
            inserted = 0
            with conn.cursor() as cur:
                for holding in holdings:
                    trade_date = holding.get("trade_date", "")
                    if not trade_date:
                        continue
                    ts = _make_timestamp(trade_date)

                    cur.execute("""
                        INSERT INTO top20_holdings
                            (ts, exchange, contract_code, product_code,
                             member_name, rank,
                             long_volume, short_volume,
                             long_change, short_change)
                        VALUES
                            (CAST(%s AS TIMESTAMP), %s, %s, %s,
                             %s, %s,
                             %s, %s,
                             %s, %s)
                    """, (
                        ts, exchange, contract_code, product_code,
                        holding.get("member_name", ""),
                        holding.get("rank", 0),
                        holding.get("long_volume", 0),
                        holding.get("short_volume", 0),
                        holding.get("long_change", 0),
                        holding.get("short_change", 0),
                    ))
                    inserted += 1

            logger.info(f"Inserted {inserted} holdings records into QuestDB")
            return inserted
        except Exception as e:
            logger.error(f"Failed to insert holdings: {e}")
            return 0

    @staticmethod
    def insert_dataframe(table_name: str, df: pd.DataFrame,
                         timestamp_col: str = "ts") -> int:
        """Insert a pandas DataFrame into QuestDB via batched INSERT."""
        conn = QuestDBStore._get_conn()
        if not conn or df.empty:
            return 0

        try:
            columns = [c for c in df.columns if c != timestamp_col]
            col_list = ", ".join([timestamp_col] + columns)
            placeholders = ", ".join(["%s"] * (len(columns) + 1))

            inserted = 0
            with conn.cursor() as cur:
                for _, row in df.iterrows():
                    ts_val = row.get(timestamp_col)
                    if ts_val is None or pd.isna(ts_val):
                        continue
                    if isinstance(ts_val, (datetime, date)):
                        ts_val = ts_val.isoformat()

                    values = [ts_val] + [row.get(c) for c in columns]
                    cur.execute(
                        f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})",
                        values,
                    )
                    inserted += 1

            logger.info(f"Inserted {inserted} rows into QuestDB.{table_name}")
            return inserted
        except Exception as e:
            logger.error(f"Failed to insert DataFrame into QuestDB: {e}")
            return 0
