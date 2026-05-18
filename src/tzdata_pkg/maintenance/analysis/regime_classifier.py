"""Market regime classifier.

Analyzes price and volume data to classify the current market state.
Writes to market_regime table in tzdata_analysis.db.

Regime types:
- trending_up: Strong upward momentum
- trending_down: Strong downward momentum
- range: Sideways, low volatility
- volatile: High volatility, no clear trend

Usage:
    from tzdata_pkg.maintenance.analysis.regime_classifier import RegimeClassifier
    classifier = RegimeClassifier(registry)
    classifier.classify_daily("2025-03-10")
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

REGIME_TRENDING_UP = "trending_up"
REGIME_TRENDING_DOWN = "trending_down"
REGIME_RANGE = "range"
REGIME_VOLATILE = "volatile"


class RegimeClassifier:
    """Classify market regime from price/volume data."""

    def __init__(self, registry):
        self.registry = registry

    def _analysis_pool(self):
        return self.registry.get_pool("analysis")

    def _market_pool(self):
        return self.registry.get_pool("market")

    # ── Daily Classification ─────────────────────────────────

    def classify_daily(self, trade_date: str, lookback: int = 20) -> dict | None:
        """Classify market regime for a given date.

        Uses lookback days of price data to compute:
        - Moving average trend direction
        - Volatility (ATR-like measure)
        - Volume trend

        Args:
            trade_date: YYYY-MM-DD
            lookback: Number of days for calculation

        Returns:
            Regime dict or None if insufficient data
        """
        pool = self._market_pool()
        with pool.connection() as conn:
            # Get recent daily prices for main contracts
            rows = conn.execute("""
                SELECT trade_date, contract_code, open, high, low, close, volume
                FROM daily_quotes
                WHERE trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT ?
            """, (trade_date, lookback * 2)).fetchall()

        if len(rows) < lookback:
            logger.warning(f"RegimeClassifier: insufficient data for {trade_date} ({len(rows)} < {lookback})")
            return None

        # Group by contract and classify each
        contracts = {}
        for row in rows:
            code = row[1]
            if code not in contracts:
                contracts[code] = []
            contracts[code].append({
                "trade_date": row[0],
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "volume": row[6],
            })

        results = []
        for contract_code, prices in contracts.items():
            if len(prices) < lookback:
                continue

            prices.reverse()  # oldest first
            regime = self._classify_contract(contract_code, trade_date, prices, lookback)
            if regime:
                results.append(regime)

        # Save to DB
        self._save_regimes(results)
        logger.info(f"RegimeClassifier: {len(results)} regimes classified for {trade_date}")
        return results[0] if results else None

    def _classify_contract(self, contract: str, trade_date: str,
                           prices: list[dict], lookback: int) -> dict:
        """Classify regime for a single contract."""

        closes = [p["close"] for p in prices[-lookback:]]
        highs = [p["high"] for p in prices[-lookback:]]
        lows = [p["low"] for p in prices[-lookback:]]
        volumes = [p.get("volume") or 0 for p in prices[-lookback:]]

        # Trend: compare short vs long MA
        short_ma = sum(closes[-5:]) / min(5, len(closes))
        long_ma = sum(closes) / len(closes)
        trend_strength = abs(short_ma - long_ma) / long_ma if long_ma else 0

        # Volatility: average true range proxy
        true_ranges = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)
        avg_tr = sum(true_ranges) / len(true_ranges) if true_ranges else 0
        volatility_level = avg_tr / long_ma if long_ma else 0

        # Volume trend
        vol_first_half = sum(volumes[:len(volumes) // 2])
        vol_second_half = sum(volumes[len(volumes) // 2:])
        volume_trend = vol_second_half / vol_first_half if vol_first_half else 1.0

        # Classify regime
        regime_type = self._determine_regime(
            trend_strength, volatility_level, closes[-1] > closes[0]
        )

        # Regime score: 0-1 composite confidence
        regime_score = min(1.0, trend_strength * 2 + (1 - volatility_level) * 0.5)

        # IV regime (simplified — use volatility percentiles)
        iv_regime = self._classify_iv(volatility_level, closes)

        return {
            "trade_date": trade_date,
            "regime_type": regime_type,
            "contract_code": contract,
            "trend_strength": round(trend_strength, 4),
            "volatility_level": round(volatility_level, 4),
            "volume_trend": round(volume_trend, 3),
            "iv_regime": iv_regime,
            "regime_score": round(regime_score, 3),
        }

    def _determine_regime(self, trend_strength: float,
                          volatility_level: float,
                          is_uptrend: bool) -> str:
        """Determine regime type from metrics."""

        # High volatility → volatile regime
        if volatility_level > 0.03:
            return REGIME_VOLATILE

        # Strong trend
        if trend_strength > 0.01:
            return REGIME_TRENDING_UP if is_uptrend else REGIME_TRENDING_DOWN

        # Weak trend, low volatility → range
        return REGIME_RANGE

    def _classify_iv(self, volatility_level: float, closes: list[float]) -> str:
        """Simplified IV regime classification."""
        if len(closes) < 10:
            return "unknown"

        # Use recent volatility percentile
        recent_vol = volatility_level
        if recent_vol > 0.025:
            return "high_iv"
        elif recent_vol < 0.01:
            return "low_iv"
        elif len(closes) > 1 and closes[-1] > closes[-5]:
            return "rising_iv"
        else:
            return "falling_iv"

    def _save_regimes(self, regimes: list[dict]) -> int:
        """Save regimes to market_regime table."""
        if not regimes:
            return 0

        pool = self._analysis_pool()
        count = 0
        with pool.connection() as conn:
            for r in regimes:
                try:
                    conn.execute("""
                        INSERT INTO market_regime
                            (trade_date, regime_type, contract_code,
                             trend_strength, volatility_level, volume_trend,
                             iv_regime, regime_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        r["trade_date"], r["regime_type"], r["contract_code"],
                        r["trend_strength"], r["volatility_level"], r["volume_trend"],
                        r["iv_regime"], r["regime_score"],
                    ))
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to save regime: {e}")

        return count

    # ── Regime Queries ────────────────────────────────────────

    def get_current_regime(self, contract_code: str = None) -> list[dict]:
        """Get the latest regime classification."""
        pool = self._analysis_pool()
        where = ""
        params: list = []
        if contract_code:
            where = "WHERE contract_code = ?"
            params.append(contract_code)

        with pool.connection() as conn:
            cursor = conn.execute(f"""
                SELECT trade_date, regime_type, contract_code,
                       trend_strength, volatility_level, volume_trend,
                       iv_regime, regime_score
                FROM market_regime
                {where}
                ORDER BY trade_date DESC
                LIMIT 10
            """, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def get_regime_history(self, days: int = 30) -> list[dict]:
        """Get regime history for the past N days."""
        pool = self._analysis_pool()
        with pool.connection() as conn:
            cursor = conn.execute("""
                SELECT trade_date, regime_type, contract_code,
                       trend_strength, volatility_level, regime_score
                FROM market_regime
                ORDER BY trade_date DESC
                LIMIT ?
            """, (days,))
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
