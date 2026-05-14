"""
Data catalog manager.
Manages the data_catalog table in SQLite (tzdata_market.db).
"""
import logging
from typing import Optional
from datetime import datetime

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)


class CatalogManager:
    """Manager for data catalog operations using SQLite."""
    
    @staticmethod
    def create_catalog(
        catalog_name: str,
        exchange_code: str,
        product_code: str,
        data_type: str,
        contract_code: Optional[str] = None,
        frequency: Optional[str] = None,
        data_source: str = 'tushare',
        is_enabled: bool = True,
        sync_mode: str = 'incremental'
    ) -> int:
        """Create a new data catalog entry."""
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        with pool.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO data_catalog (
                    catalog_name, exchange_code, product_code, 
                    contract_code, data_type, frequency,
                    data_source, is_enabled, sync_mode, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                catalog_name, exchange_code, product_code,
                contract_code, data_type, frequency,
                data_source, 1 if is_enabled else 0, sync_mode
            ))
            return cursor.lastrowid
    
    @staticmethod
    def get_catalog(catalog_id: int) -> Optional[dict]:
        """Get a single catalog by ID."""
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        with pool.connection() as conn:
            row = conn.execute("""
                SELECT id, catalog_name, exchange_code, product_code,
                       contract_code, data_type, frequency, data_source,
                       is_enabled, sync_mode, last_sync_at, created_at
                FROM data_catalog
                WHERE id = ?
            """, (catalog_id,)).fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'catalog_name': row[1],
                    'exchange_code': row[2],
                    'product_code': row[3],
                    'contract_code': row[4],
                    'data_type': row[5],
                    'frequency': row[6],
                    'data_source': row[7],
                    'is_enabled': bool(row[8]),
                    'sync_mode': row[9],
                    'last_sync_at': row[10],
                    'created_at': row[11]
                }
            return None
    
    @staticmethod
    def list_catalogs(
        exchange_code: Optional[str] = None,
        product_code: Optional[str] = None,
        is_enabled: Optional[bool] = None
    ) -> list[dict]:
        """List catalogs with optional filters."""
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        query = """
            SELECT id, catalog_name, exchange_code, product_code,
                   contract_code, data_type, frequency, data_source,
                   is_enabled, sync_mode, last_sync_at
            FROM data_catalog
            WHERE 1=1
        """
        params = []
        
        if exchange_code:
            query += " AND exchange_code = ?"
            params.append(exchange_code)
        
        if product_code:
            query += " AND product_code = ?"
            params.append(product_code)
        
        if is_enabled is not None:
            query += " AND is_enabled = ?"
            params.append(1 if is_enabled else 0)
        
        query += " ORDER BY exchange_code, product_code, data_type"
        
        with pool.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            
            return [
                {
                    'id': row[0],
                    'catalog_name': row[1],
                    'exchange_code': row[2],
                    'product_code': row[3],
                    'contract_code': row[4],
                    'data_type': row[5],
                    'frequency': row[6],
                    'data_source': row[7],
                    'is_enabled': bool(row[8]),
                    'sync_mode': row[9],
                    'last_sync_at': row[10]
                }
                for row in rows
            ]
    
    @staticmethod
    def get_enabled_catalogs() -> list[dict]:
        """Get all enabled catalogs."""
        return CatalogManager.list_catalogs(is_enabled=True)
    
    @staticmethod
    def update_last_sync(catalog_id: int, sync_time: datetime):
        """Update the last sync timestamp for a catalog."""
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        with pool.transaction() as conn:
            conn.execute("""
                UPDATE data_catalog
                SET last_sync_at = ?, updated_at = datetime('now')
                WHERE id = ?
            """, (sync_time.isoformat(), catalog_id))
    
    @staticmethod
    def toggle_catalog(catalog_id: int, is_enabled: bool):
        """Enable or disable a catalog."""
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        with pool.transaction() as conn:
            conn.execute("""
                UPDATE data_catalog
                SET is_enabled = ?, updated_at = datetime('now')
                WHERE id = ?
            """, (1 if is_enabled else 0, catalog_id))
    
    @staticmethod
    def delete_catalog(catalog_id: int) -> bool:
        """Delete a catalog."""
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            with pool.transaction() as conn:
                conn.execute("DELETE FROM data_catalog WHERE id = ?", (catalog_id,))
            return True
        except Exception as e:
            logger.error(f"Failed to delete catalog: {e}")
            return False
