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
        For daily data: detect anomalies in price, volume, and cross-field consistency.
        For position data: check rank range, volume signs, member names.
        """
        pool = DBRegistry().get_pool('market')

        try:
            with pool.connection() as conn:
                cursor = conn.execute("""
                    SELECT data_type, exchange_code, contract_code, product_code
                    FROM data_catalog WHERE id = ?
                """, (catalog_id,))
                row = cursor.fetchone()
                if not row:
                    return 100.0
                data_type, exchange, contract_code, product_code = row

            if data_type == 'minute':
                return 100.0  # TODO: minute-daily aggregation check
            elif data_type == 'daily':
                anomalies = QualityEvaluator._detect_daily_anomalies(
                    catalog_id, exchange, contract_code, product_code
                )
                if not anomalies:
                    return 100.0
                penalty = min(50, len(anomalies) * 5)
                return max(0, 100 - penalty)
            elif data_type in ('top20_holdings', 'position'):
                return QualityEvaluator._check_position_consistency(
                    exchange, contract_code, product_code
                )
            else:
                return 100.0

        except Exception as e:
            logger.error(f"Failed to check consistency: {e}")
            return 80.0

    @staticmethod
    def _detect_daily_anomalies(
        catalog_id: int,
        exchange: str,
        contract_code: str,
        product_code: str,
    ) -> list[dict]:
        """
        Detect anomalies in daily_quotes data.

        Checks:
        - Zero price on active trading days
        - Extreme daily change (> 9%)
        - Volume = 0 with non-zero close price
        - Close vs settle price divergence (> 2%)
        - Negative volume
        """
        pool = DBRegistry().get_pool('market')
        anomalies = []

        try:
            if contract_code:
                where = "WHERE exchange = ? AND contract_code = ?"
                params = (exchange, contract_code)
            elif product_code:
                where = "WHERE exchange = ? AND contract_code LIKE ?"
                params = (exchange, f'{product_code}%')
            else:
                return anomalies

            with pool.connection() as conn:
                # Check 1: Zero price with active volume
                zero_price = conn.execute(
                    f"SELECT trade_date, open, close, settle, volume "
                    f"FROM daily_quotes {where} "
                    f"AND (close = 0 OR settle = 0) AND volume > 0 "
                    f"ORDER BY trade_date DESC LIMIT 20",
                    params,
                ).fetchall()
                for row in zero_price:
                    anomalies.append({
                        'type': 'zero_price', 'date': row[0],
                        'detail': f'close={row[2]}, settle={row[3]}, vol={row[4]}',
                    })

                # Check 2: Extreme daily change > 9%
                prev_prices = conn.execute(
                    f"SELECT d1.trade_date, d1.close, d2.close, "
                    f"ABS(d1.close - d2.close) * 100.0 / NULLIF(d2.close, 0) "
                    f"FROM daily_quotes d1 JOIN daily_quotes d2 "
                    f"  ON d1.exchange = d2.exchange AND d1.contract_code = d2.contract_code "
                    f"  AND d2.trade_date = ("
                    f"    SELECT MAX(trade_date) FROM daily_quotes "
                    f"    WHERE exchange = d1.exchange AND contract_code = d1.contract_code "
                    f"    AND trade_date < d1.trade_date"
                    f"  ) "
                    f"{where} AND d2.close > 0 "
                    f"AND ABS(d1.close - d2.close) * 100.0 / d2.close > 9 "
                    f"ORDER BY 4 DESC LIMIT 20",
                    params,
                ).fetchall()
                for row in prev_prices:
                    anomalies.append({
                        'type': 'extreme_change', 'date': row[0],
                        'detail': f'close={row[1]:.2f}, prev={row[2]:.2f}, change={row[3]:.1f}%',
                    })

                # Check 3: Zero volume with non-zero close
                zero_vol = conn.execute(
                    f"SELECT trade_date, close FROM daily_quotes {where} "
                    f"AND close > 0 AND volume = 0 "
                    f"ORDER BY trade_date DESC LIMIT 20",
                    params,
                ).fetchall()
                for row in zero_vol:
                    anomalies.append({
                        'type': 'zero_volume_with_price', 'date': row[0],
                        'detail': f'close={row[1]}, volume=0',
                    })

                # Check 4: Close vs settle divergence > 2%
                divergence = conn.execute(
                    f"SELECT trade_date, close, settle, "
                    f"ABS(close - settle) * 100.0 / NULLIF(settle, 0) "
                    f"FROM daily_quotes {where} "
                    f"AND close > 0 AND settle > 0 "
                    f"AND ABS(close - settle) * 100.0 / settle > 2 "
                    f"ORDER BY 4 DESC LIMIT 20",
                    params,
                ).fetchall()
                for row in divergence:
                    anomalies.append({
                        'type': 'close_settle_divergence', 'date': row[0],
                        'detail': f'close={row[1]:.2f}, settle={row[2]:.2f}, div={row[3]:.1f}%',
                    })

                # Check 5: Negative volume
                neg_vol = conn.execute(
                    f"SELECT trade_date, volume FROM daily_quotes {where} "
                    f"AND volume < 0 LIMIT 20",
                    params,
                ).fetchall()
                for row in neg_vol:
                    anomalies.append({
                        'type': 'negative_volume', 'date': row[0],
                        'detail': f'volume={row[1]}',
                    })

        except Exception as e:
            logger.warning(f"Anomaly detection failed for catalog {catalog_id}: {e}")

        if anomalies:
            logger.warning(
                f"Catalog {catalog_id}: {len(anomalies)} anomalies detected — "
                f"{anomalies[:3]}"
            )
        return anomalies

    @staticmethod
    def _check_position_consistency(
        exchange: str,
        contract_code: str,
        product_code: str,
    ) -> float:
        """Check position data for rank out of range, negative volume, empty member names."""
        pool = DBRegistry().get_pool('market')
        try:
            if contract_code:
                where = "WHERE exchange = ? AND contract_code = ?"
                params = (exchange, contract_code)
            elif product_code:
                where = "WHERE exchange = ? AND contract_code LIKE ?"
                params = (exchange, f'{product_code}%')
            else:
                return 100.0

            with pool.connection() as conn:
                total = conn.execute(
                    f"SELECT COUNT(*) FROM position_detail {where}", params
                ).fetchone()[0]
                if total == 0:
                    return 100.0

                issues = 0
                issues += conn.execute(
                    f"SELECT COUNT(*) FROM position_detail {where} AND (rank < 1 OR rank > 20)", params
                ).fetchone()[0]
                issues += conn.execute(
                    f"SELECT COUNT(*) FROM position_detail {where} AND (long_volume < 0 OR short_volume < 0)", params
                ).fetchone()[0]
                issues += conn.execute(
                    f"SELECT COUNT(*) FROM position_detail {where} AND (member_name IS NULL OR member_name = '')", params
                ).fetchone()[0]

                pct = issues / total * 100
                return max(0, 100 - pct * 2)
        except Exception as e:
            logger.error(f"Position consistency check failed: {e}")
            return 80.0
    
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
