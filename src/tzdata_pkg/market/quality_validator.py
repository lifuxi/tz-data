"""Quality validation for market data snapshots."""

from __future__ import annotations

from datetime import datetime

from tzdata_pkg.market.models import UnifiedMarketData


class QualityValidator:
    """Validate incoming UnifiedMarketData snapshots.

    Validation tiers:
    1. Timeliness — reject data older than threshold
    2. Completeness — reject data missing required fields
    3. Reasonableness — flag (not reject) anomalous values
    4. Option-specific — check Greeks sign consistency
    """

    def __init__(
        self,
        realtime_delay_ms: int = 2000,
        non_realtime_delay_ms: int = 10000,
    ):
        self._realtime_delay = realtime_delay_ms
        self._non_realtime_delay = non_realtime_delay_ms

    def validate(
        self,
        data: UnifiedMarketData,
        is_realtime: bool = True,
    ) -> tuple[str, list[str]]:
        """Validate a data snapshot.

        Returns:
            (quality_level, issues) where quality_level is
            'normal', 'degraded', or 'suspect', and issues is a list
            of human-readable validation failure descriptions.
        """
        issues = []

        # 1. Timeliness
        delay = self._check_timeliness(data, is_realtime)
        if delay is not None:
            issues.append(f"Data stale: {delay}ms delay")
            return "degraded", issues  # stale data is dropped

        # 2. Completeness
        self._check_completeness(data, issues)

        # 3. Reasonableness
        self._check_reasonableness(data, issues)

        # 4. Option-specific
        self._check_option_greeks(data, issues)

        quality = "suspect" if issues else "normal"
        return quality, issues

    def _check_timeliness(self, data: UnifiedMarketData, is_realtime: bool) -> int | None:
        """Check data freshness. Returns delay_ms if stale, None if ok."""
        if data.timestamp <= 0:
            return None
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        delay_ms = now_ms - data.timestamp
        threshold = self._realtime_delay if is_realtime else self._non_realtime_delay
        if delay_ms > threshold:
            return delay_ms
        return None

    def _check_completeness(self, data: UnifiedMarketData, issues: list[str]) -> None:
        """Check required fields are present."""
        required = ["open", "high", "low", "close", "volume"]
        for field in required:
            value = getattr(data, field, None)
            if value is None:
                issues.append(f"Missing required field: {field}")

    def _check_reasonableness(self, data: UnifiedMarketData, issues: list[str]) -> None:
        """Check value reasonableness: price limits, IV bounds, Delta bounds."""
        # Price should be positive
        for field_name in ("open", "high", "low", "close"):
            val = getattr(data, field_name, None)
            if val is not None and val < 0:
                issues.append(f"{field_name} is negative: {val}")

        # High >= Low
        if data.high is not None and data.low is not None and data.high < data.low:
            issues.append(f"High ({data.high}) < Low ({data.low})")

        # IV bounds (0% - 200%)
        if data.implied_volatility is not None:
            if data.implied_volatility < 0 or data.implied_volatility > 2.0:
                issues.append(f"IV out of range: {data.implied_volatility}")

        # Delta bounds (-1 to 1)
        if data.delta is not None:
            if abs(data.delta) > 1.0:
                issues.append(f"Delta out of range: {data.delta}")

    def _check_option_greeks(self, data: UnifiedMarketData, issues: list[str]) -> None:
        """Option-specific checks: Call delta should be positive, Put delta negative."""
        if data.option_type and data.delta is not None:
            if data.option_type.upper() == "CALL" and data.delta < 0:
                issues.append(f"CALL delta should be positive: {data.delta}")
            elif data.option_type.upper() == "PUT" and data.delta > 0:
                issues.append(f"PUT delta should be negative: {data.delta}")
