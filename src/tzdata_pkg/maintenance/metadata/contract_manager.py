"""
Contract information manager.
Manages contract_info table in market.db.
"""
import logging
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)


class ContractManager:
    @staticmethod
    def create(contract_code: str, exchange_code: str = None, product_code: str = None,
               contract_type: str = None, underlying: str = None, strike_price: float = None,
               listing_date: str = None, expiry_date: str = None, multiplier: float = None,
               tick_size: float = None, status: str = 'active', is_tracked: bool = False) -> int:
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO contract_info (contract_code, exchange_code, product_code, contract_type,
                    underlying_contract, strike_price, listing_date, expiry_date, multiplier, tick_size,
                    status, is_tracked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (contract_code, exchange_code, product_code, contract_type, underlying,
                  strike_price, listing_date, expiry_date, multiplier, tick_size, status, 1 if is_tracked else 0))
            return cursor.lastrowid

    @staticmethod
    def update(contract_id: int, **kwargs) -> bool:
        pool = DBRegistry().get_pool('market')
        fields = ['contract_code', 'exchange_code', 'product_code', 'contract_type',
                  'underlying_contract', 'strike_price', 'listing_date', 'expiry_date',
                  'multiplier', 'tick_size', 'status', 'is_tracked']
        updates, params = [], []
        for f in fields:
            if f in kwargs:
                updates.append(f"{f} = ?")
                params.append(1 if f == 'is_tracked' and kwargs[f] else kwargs[f])
        if not updates:
            return False
        params.append(contract_id)
        with pool.transaction() as conn:
            conn.execute(f"UPDATE contract_info SET {', '.join(updates)} WHERE id = ?", params)
        return True

    @staticmethod
    def get(contract_id: int) -> Optional[dict]:
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            row = conn.execute("SELECT * FROM contract_info WHERE id = ?", (contract_id,)).fetchone()
            if row:
                return {
                    'id': row[0], 'contract_code': row[1], 'exchange_code': row[2],
                    'product_code': row[3], 'contract_type': row[4], 'underlying_contract': row[5],
                    'strike_price': row[6], 'listing_date': row[7], 'expiry_date': row[8],
                    'delisting_date': row[9], 'multiplier': row[10], 'tick_size': row[11],
                    'status': row[12], 'is_tracked': bool(row[13]), 'created_at': row[14]
                }
            return None

    @staticmethod
    def list_all(exchange_code: str = None, product_code: str = None,
                 status: str = None, is_tracked: bool = None) -> list[dict]:
        pool = DBRegistry().get_pool('market')
        query = "SELECT * FROM contract_info WHERE 1=1"
        params = []
        if exchange_code:
            query += " AND exchange_code = ?"
            params.append(exchange_code)
        if product_code:
            query += " AND product_code = ?"
            params.append(product_code)
        if status:
            query += " AND status = ?"
            params.append(status)
        if is_tracked is not None:
            query += " AND is_tracked = ?"
            params.append(1 if is_tracked else 0)
        query += " ORDER BY product_code, contract_code"
        with pool.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                {'id': r[0], 'contract_code': r[1], 'exchange_code': r[2],
                 'product_code': r[3], 'contract_type': r[4], 'underlying_contract': r[5],
                 'strike_price': r[6], 'listing_date': r[7], 'expiry_date': r[8],
                 'delisting_date': r[9], 'multiplier': r[10], 'tick_size': r[11],
                 'status': r[12], 'is_tracked': bool(r[13]), 'created_at': r[14]}
                for r in rows
            ]

    @staticmethod
    def delete(contract_id: int) -> bool:
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            conn.execute("DELETE FROM contract_info WHERE id = ?", (contract_id,))
        return True
