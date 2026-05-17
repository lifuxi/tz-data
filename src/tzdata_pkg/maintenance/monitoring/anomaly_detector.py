"""Anomaly detector for market data.

Detects unusual patterns in:
- Price spikes (adjacent day change > 20%)
- Volume anomalies (volume > 3x 30-day average)
- Zero price with non-zero volume
- Position sudden changes (> 50% day-over-day)
- IV anomalies (IV change > 0.3 day-over-day)
"""
import logging
from datetime import date, timedelta
from typing import Dict, List

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detect anomalies in market data."""

    def __init__(self, market_db_path: str = None):
        if market_db_path:
            from tzdata_pkg.core.db import SQLitePool
            self._pool = SQLitePool(market_db_path)
        else:
            from tzdata_pkg.storage.db_registry import DBRegistry
            self._pool = DBRegistry().get_pool('market')

    def detect_all(self, ref_date: date = None) -> List[Dict]:
        """Run all anomaly checks. Returns list of anomaly records."""
        ref = ref_date or date.today()
        anomalies = []
        anomalies.extend(self._check_price_spikes(ref))
        anomalies.extend(self._check_volume_anomalies(ref))
        anomalies.extend(self._check_zero_prices(ref))
        anomalies.extend(self._check_position_spikes(ref))
        anomalies.extend(self._check_iv_anomalies(ref))
        return anomalies

    def _check_price_spikes(self, ref_date: date) -> List[Dict]:
        """Detect price changes > 20% between adjacent trading days."""
        anomalies = []
        try:
            with self._pool.connection() as conn:
                rows = conn.execute("""
                    SELECT d1.exchange, d1.contract_code, d1.trade_date,
                           d1.close as prev_close, d2.close as curr_close,
                           ROUND(ABS(d2.close - d1.close) / d1.close * 100, 2) as pct_change
                    FROM daily_quotes d1
                    INNER JOIN daily_quotes d2
                        ON d1.exchange = d2.exchange
                        AND d1.contract_code = d2.contract_code
                        AND d2.trade_date > d1.trade_date
                    WHERE d1.trade_date >= ?
                      AND d1.close > 0 AND d2.close > 0
                      AND ABS(d2.close - d1.close) / d1.close > 0.20
                    ORDER BY pct_change DESC
                    LIMIT 50
                """, ((ref_date - timedelta(days=30)).isoformat(),)).fetchall()

                for r in rows:
                    anomalies.append({
                        'type': 'price_spike',
                        'exchange': r[0],
                        'contract': r[1],
                        'date': r[2],
                        'detail': f"price changed {r[3]} -> {r[4]} ({r[5]}%)",
                    })
        except Exception as e:
            logger.debug(f"Price spike check failed: {e}")
        return anomalies

    def _check_volume_anomalies(self, ref_date: date) -> List[Dict]:
        """Detect volume > 3x 30-day average."""
        anomalies = []
        try:
            with self._pool.connection() as conn:
                rows = conn.execute("""
                    SELECT d.exchange, d.contract_code, d.trade_date,
                           d.volume,
                           (SELECT AVG(d2.volume)
                            FROM daily_quotes d2
                            WHERE d2.exchange = d.exchange
                              AND d2.contract_code = d.contract_code
                              AND d2.trade_date < d.trade_date
                              AND d2.trade_date >= date(?, '-30 days')
                           ) as avg_30d
                    FROM daily_quotes d
                    WHERE d.trade_date >= ?
                      AND d.volume > 0
                """, (ref_date.isoformat(), (ref_date - timedelta(days=30)).isoformat())).fetchall()

                for r in rows:
                    if r[4] and r[4] > 0 and r[3] > r[4] * 3:
                        anomalies.append({
                            'type': 'volume_anomaly',
                            'exchange': r[0],
                            'contract': r[1],
                            'date': r[2],
                            'detail': f"volume={r[3]}, 30d_avg={r[4]:.0f}, ratio={r[3]/r[4]:.1f}x",
                        })
        except Exception as e:
            logger.debug(f"Volume anomaly check failed: {e}")
        return anomalies

    def _check_zero_prices(self, ref_date: date) -> List[Dict]:
        """Detect close=0 but volume>0."""
        anomalies = []
        try:
            with self._pool.connection() as conn:
                rows = conn.execute("""
                    SELECT exchange, contract_code, trade_date, volume
                    FROM daily_quotes
                    WHERE trade_date >= ?
                      AND (close = 0 OR close IS NULL)
                      AND volume > 0
                    LIMIT 50
                """, ((ref_date - timedelta(days=7)).isoformat(),)).fetchall()

                for r in rows:
                    anomalies.append({
                        'type': 'zero_price',
                        'exchange': r[0],
                        'contract': r[1],
                        'date': r[2],
                        'detail': f"close=0 but volume={r[3]}",
                    })
        except Exception as e:
            logger.debug(f"Zero price check failed: {e}")
        return anomalies

    def _check_position_spikes(self, ref_date: date) -> List[Dict]:
        """Detect total position changes > 50% day-over-day."""
        anomalies = []
        try:
            with self._pool.connection() as conn:
                rows = conn.execute("""
                    SELECT p1.exchange, p1.contract_code, p1.trade_date,
                           SUM(p1.volume) as curr_total,
                           (SELECT SUM(p2.volume)
                            FROM position_detail p2
                            WHERE p2.exchange = p1.exchange
                              AND p2.contract_code = p1.contract_code
                              AND p2.trade_date = (
                                  SELECT MAX(p3.trade_date)
                                  FROM position_detail p3
                                  WHERE p3.exchange = p1.exchange
                                    AND p3.contract_code = p1.contract_code
                                    AND p3.trade_date < p1.trade_date
                              )
                           ) as prev_total
                    FROM position_detail p1
                    WHERE p1.trade_date >= ?
                    GROUP BY p1.exchange, p1.contract_code, p1.trade_date
                """, ((ref_date - timedelta(days=7)).isoformat(),)).fetchall()

                totals = {}
                for r in rows:
                    key = (r[0], r[1], r[2])
                    totals[key] = (r[3], r[4])

                for (exchange, contract, dt), (curr, prev) in totals.items():
                    if prev and prev > 0 and abs(curr - prev) / prev > 0.5:
                        anomalies.append({
                            'type': 'position_spike',
                            'exchange': exchange,
                            'contract': contract,
                            'date': dt,
                            'detail': f"total position {prev} -> {curr}",
                        })
        except Exception as e:
            logger.debug(f"Position spike check failed: {e}")
        return anomalies

    def _check_iv_anomalies(self, ref_date: date) -> List[Dict]:
        """Detect IV changes > 0.3 (30 percentage points) day-over-day."""
        anomalies = []
        try:
            with self._pool.connection() as conn:
                rows = conn.execute("""
                    SELECT v1.contract_code, v1.trade_date, v1.iv, v2.iv as prev_iv
                    FROM mo_daily_iv_quotes v1
                    INNER JOIN mo_daily_iv_quotes v2
                        ON v1.contract_code = v2.contract_code
                    WHERE v1.trade_date >= ?
                      AND v2.trade_date < v1.trade_date
                      AND v1.iv IS NOT NULL AND v2.iv IS NOT NULL
                    ORDER BY v1.trade_date DESC
                """, ((ref_date - timedelta(days=30)).strftime('%Y%m%d'),)).fetchall()

                seen = set()
                for r in rows:
                    contract = r[0]
                    dt = r[1]
                    key = (contract, dt)
                    if key in seen:
                        continue
                    seen.add(key)

                    iv_curr = r[2]
                    iv_prev = r[3]
                    if iv_curr is not None and iv_prev is not None and abs(iv_curr - iv_prev) > 0.3:
                        anomalies.append({
                            'type': 'iv_anomaly',
                            'contract': contract,
                            'date': dt,
                            'detail': f"IV changed {iv_prev:.3f} -> {iv_curr:.3f} (delta={abs(iv_curr - iv_prev):.3f})",
                        })
        except Exception as e:
            logger.debug(f"IV anomaly check failed: {e}")
        return anomalies
