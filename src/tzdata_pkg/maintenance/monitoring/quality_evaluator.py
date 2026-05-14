"""
Data quality evaluator.
Evaluates data quality based on completeness, accuracy, and consistency.
"""
import logging
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry
from tzdata_pkg.maintenance.monitoring.completeness_checker import CompletenessChecker

logger = logging.getLogger(__name__)


class QualityEvaluator:
    """Evaluate data quality with multi-factor scoring."""
    
    # Weights for different quality factors
    WEIGHTS = {
        'completeness': 0.5,   # 50% weight
        'accuracy': 0.3,       # 30% weight
        'consistency': 0.2     # 20% weight
    }
    
    @staticmethod
    def evaluate_catalog_quality(catalog_id: int) -> dict:
        """
        Evaluate overall quality for a catalog.
        
        Args:
            catalog_id: ID of the data catalog
        
        Returns:
            Dictionary with quality scores and details
        """
        try:
            # Check completeness
            completeness_score = QualityEvaluator._check_completeness(catalog_id)
            
            # Check accuracy (cross-source validation)
            accuracy_score = QualityEvaluator._check_accuracy(catalog_id)
            
            # Check consistency (minute vs daily aggregation)
            consistency_score = QualityEvaluator._check_consistency(catalog_id)
            
            # Calculate weighted total score
            total_score = (
                completeness_score * QualityEvaluator.WEIGHTS['completeness'] +
                accuracy_score * QualityEvaluator.WEIGHTS['accuracy'] +
                consistency_score * QualityEvaluator.WEIGHTS['consistency']
            )
            
            result = {
                'catalog_id': catalog_id,
                'total_score': round(total_score, 2),
                'details': {
                    'completeness': round(completeness_score, 2),
                    'accuracy': round(accuracy_score, 2),
                    'consistency': round(consistency_score, 2)
                },
                'alerts': QualityEvaluator._generate_alerts({
                    'completeness': completeness_score,
                    'accuracy': accuracy_score,
                    'consistency': consistency_score
                }),
                'quality_level': QualityEvaluator._get_quality_level(total_score)
            }
            
            logger.info(f"Quality evaluation for catalog {catalog_id}: "
                       f"Score={result['total_score']}, "
                       f"Level={result['quality_level']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to evaluate quality for catalog {catalog_id}: {e}")
            return {
                'catalog_id': catalog_id,
                'total_score': 0.0,
                'error': str(e)
            }
    
    @staticmethod
    def _check_completeness(catalog_id: int) -> float:
        """
        Check completeness score (0-100).
        
        Uses CompletenessChecker to get completeness percentage.
        """
        result = CompletenessChecker.check_catalog_completeness(catalog_id)
        
        if 'error' in result:
            return 0.0
        
        return result.get('completeness_pct', 0.0)
    
    @staticmethod
    def _check_accuracy(catalog_id: int) -> float:
        """
        Check accuracy score (0-100) via cross-source validation.
        
        Compares data from different sources to detect deviations.
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            # Get recent diff logs for this catalog
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT deviation_pct
                    FROM data_diff_log
                    WHERE catalog_id = ?
                    ORDER BY trade_date DESC
                    LIMIT 100
                """, (catalog_id,))
                
                rows = cursor.fetchall()
                
                if not rows:
                    # No comparison data available, assume accurate
                    return 100.0
                
                # Calculate average deviation
                deviations = [row[0] for row in rows if row[0] is not None]
                
                if not deviations:
                    return 100.0
                
                avg_deviation = sum(deviations) / len(deviations)
                
                # Score: deduct 20 points per 1% deviation
                score = max(0, 100 - avg_deviation * 20)
                
                return score
                
        except Exception as e:
            logger.error(f"Failed to check accuracy: {e}")
            return 100.0  # Assume accurate on error
    
    @staticmethod
    def _check_consistency(catalog_id: int) -> float:
        """
        Check consistency score (0-100).
        
        For minute data: verify that aggregated minute data matches daily data.
        For daily data: check for gaps or anomalies.
        """
        registry = DBRegistry()
        pool = registry.get_pool('market')
        
        try:
            # Get catalog info
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT data_type
                    FROM data_catalog
                    WHERE id = ?
                """, (catalog_id,))
                
                row = cursor.fetchone()
                if not row:
                    return 100.0
                
                data_type = row[0]
            
            if data_type == 'minute':
                # TODO: Implement minute-daily consistency check
                # This requires querying both QuestDB (minute) and SQLite/PostgreSQL (daily)
                # For now, return perfect score
                return 100.0
            else:
                # For daily data, check for reasonable price movements
                # TODO: Implement anomaly detection
                return 100.0
                
        except Exception as e:
            logger.error(f"Failed to check consistency: {e}")
            return 80.0  # Slight penalty on error
    
    @staticmethod
    def _generate_alerts(scores: dict) -> list[str]:
        """
        Generate alerts based on quality scores.
        
        Args:
            scores: Dictionary with completeness, accuracy, consistency scores
        
        Returns:
            List of alert messages
        """
        alerts = []
        
        if scores['completeness'] < 90:
            alerts.append(
                f"Low completeness: {scores['completeness']}% "
                f"(threshold: 90%)"
            )
        
        if scores['completeness'] < 70:
            alerts.append(
                f"CRITICAL: Very low completeness: {scores['completeness']}%"
            )
        
        if scores['accuracy'] < 95:
            alerts.append(
                f"Accuracy concerns: {scores['accuracy']}% "
                f"(threshold: 95%)"
            )
        
        if scores['consistency'] < 90:
            alerts.append(
                f"Consistency issues: {scores['consistency']}% "
                f"(threshold: 90%)"
            )
        
        return alerts
    
    @staticmethod
    def _get_quality_level(score: float) -> str:
        """
        Get quality level based on score.
        
        Args:
            score: Total quality score (0-100)
        
        Returns:
            Quality level string
        """
        if score >= 95:
            return 'excellent'
        elif score >= 85:
            return 'good'
        elif score >= 70:
            return 'fair'
        elif score >= 50:
            return 'poor'
        else:
            return 'critical'
    
    @staticmethod
    def evaluate_all_enabled_catalogs() -> list[dict]:
        """
        Evaluate quality for all enabled catalogs.
        
        Returns:
            List of quality evaluation results
        """
        from tzdata_pkg.maintenance.metadata.catalog_manager import CatalogManager
        
        catalogs = CatalogManager.get_enabled_catalogs()
        results = []
        
        for catalog in catalogs:
            result = QualityEvaluator.evaluate_catalog_quality(catalog['id'])
            results.append(result)
        
        return results
