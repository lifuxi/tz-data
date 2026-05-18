"""Historical Volatility calculator for underlying indices.

Calculates HV from daily closing prices of underlying indices
(000852 for MO, 000300 for IO, 000016 for HO).
"""

import logging
import math
from datetime import date, timedelta
from typing import Optional

import sqlite3

from tzdata_pkg.config import TZDATA_TRADING_DB

logger = logging.getLogger(__name__)

UNDERLYING_MAP = {
    "MO": "000852",
    "IO": "000300",
    "HO": "000016",
}


class HVCalculator:
    """Calculate Historical Volatility from underlying daily prices."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(TZDATA_TRADING_DB)

    def _get_prices(self, variety: str, days: int) -> list[float]:
        """Get last N+1 closing prices for variety, newest first."""
        code = UNDERLYING_MAP.get(variety)
        if not code:
            return []

        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("""
                SELECT close FROM option_sim_underlying_daily
                WHERE underlying = ? AND close IS NOT NULL AND close > 0
                ORDER BY trade_date DESC
                LIMIT ?
            """, (code, days + 1)).fetchall()
            return [float(r[0]) for r in reversed(rows)]
        finally:
            conn.close()

    def calculate_hv(self, variety: str, window: int = 20) -> Optional[float]:
        """Calculate annualized HV for given variety and window.

        Args:
            variety: MO / IO / HO
            window: Lookback window in trading days (20 or 60)

        Returns:
            Annualized volatility as decimal (0.25 = 25%), or None if insufficient data.
        """
        prices = self._get_prices(variety, window)
        if len(prices) < window + 1:
            logger.warning(f"Insufficient prices for {variety} HV-{window}: got {len(prices)}")
            return None

        # Calculate daily log returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] <= 0:
                continue
            returns.append(math.log(prices[i] / prices[i - 1]))

        if len(returns) < 2:
            return None

        # Standard deviation of returns
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_std = math.sqrt(variance)

        # Annualize
        return daily_std * math.sqrt(252)

    def calculate_hv_series(self, variety: str, window: int = 20) -> list[dict]:
        """Calculate HV time series for all available dates.

        Returns list of {trade_date, hv} dicts.
        """
        code = UNDERLYING_MAP.get(variety)
        if not code:
            return []

        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("""
                SELECT trade_date, close FROM option_sim_underlying_daily
                WHERE underlying = ? AND close IS NOT NULL AND close > 0
                ORDER BY trade_date ASC
            """, (code,)).fetchall()

            if len(rows) < window + 1:
                return []

            prices = [float(r[1]) for r in rows]
            dates = [r[0] for r in rows]

            result = []
            for i in range(window, len(prices)):
                window_prices = prices[i - window: i + 1]
                returns = []
                for j in range(1, len(window_prices)):
                    if window_prices[j - 1] <= 0:
                        continue
                    returns.append(math.log(window_prices[j] / window_prices[j - 1]))

                if len(returns) < 2:
                    continue

                mean = sum(returns) / len(returns)
                variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
                daily_std = math.sqrt(variance)
                hv = daily_std * math.sqrt(252)

                result.append({"trade_date": dates[i], "hv": round(hv, 4)})

            return result
        finally:
            conn.close()

    def calculate_pcr(self, variety: str, trade_date: str) -> dict:
        """Calculate Put/Call ratio for given variety and date.

        Returns {pcr_volume, pcr_oi} or empty dict if no data.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Normalize date format
            td = trade_date.replace("-", "")[:8]

            row = conn.execute("""
                SELECT
                    SUM(CASE WHEN option_type = 'P' THEN volume ELSE 0 END) as put_vol,
                    SUM(CASE WHEN option_type = 'C' THEN volume ELSE 0 END) as call_vol,
                    SUM(CASE WHEN option_type = 'P' THEN open_interest ELSE 0 END) as put_oi,
                    SUM(CASE WHEN option_type = 'C' THEN open_interest ELSE 0 END) as call_oi
                FROM mo_daily_iv_quotes
                WHERE trade_date = ? AND underlying = ?
            """, (td, variety)).fetchone()

            if not row or not row[0] or not row[1]:
                return {}

            put_vol, call_vol, put_oi, call_oi = float(row[0]), float(row[1]), float(row[2] or 0), float(row[3] or 0)

            return {
                "pcr_volume": round(put_vol / call_vol, 4) if call_vol > 0 else 0,
                "pcr_oi": round(put_oi / call_oi, 4) if call_oi > 0 else 0,
            }
        finally:
            conn.close()
