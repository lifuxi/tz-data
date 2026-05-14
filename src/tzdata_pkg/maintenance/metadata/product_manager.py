"""
Product configuration manager.
Manages product_config table in market.db.
"""
import logging
import json
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)


class ProductManager:
    @staticmethod
    def create(exchange_code: str, product_code: str, product_name: str,
               product_type: str = None, is_tracked: bool = True) -> int:
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO product_config (exchange_code, product_code, product_name, product_type, is_tracked)
                VALUES (?, ?, ?, ?, ?)
            """, (exchange_code, product_code, product_name, product_type, 1 if is_tracked else 0))
            return cursor.lastrowid

    @staticmethod
    def update(product_id: int, **kwargs) -> bool:
        pool = DBRegistry().get_pool('market')
        fields = ['exchange_code', 'product_code', 'product_name', 'product_type', 'is_tracked']
        updates = []
        params = []
        for f in fields:
            if f in kwargs:
                updates.append(f"{f} = ?")
                params.append(1 if f == 'is_tracked' and kwargs[f] else kwargs[f])
        if not updates:
            return False
        params.append(product_id)
        with pool.transaction() as conn:
            conn.execute(f"UPDATE product_config SET {', '.join(updates)} WHERE id = ?", params)
        return True

    @staticmethod
    def get(product_id: int) -> Optional[dict]:
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            row = conn.execute("SELECT * FROM product_config WHERE id = ?", (product_id,)).fetchone()
            if row:
                return {
                    'id': row[0], 'exchange_code': row[1], 'product_code': row[2],
                    'product_name': row[3], 'product_type': row[4],
                    'is_tracked': bool(row[5]), 'created_at': row[6]
                }
            return None

    @staticmethod
    def list_all(exchange_code: str = None, is_tracked: bool = None) -> list[dict]:
        pool = DBRegistry().get_pool('market')
        query = "SELECT * FROM product_config WHERE 1=1"
        params = []
        if exchange_code:
            query += " AND exchange_code = ?"
            params.append(exchange_code)
        if is_tracked is not None:
            query += " AND is_tracked = ?"
            params.append(1 if is_tracked else 0)
        query += " ORDER BY exchange_code, product_code"
        with pool.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                {'id': r[0], 'exchange_code': r[1], 'product_code': r[2],
                 'product_name': r[3], 'product_type': r[4], 'is_tracked': bool(r[5]), 'created_at': r[6]}
                for r in rows
            ]

    @staticmethod
    def delete(product_id: int) -> bool:
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            conn.execute("DELETE FROM product_config WHERE id = ?", (product_id,))
        return True
