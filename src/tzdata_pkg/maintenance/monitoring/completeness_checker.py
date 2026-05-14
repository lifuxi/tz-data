"""
Data completeness checker.
Checks if data is complete by comparing with trading calendar.
"""
import logging
from datetime import date, timedelta
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager

logger = logging.getLogger(__name__)


class CompletenessChecker:
    """Check data completeness against trading calendar."""

    @staticmethod
    def get_trading_calendar(start_date: date, end_date: date,
                             exchange_code: str = 'ALL') -> list[date]:
        """Get trading calendar from the database."""
        return TradeCalendarManager.get_trading_days(start_date, end_date, exchange_code)
    
    @staticmethod
    def check_catalog_completeness(catalog_id: int) -> dict:
        """
        Check completeness for a specific catalog.
        
        Args:
            catalog_id: ID of the data catalog
        
        Returns:
            Dictionary with completeness information
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            # Get catalog info
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT exchange_code, product_code, contract_code, 
                           data_type, frequency
                    FROM data_catalog
                    WHERE id = ?
                """, (catalog_id,))
                
                row = cursor.fetchone()
                if not row:
                    return {'error': f'Catalog {catalog_id} not found'}
                
                exchange_code, product_code, contract_code, data_type, frequency = row
            
            # Get local data status
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT latest_date, earliest_date, total_records
                    FROM data_status_local
                    WHERE catalog_id = ?
                """, (catalog_id,))
                
                status_row = cursor.fetchone()
                
                if not status_row or not status_row[0]:
                    return {
                        'catalog_id': catalog_id,
                        'completeness_pct': 0.0,
                        'missing_days': 0,
                        'status': 'no_data',
                        'message': 'No local data found'
                    }
                
                latest_date = status_row[0]
                earliest_date = status_row[1]
                total_records = status_row[2]
            
            # Calculate expected trading days
            trading_days = CompletenessChecker.get_trading_calendar(
                earliest_date, latest_date
            )
            expected_days = len(trading_days)
            
            # Calculate missing days
            # For minute data, we need to check each day has sufficient records
            if data_type == 'minute':
                missing_days = CompletenessChecker._check_minute_completeness(
                    catalog_id, contract_code, trading_days, frequency
                )
            else:
                # For daily data, compare record count with trading days
                missing_days = max(0, expected_days - total_records)
            
            # Calculate completeness percentage
            completeness_pct = (
                ((expected_days - missing_days) / expected_days * 100)
                if expected_days > 0 else 100.0
            )
            
            result = {
                'catalog_id': catalog_id,
                'exchange_code': exchange_code,
                'product_code': product_code,
                'contract_code': contract_code,
                'data_type': data_type,
                'earliest_date': earliest_date,
                'latest_date': latest_date,
                'expected_days': expected_days,
                'actual_records': total_records,
                'missing_days': missing_days,
                'completeness_pct': round(completeness_pct, 2),
                'status': 'complete' if missing_days == 0 else 'incomplete'
            }
            
            logger.info(f"Completeness check for catalog {catalog_id}: "
                       f"{result['completeness_pct']}% complete")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to check completeness for catalog {catalog_id}: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def _check_minute_completeness(
        catalog_id: int,
        contract_code: str,
        trading_days: list[date],
        frequency: str
    ) -> int:
        """
        Check completeness for minute-level data.
        Uses the dedicated MinuteCompletenessChecker.
        """
        from tzdata_pkg.maintenance.monitoring.minute_completeness import MinuteCompletenessChecker

        report = MinuteCompletenessChecker.check_date_range_completeness(
            catalog_id, trading_days, frequency
        )
        return report.get('missing_days', 0)
    
    @staticmethod
    def check_all_enabled_catalogs() -> list[dict]:
        """
        Check completeness for all enabled catalogs.
        
        Returns:
            List of completeness results
        """
        from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager
        
        catalogs = CatalogManager.get_enabled_catalogs()
        results = []
        
        for catalog in catalogs:
            result = CompletenessChecker.check_catalog_completeness(catalog['id'])
            results.append(result)
        
        return results
