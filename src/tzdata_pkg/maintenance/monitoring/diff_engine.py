"""
Data difference engine.
Compares data from multiple sources to detect discrepancies.
"""
import logging
from datetime import date
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)


class DiffEngine:
    """Compare data from different sources and log differences."""
    
    @staticmethod
    def compare_sources(
        catalog_id: int,
        trade_date: date,
        source_a: str,
        source_b: str,
        field_name: str = 'close',
        threshold_pct: float = 0.5
    ) -> dict:
        """
        Compare a specific field between two data sources.
        
        Args:
            catalog_id: ID of the data catalog
            trade_date: Date to compare
            source_a: First data source name
            source_b: Second data source name
            field_name: Field to compare (e.g., 'close', 'volume')
            threshold_pct: Alert threshold percentage
        
        Returns:
            Dictionary with comparison results
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            # Get catalog info
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT exchange_code, contract_code, data_type
                    FROM data_catalog
                    WHERE id = ?
                """, (catalog_id,))
                
                row = cursor.fetchone()
                if not row:
                    return {'error': f'Catalog {catalog_id} not found'}
                
                exchange_code, contract_code, data_type = row
            
            # TODO: Query actual data from both sources
            # For now, this is a placeholder
            # In production, you would:
            # 1. Query source A (e.g., Tushare) for the data
            # 2. Query source B (e.g., CFFEX official) for the data
            # 3. Compare the values
            
            value_a = None  # Placeholder
            value_b = None  # Placeholder
            
            if value_a is None or value_b is None:
                return {
                    'catalog_id': catalog_id,
                    'trade_date': trade_date,
                    'source_a': source_a,
                    'source_b': source_b,
                    'field_name': field_name,
                    'status': 'skipped',
                    'message': 'Data not available for comparison'
                }
            
            # Calculate deviation
            if value_b != 0:
                deviation_pct = abs(value_a - value_b) / abs(value_b) * 100
            else:
                deviation_pct = 0.0
            
            is_alert = deviation_pct > threshold_pct
            
            # Log the difference
            with pool.transaction() as conn:
                conn.execute("""
                    INSERT INTO data_diff_log (
                        catalog_id, trade_date, source_a, source_b,
                        field_name, value_a, value_b, deviation_pct,
                        threshold_pct, is_alert
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    catalog_id, trade_date.isoformat(), source_a, source_b,
                    field_name, value_a, value_b, deviation_pct,
                    threshold_pct, 1 if is_alert else 0
                ))
            
            result = {
                'catalog_id': catalog_id,
                'trade_date': trade_date,
                'field_name': field_name,
                'value_a': value_a,
                'value_b': value_b,
                'deviation_pct': round(deviation_pct, 4),
                'threshold_pct': threshold_pct,
                'is_alert': is_alert,
                'status': 'alert' if is_alert else 'normal'
            }
            
            if is_alert:
                logger.warning(
                    f"Data discrepancy detected: Catalog {catalog_id}, "
                    f"{trade_date}, {field_name}: "
                    f"{source_a}={value_a}, {source_b}={value_b}, "
                    f"deviation={deviation_pct:.2f}%"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to compare sources: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def get_recent_diffs(catalog_id: int, limit: int = 50) -> list[dict]:
        """
        Get recent difference logs for a catalog.
        
        Args:
            catalog_id: ID of the data catalog
            limit: Maximum number of records to return
        
        Returns:
            List of difference records
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT id, trade_date, source_a, source_b,
                           field_name, value_a, value_b, deviation_pct,
                           is_alert, created_at
                    FROM data_diff_log
                    WHERE catalog_id = ?
                    ORDER BY trade_date DESC
                    LIMIT ?
                """, (catalog_id, limit))
                
                rows = cursor.fetchall()
                
                return [
                    {
                        'id': row[0],
                        'trade_date': row[1],
                        'source_a': row[2],
                        'source_b': row[3],
                        'field_name': row[4],
                        'value_a': float(row[5]) if row[5] else None,
                        'value_b': float(row[6]) if row[6] else None,
                        'deviation_pct': float(row[7]) if row[7] else None,
                        'is_alert': row[8],
                        'created_at': row[9]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Failed to get recent diffs: {e}")
            return []
    
    @staticmethod
    def get_alert_summary(days: int = 7) -> dict:
        """
        Get summary of alerts in the past N days.
        
        Args:
            days: Number of days to look back
        
        Returns:
            Dictionary with alert summary
        """
        from datetime import timedelta
        
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            cutoff_date = (date.today() - timedelta(days=days)).isoformat()
            
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_alerts,
                        COUNT(DISTINCT catalog_id) as affected_catalogs,
                        COUNT(DISTINCT trade_date) as affected_dates
                    FROM data_diff_log
                    WHERE is_alert = 1
                      AND trade_date >= ?
                """, (cutoff_date,))
                
                row = cursor.fetchone()
                
                return {
                    'period_days': days,
                    'total_alerts': row[0],
                    'affected_catalogs': row[1],
                    'affected_dates': row[2]
                }
                
        except Exception as e:
            logger.error(f"Failed to get alert summary: {e}")
            return {}
