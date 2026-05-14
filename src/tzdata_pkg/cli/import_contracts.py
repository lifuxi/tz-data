"""
Contract sync from Tushare.
Syncs futures and options contracts from Tushare opt_basic/fut_basic endpoints.
Also handles expired contract detection and expiring contract queries.
"""
import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# Extract variety (product code) from contract symbol
# e.g. IM2606 -> IM, MO2606-C-5500 -> MO
def _extract_product(symbol: str) -> str:
    """Extract product code from contract symbol."""
    for i, c in enumerate(symbol):
        if c.isdigit():
            return symbol[:i]
    return symbol


def _extract_contract_type(call_put: Optional[str]) -> str:
    """Map call_put indicator to contract_type."""
    if call_put is None or pd.isna(call_put):
        return 'futures'
    call_put = str(call_put).upper()
    if call_put == 'C':
        return 'option_call'
    elif call_put == 'P':
        return 'option_put'
    return 'futures'


def _convert_date(date_str: Optional[str]) -> Optional[str]:
    """Convert YYYYMMDD to YYYY-MM-DD."""
    if date_str is None or pd.isna(date_str) or str(date_str).strip() == '':
        return None
    s = str(date_str).strip()
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


class ContractSyncService:
    """Sync contracts from Tushare API."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            from tzdata_pkg.core.db import SQLitePool
            self._pool = SQLitePool(db_path)
        else:
            from tzdata_pkg.storage.db_registry import DBRegistry
            self._pool = DBRegistry().get_pool('market')

        self._client = None

    def _get_client(self):
        if self._client is None:
            from tzdata_pkg.config import get_tushare_config
            from tzdata_pkg.download.tushare.client import TushareClient
            tushare_cfg = get_tushare_config()
            self._client = TushareClient(token=tushare_cfg["token"])
        return self._client

    def _fetch_futures(self, exchange: str) -> Optional[pd.DataFrame]:
        """Fetch futures contracts from Tushare fut_basic."""
        client = self._get_client()
        try:
            return client.pro.fut_basic(
                exchange=exchange,
                fut_type='1',  # futures
                fields='ts_code,symbol,exchange,contract_type,list_date,delist_date'
            )
        except Exception as e:
            logger.warning(f"Tushare fut_basic failed: {e}")
            return None

    def _fetch_options(self, exchange: str) -> Optional[pd.DataFrame]:
        """Fetch options contracts from Tushare opt_basic."""
        client = self._get_client()
        return client.opt_basic(exchange=exchange)

    def sync_futures(self, exchange: str = 'CFFEX') -> dict:
        """
        Sync futures contracts from Tushare.

        Returns:
            dict with 'inserted' count
        """
        logger.info(f"Syncing futures for {exchange}")
        df = self._fetch_futures(exchange)
        if df is None or df.empty:
            return {'inserted': 0}

        inserted = 0
        with self._pool.transaction() as conn:
            for _, row in df.iterrows():
                symbol = str(row.get('symbol', ''))
                if not symbol:
                    continue

                product = _extract_product(symbol)
                list_date = _convert_date(row.get('list_date'))
                delist_date = _convert_date(row.get('delist_date'))

                existing = conn.execute(
                    "SELECT 1 FROM contract_info WHERE contract_code = ?",
                    (symbol,)
                ).fetchone()

                if existing:
                    continue

                conn.execute("""
                    INSERT INTO contract_info
                        (contract_code, exchange_code, product_code, contract_type,
                         listing_date, delisting_date, status)
                    VALUES (?, ?, ?, 'futures', ?, ?, 'active')
                """, (symbol, exchange, product, list_date, delist_date))

                # Ensure product_config exists
                product_exists = conn.execute(
                    "SELECT 1 FROM product_config WHERE exchange_code = ? AND product_code = ?",
                    (exchange, product)
                ).fetchone()

                if not product_exists:
                    conn.execute("""
                        INSERT INTO product_config (exchange_code, product_code, product_name, product_type)
                        VALUES (?, ?, ?, 'index_future')
                    """, (exchange, product, product))

                inserted += 1

        logger.info(f"Inserted {inserted} new futures for {exchange}")
        return {'inserted': inserted, 'exchange': exchange}

    def sync_options(self, exchange: str = 'CFFEX') -> dict:
        """
        Sync options contracts from Tushare.

        Returns:
            dict with 'inserted' count
        """
        logger.info(f"Syncing options for {exchange}")
        df = self._fetch_options(exchange)
        if df is None or df.empty:
            return {'inserted': 0}

        inserted = 0
        with self._pool.transaction() as conn:
            for _, row in df.iterrows():
                symbol = str(row.get('symbol', ''))
                if not symbol:
                    continue

                product = _extract_product(symbol)
                call_put = row.get('call_put', None)
                contract_type = _extract_contract_type(call_put)
                strike = row.get('strike_price', None)
                if strike is not None and pd.isna(strike):
                    strike = None
                else:
                    strike = float(strike) if strike is not None else None

                list_date = _convert_date(row.get('list_date'))
                delist_date = _convert_date(row.get('delist_date'))

                existing = conn.execute(
                    "SELECT 1 FROM contract_info WHERE contract_code = ?",
                    (symbol,)
                ).fetchone()

                if existing:
                    continue

                # Extract underlying contract from symbol (e.g. MO2606-C-5500 -> MO2606)
                underlying = product
                for i, c in enumerate(symbol):
                    if c in ('C', 'P', '-') and i > 0:
                        underlying = symbol[:i]
                        break

                conn.execute("""
                    INSERT INTO contract_info
                        (contract_code, exchange_code, product_code, contract_type,
                         underlying_contract, strike_price, listing_date, delisting_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
                """, (symbol, exchange, product, contract_type, underlying, strike, list_date, delist_date))

                # Ensure product_config exists
                product_exists = conn.execute(
                    "SELECT 1 FROM product_config WHERE exchange_code = ? AND product_code = ?",
                    (exchange, product)
                ).fetchone()

                if not product_exists:
                    conn.execute("""
                        INSERT INTO product_config (exchange_code, product_code, product_name, product_type)
                        VALUES (?, ?, ?, 'index_option')
                    """, (exchange, product, product))

                inserted += 1

        logger.info(f"Inserted {inserted} new options for {exchange}")
        return {'inserted': inserted, 'exchange': exchange}

    def mark_expired(self, reference_date: Optional[date] = None) -> dict:
        """
        Mark contracts with last_trade_date <= reference_date as expired.

        Args:
            reference_date: Date to check against (default: today)

        Returns:
            dict with 'expired' count
        """
        if reference_date is None:
            reference_date = date.today()

        ref_str = reference_date.isoformat()

        with self._pool.transaction() as conn:
            cursor = conn.execute("""
                UPDATE contract_info
                SET status = 'expired'
                WHERE status = 'active'
                  AND last_trade_date IS NOT NULL
                  AND last_trade_date <= ?
            """, (ref_str,))
            expired = cursor.rowcount

        logger.info(f"Marked {expired} contracts as expired (before {ref_str})")
        return {'expired': expired}

    def get_expiring(self, reference_date: Optional[date] = None, days_ahead: int = 30) -> list[dict]:
        """
        Get contracts expiring within the next N days.

        Args:
            reference_date: Starting date (default: today)
            days_ahead: Number of days to look ahead

        Returns:
            List of expiring contract dicts
        """
        if reference_date is None:
            reference_date = date.today()

        from datetime import timedelta
        end_date = reference_date + timedelta(days=days_ahead)

        with self._pool.connection() as conn:
            rows = conn.execute("""
                SELECT contract_code, exchange_code, product_code, contract_type,
                       last_trade_date, strike_price, status
                FROM contract_info
                WHERE status = 'active'
                  AND last_trade_date IS NOT NULL
                  AND last_trade_date BETWEEN ? AND ?
                ORDER BY last_trade_date
            """, (reference_date.isoformat(), end_date.isoformat())).fetchall()

        return [
            {
                'contract_code': row[0],
                'exchange_code': row[1],
                'product_code': row[2],
                'contract_type': row[3],
                'last_trade_date': row[4],
                'strike_price': row[5],
                'status': row[6],
            }
            for row in rows
        ]
