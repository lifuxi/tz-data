"""
Exchange configuration manager.
Manages exchange_config table in market.db.
"""
import logging
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)


class ExchangeManager:
    @staticmethod
    def create(exchange_code: str, exchange_name: str, trading_hours: str = None,
               timezone: str = 'Asia/Shanghai', is_active: bool = True) -> int:
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO exchange_config (exchange_code, exchange_name, trading_hours, timezone, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (exchange_code, exchange_name, trading_hours, timezone, 1 if is_active else 0))
            return cursor.lastrowid

    @staticmethod
    def update(exchange_id: int, **kwargs) -> bool:
        pool = DBRegistry().get_pool('market')
        fields = ['exchange_code', 'exchange_name', 'trading_hours', 'timezone', 'is_active']
        updates = []
        params = []
        for f in fields:
            if f in kwargs:
                updates.append(f"{f} = ?")
                params.append(1 if f == 'is_active' and kwargs[f] else kwargs[f])
        if not updates:
            return False
        params.append(exchange_id)
        with pool.transaction() as conn:
            conn.execute(f"UPDATE exchange_config SET {', '.join(updates)} WHERE id = ?", params)
        return True

    @staticmethod
    def get(exchange_id: int) -> Optional[dict]:
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            row = conn.execute("SELECT * FROM exchange_config WHERE id = ?", (exchange_id,)).fetchone()
            if row:
                return {
                    'id': row[0], 'exchange_code': row[1], 'exchange_name': row[2],
                    'trading_hours': row[3], 'timezone': row[4],
                    'is_active': bool(row[5]), 'created_at': row[6]
                }
            return None

    @staticmethod
    def list_all(is_active: bool = None) -> list[dict]:
        pool = DBRegistry().get_pool('market')
        query = "SELECT * FROM exchange_config"
        params = []
        if is_active is not None:
            query += " WHERE is_active = ?"
            params.append(1 if is_active else 0)
        query += " ORDER BY exchange_code"
        with pool.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                {'id': r[0], 'exchange_code': r[1], 'exchange_name': r[2],
                 'trading_hours': r[3], 'timezone': r[4], 'is_active': bool(r[5]), 'created_at': r[6]}
                for r in rows
            ]

    @staticmethod
    def delete(exchange_id: int) -> bool:
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            conn.execute("DELETE FROM exchange_config WHERE id = ?", (exchange_id,))
        return True
