"""
Minute-level data completeness checker.
Checks if minute data has sufficient records per trading session.
"""
import logging
from datetime import date, timedelta
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)

# Expected minutes per session for Chinese futures exchanges
# Day session: 09:00-11:30 (150 min) + 13:30-15:00 (90 min) = 240 min
# Night session varies by exchange and product
EXPECTED_MINUTES = {
    '1min': {
        'day_only': 240,   # 09:00-11:30 + 13:30-15:00
        'with_night': 480,  # + night session (varies by product)
        'min_threshold': 180,  # Minimum acceptable for day session
    },
    '5min': {
        'day_only': 48,
        'with_night': 96,
        'min_threshold': 36,
    },
    '15min': {
        'day_only': 16,
        'with_night': 32,
        'min_threshold': 12,
    },
    '30min': {
        'day_only': 8,
        'with_night': 16,
        'min_threshold': 6,
    },
    '60min': {
        'day_only': 4,
        'with_night': 8,
        'min_threshold': 3,
    },
}


class MinuteCompletenessChecker:
    """Check minute-level data completeness."""

    @staticmethod
    def _get_expected_count(frequency: str, has_night_session: bool = False) -> int:
        """Get expected number of records per day for a frequency."""
        config = EXPECTED_MINUTES.get(frequency, EXPECTED_MINUTES['1min'])
        return config['with_night'] if has_night_session else config['day_only']

    @staticmethod
    def _get_threshold(frequency: str) -> int:
        """Get minimum acceptable record count per day."""
        config = EXPECTED_MINUTES.get(frequency, EXPECTED_MINUTES['1min'])
        return config['min_threshold']

    @staticmethod
    def check_day_completeness(
        contract_code: str,
        trade_date: date,
        frequency: str = '1min'
    ) -> dict:
        """
        Check completeness for a single trading day.

        Args:
            contract_code: Contract code
            trade_date: Trading date
            frequency: Data frequency

        Returns:
            Dictionary with completeness info
        """
        try:
            from tzdata_pkg.storage.questdb_store import QuestDBStore

            pool = DBRegistry().get_pool('market')

            # Count records for this day in minute_quotes table
            date_str = trade_date.isoformat()
            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*)
                    FROM minute_quotes
                    WHERE contract_code = ?
                      AND trade_date = ?
                      AND frequency = ?
                """, (contract_code, date_str, frequency))

                row = cursor.fetchone()
                actual_count = row[0] if row else 0

            if actual_count == 0:
                return {
                    'trade_date': date_str,
                    'contract_code': contract_code,
                    'frequency': frequency,
                    'actual_count': 0,
                    'expected_count': 0,
                    'completeness_pct': 0.0,
                    'status': 'missing',
                    'warning': 'No minute data found for this date'
                }

            # Determine expected count (day session only, conservative estimate)
            expected_count = MinuteCompletenessChecker._get_expected_count(frequency)
            threshold = MinuteCompletenessChecker._get_threshold(frequency)

            completeness_pct = min(100.0, (actual_count / expected_count) * 100)

            if actual_count >= expected_count * 0.9:
                status = 'complete'
            elif actual_count >= threshold:
                status = 'partial'
            else:
                status = 'incomplete'

            return {
                'trade_date': date_str,
                'contract_code': contract_code,
                'frequency': frequency,
                'actual_count': actual_count,
                'expected_count': expected_count,
                'completeness_pct': round(completeness_pct, 1),
                'status': status,
                'warning': None if status == 'complete' else f'Only {actual_count}/{expected_count} records'
            }

        except Exception as e:
            logger.warning(f"Minute completeness check failed for {contract_code} on {trade_date}: {e}")
            return {
                'trade_date': trade_date.isoformat(),
                'contract_code': contract_code,
                'frequency': frequency,
                'actual_count': 0,
                'status': 'error',
                'warning': str(e)
            }

    @staticmethod
    def check_date_range_completeness(
        catalog_id: int,
        trading_days: list[date],
        frequency: str = '1min'
    ) -> dict:
        """
        Check minute data completeness across a date range.

        Args:
            catalog_id: Catalog ID
            trading_days: List of trading dates to check
            frequency: Data frequency

        Returns:
            Aggregated completeness report
        """
        try:
            pool = DBRegistry().get_pool('market')

            with pool.transaction() as conn:
                cursor = conn.execute("""
                    SELECT contract_code
                    FROM data_catalog
                    WHERE id = ?
                """, (catalog_id,))
                row = cursor.fetchone()
                contract_code = row[0] if row else ''

            day_results = []
            missing_days = 0
            partial_days = 0
            complete_days = 0

            for trading_day in trading_days:
                result = MinuteCompletenessChecker.check_day_completeness(
                    contract_code, trading_day, frequency
                )
                day_results.append(result)

                if result['status'] == 'missing':
                    missing_days += 1
                elif result['status'] == 'partial':
                    partial_days += 1
                elif result['status'] == 'complete':
                    complete_days += 1

            total_days = len(trading_days)
            overall_completeness = (
                (complete_days + partial_days * 0.5) / total_days * 100
                if total_days > 0 else 100.0
            )

            return {
                'catalog_id': catalog_id,
                'contract_code': contract_code,
                'frequency': frequency,
                'total_trading_days': total_days,
                'complete_days': complete_days,
                'partial_days': partial_days,
                'missing_days': missing_days,
                'overall_completeness_pct': round(overall_completeness, 1),
                'day_details': day_results
            }

        except Exception as e:
            logger.error(f"Date range completeness check failed: {e}")
            return {
                'error': str(e),
                'total_trading_days': 0
            }
