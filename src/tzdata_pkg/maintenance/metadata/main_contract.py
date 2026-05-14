"""
Main contract identification (主力合约识别).
Determines the dominant contract for a product on a given date
based on open interest / volume, with manual override support.
"""
import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


class MainContractService:
    """Identify and manage main (dominant) contracts."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            from tzdata_pkg.core.db import SQLitePool
            self._pool = SQLitePool(db_path)
        else:
            from tzdata_pkg.storage.db_registry import DBRegistry
            self._pool = DBRegistry().get_pool('market')

    def get_main_contract(self, product_code: str, trade_date: date) -> Optional[str]:
        """
        Get the main contract for a product on a given date.

        Priority:
        1. Manual mapping (main_contract_map)
        2. Data-driven: highest open_interest on trade_date
        3. Data-driven fallback: highest volume on trade_date

        Args:
            product_code: Product code (e.g. 'IM', 'IF')
            trade_date: Date to check

        Returns:
            Contract code of main contract, or None
        """
        date_str = trade_date.isoformat()

        with self._pool.connection() as conn:
            # 1. Check manual mapping first
            row = conn.execute("""
                SELECT contract_code FROM main_contract_map
                WHERE product_code = ? AND trade_date = ?
            """, (product_code, date_str)).fetchone()

            if row:
                return row[0]

            # 2. Data-driven: highest open_interest
            row = conn.execute("""
                SELECT dq.contract_code
                FROM daily_quotes dq
                JOIN contract_info ci ON dq.contract_code = ci.contract_code
                WHERE ci.product_code = ?
                  AND dq.trade_date = ?
                  AND dq.open_interest IS NOT NULL
                  AND ci.status = 'active'
                ORDER BY dq.open_interest DESC
                LIMIT 1
            """, (product_code, date_str)).fetchone()

            if row and row[0]:
                return row[0]

            # 3. Fallback: highest volume
            row = conn.execute("""
                SELECT dq.contract_code
                FROM daily_quotes dq
                JOIN contract_info ci ON dq.contract_code = ci.contract_code
                WHERE ci.product_code = ?
                  AND dq.trade_date = ?
                  AND dq.volume IS NOT NULL
                  AND ci.status = 'active'
                ORDER BY dq.volume DESC
                LIMIT 1
            """, (product_code, date_str)).fetchone()

            return row[0] if row else None

    def set_main_contract(self, product_code: str, trade_date: date, contract_code: str) -> None:
        """
        Manually set main contract for a date.

        Args:
            product_code: Product code
            trade_date: Date
            contract_code: Main contract code
        """
        with self._pool.transaction() as conn:
            conn.execute("""
                INSERT INTO main_contract_map (product_code, trade_date, contract_code, method)
                VALUES (?, ?, ?, 'manual')
                ON CONFLICT(product_code, trade_date)
                DO UPDATE SET contract_code = excluded.contract_code, method = 'manual'
            """, (product_code, trade_date.isoformat(), contract_code))

    def get_main_series(self, product_code: str, start: date, end: date) -> list[dict]:
        """
        Get main contract series for a date range.

        Returns:
            List of (trade_date, contract_code, method) dicts
        """
        with self._pool.connection() as conn:
            rows = conn.execute("""
                SELECT trade_date, contract_code, method
                FROM main_contract_map
                WHERE product_code = ?
                  AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date
            """, (product_code, start.isoformat(), end.isoformat())).fetchall()

        return [
            {
                'trade_date': row[0],
                'contract_code': row[1],
                'method': row[2],
            }
            for row in rows
        ]

    def get_rollover_dates(self, product_code: str, start: date, end: date) -> list[dict]:
        """
        Find dates when the main contract changes (rollover dates).

        Returns:
            List of (date, from_contract, to_contract) dicts
        """
        series = self.get_main_series(product_code, start, end)
        rollovers = []

        for i in range(1, len(series)):
            if series[i]['contract_code'] != series[i - 1]['contract_code']:
                rollovers.append({
                    'date': series[i]['trade_date'],
                    'from_contract': series[i - 1]['contract_code'],
                    'to_contract': series[i]['contract_code'],
                })

        return rollovers

    def auto_populate(self, product_code: str, start: date, end: date) -> int:
        """
        Auto-populate main contract mappings based on open interest data.

        For each date in range, find the contract with highest open_interest.

        Returns:
            Number of records inserted
        """
        from datetime import timedelta

        current = start
        inserted = 0
        batch = []

        with self._pool.transaction() as conn:
            while current <= end:
                date_str = current.isoformat()

                # Skip if already has a mapping
                existing = conn.execute(
                    "SELECT 1 FROM main_contract_map WHERE product_code = ? AND trade_date = ?",
                    (product_code, date_str)
                ).fetchone()

                if not existing:
                    row = conn.execute("""
                        SELECT dq.contract_code
                        FROM daily_quotes dq
                        JOIN contract_info ci ON dq.contract_code = ci.contract_code
                        WHERE ci.product_code = ?
                          AND dq.trade_date = ?
                          AND dq.open_interest IS NOT NULL
                          AND ci.status = 'active'
                        ORDER BY dq.open_interest DESC
                        LIMIT 1
                    """, (product_code, date_str)).fetchone()

                    if row and row[0]:
                        batch.append((product_code, date_str, row[0]))

                current += timedelta(days=1)

            if batch:
                conn.executemany("""
                    INSERT INTO main_contract_map (product_code, trade_date, contract_code, method)
                    VALUES (?, ?, ?, 'volume_oi')
                """, batch)
                inserted = len(batch)

        logger.info(f"Auto-populated {inserted} main contract records for {product_code}")
        return inserted
