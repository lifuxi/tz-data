"""
Health snapshot generator.
Generates comprehensive health snapshots for all data catalogs.
"""
import logging
from datetime import date, datetime
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.maintenance.monitoring.completeness_checker import CompletenessChecker
from tzdata_pkg.maintenance.monitoring.quality_evaluator import QualityEvaluator

logger = logging.getLogger(__name__)


class HealthSnapshotGenerator:
    """Generate and store health snapshots for data catalogs."""
    
    @staticmethod
    def generate_snapshot(catalog_id: int) -> dict:
        """
        Generate a health snapshot for a specific catalog.
        
        Args:
            catalog_id: ID of the data catalog
        
        Returns:
            Dictionary with snapshot data
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            # Get completeness info
            completeness_result = CompletenessChecker.check_catalog_completeness(catalog_id)
            
            # Get quality evaluation
            quality_result = QualityEvaluator.evaluate_catalog_quality(catalog_id)
            
            # Extract key metrics
            missing_days = completeness_result.get('missing_days', 0)
            completeness_pct = completeness_result.get('completeness_pct', 0.0)
            quality_score = quality_result.get('total_score', 0.0)
            
            # Determine consistency status
            consistency_score = quality_result.get('details', {}).get('consistency', 100.0)
            if consistency_score >= 95:
                consistency_status = 'consistent'
            elif consistency_score >= 80:
                consistency_status = 'minor_issues'
            else:
                consistency_status = 'inconsistent'
            
            # Get last sync status from sync_task table
            last_sync_status, last_sync_error = HealthSnapshotGenerator._get_last_sync_status(
                catalog_id
            )
            
            # Generate missing dates list (simplified)
            missing_dates = []
            if missing_days > 0 and 'earliest_date' in completeness_result:
                # In production, calculate actual missing dates
                # For now, just indicate there are missing dates
                missing_dates = ["See completeness check for details"]
            
            # Insert or update snapshot (SQLite uses INSERT OR REPLACE)
            with pool.transaction() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO data_health_snapshot (
                        catalog_id, snapshot_date, missing_days,
                        missing_dates, data_quality_score,
                        completeness_pct, consistency_status,
                        last_sync_status, last_sync_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    catalog_id,
                    date.today().isoformat(),
                    missing_days,
                    str(missing_dates),
                    quality_score,
                    completeness_pct,
                    consistency_status,
                    last_sync_status,
                    last_sync_error
                ))
            
            snapshot = {
                'catalog_id': catalog_id,
                'snapshot_date': date.today(),
                'missing_days': missing_days,
                'data_quality_score': quality_score,
                'completeness_pct': completeness_pct,
                'consistency_status': consistency_status,
                'last_sync_status': last_sync_status,
                'quality_level': quality_result.get('quality_level', 'unknown'),
                'alerts': quality_result.get('alerts', [])
            }
            
            logger.info(f"Generated health snapshot for catalog {catalog_id}: "
                       f"Score={quality_score}, Missing={missing_days} days")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to generate snapshot for catalog {catalog_id}: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def _get_last_sync_status(catalog_id: int) -> tuple[str, Optional[str]]:
        """
        Get the status of the last sync task for a catalog.
        
        Returns:
            Tuple of (status, error_message)
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT status, error_message
                    FROM sync_task
                    WHERE catalog_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (catalog_id,))
                
                row = cursor.fetchone()
                
                if row:
                    return (row[0], row[1])
                else:
                    return ('never_synced', None)
                    
        except Exception as e:
            logger.error(f"Failed to get last sync status: {e}")
            return ('unknown', str(e))
    
    @staticmethod
    def generate_all_snapshots() -> list[dict]:
        """
        Generate health snapshots for all enabled catalogs.
        
        Returns:
            List of snapshot results
        """
        from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager
        
        catalogs = CatalogManager.get_enabled_catalogs()
        results = []
        
        logger.info(f"Generating health snapshots for {len(catalogs)} catalogs...")
        
        for catalog in catalogs:
            try:
                result = HealthSnapshotGenerator.generate_snapshot(catalog['id'])
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to generate snapshot for catalog {catalog['id']}: {e}")
                results.append({
                    'catalog_id': catalog['id'],
                    'error': str(e)
                })
        
        logger.info(f"Generated {len(results)} health snapshots")
        
        return results
    
    @staticmethod
    def get_latest_snapshot(catalog_id: int) -> Optional[dict]:
        """
        Get the latest health snapshot for a catalog.
        
        Args:
            catalog_id: ID of the data catalog
        
        Returns:
            Dictionary with snapshot data, or None if not found
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT id, snapshot_date, missing_days,
                           missing_dates, data_quality_score,
                           completeness_pct, consistency_status,
                           last_sync_status, last_sync_error,
                           created_at
                    FROM data_health_snapshot
                    WHERE catalog_id = ?
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """, (catalog_id,))
                
                row = cursor.fetchone()
                
                if row:
                    return {
                        'id': row[0],
                        'catalog_id': catalog_id,
                        'snapshot_date': row[1],
                        'missing_days': row[2],
                        'missing_dates': row[3],
                        'data_quality_score': float(row[4]) if row[4] else 0.0,
                        'completeness_pct': float(row[5]) if row[5] else 0.0,
                        'consistency_status': row[6],
                        'last_sync_status': row[7],
                        'last_sync_error': row[8],
                        'created_at': row[9]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to get latest snapshot: {e}")
            return None
    
    @staticmethod
    def get_all_diffs() -> list[dict]:
        """
        Get diff status for all catalogs (for API endpoint).
        
        Returns:
            List of catalog diff information
        """
        from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager
        
        catalogs = CatalogManager.get_enabled_catalogs()
        results = []
        
        for catalog in catalogs:
            snapshot = HealthSnapshotGenerator.get_latest_snapshot(catalog['id'])
            
            if snapshot:
                results.append({
                    'catalog_id': catalog['id'],
                    'catalog_name': catalog['catalog_name'],
                    'exchange_code': catalog['exchange_code'],
                    'product_code': catalog['product_code'],
                    'data_type': catalog['data_type'],
                    'latest_date': snapshot.get('snapshot_date'),
                    'missing_days': snapshot.get('missing_days', 0),
                    'quality_score': snapshot.get('data_quality_score', 0.0),
                    'sync_status': snapshot.get('last_sync_status', 'unknown')
                })
        
        return results
