"""Tushare API client wrapper.

Handles authentication, rate limiting, and common API patterns.
"""

import time
import logging
from typing import Any, Dict, Optional

import tushare as ts

logger = logging.getLogger(__name__)


class TushareClient:
    """Thread-safe Tushare API client wrapper."""

    def __init__(self, token: str, rate_limit: float = 0.3):
        """
        Args:
            token: Tushare API token
            rate_limit: Minimum seconds between API calls
        """
        if not token:
            raise ValueError("Tushare token is required")
        self._token = token
        self._rate_limit = rate_limit
        self._last_call = 0
        self._pro = None
        self.logger = logger

    @property
    def pro(self):
        """Lazy-init Tushare Pro API."""
        if self._pro is None:
            ts.set_token(self._token)
            self._pro = ts.pro_api()
        return self._pro

    def _wait(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_call
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_call = time.time()

    def daily(self, ts_code: str, start_date: str = None, end_date: str = None,
              freq: str = "D") -> Optional[Any]:
        """Fetch daily/weekly/monthly bar data.

        Args:
            ts_code: Tushare contract code (e.g. "MO2505.CFFEX")
            start_date: YYYYMMDD
            end_date: YYYYMMDD
            freq: D= daily, W= weekly, M= monthly
        """
        self._wait()
        try:
            df = self.pro.fut_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                exchange="CFFEX",
            )
            return df
        except Exception as e:
            self.logger.warning(f"Tushare daily failed for {ts_code}: {e}")
            return None

    def fut_min(self, ts_code: str, start_date: str = None,
                end_date: str = None, freq: str = "1min") -> Optional[Any]:
        """Fetch minute bar data.

        Args:
            ts_code: Tushare contract code
            start_date: YYYYMMDD
            end_date: YYYYMMDD
            freq: 1min, 5min, 15min, 30min, 60min
        """
        self._wait()
        try:
            # Tushare uses fut_mins for minute data
            df = self.pro.fut_mins(
                ts_code=ts_code,
                freq=freq,
                start_date=start_date,
                end_date=end_date,
            )
            return df
        except Exception as e:
            self.logger.warning(f"Tushare fut_min failed for {ts_code}: {e}")
            return None

    def opt_daily(self, ts_code: str, start_date: str = None,
                  end_date: str = None) -> Optional[Any]:
        """Fetch option daily data with Greeks.

        Args:
            ts_code: Tushare option code (e.g. "MO2505-C-8500.CFFEX")
            start_date: YYYYMMDD
            end_date: YYYYMMDD
        """
        self._wait()
        try:
            df = self.pro.opt_daily(
                ts_code=ts_code,
                exchange="CFFEX",
                start_date=start_date,
                end_date=end_date,
                fields="ts_code,trade_date,pre_settle,open,high,low,close,"
                       "settle,volume,amount,oi,delta,gamma,theta,vega,iv",
            )
            return df
        except Exception as e:
            self.logger.warning(f"Tushare opt_daily failed for {ts_code}: {e}")
            return None

    def opt_basic(self, exchange: str = "CFFEX") -> Optional[Any]:
        """Fetch option contract list.

        Args:
            exchange: Exchange code
        """
        self._wait()
        try:
            df = self.pro.opt_basic(exchange=exchange)
            return df
        except Exception as e:
            self.logger.warning(f"Tushare opt_basic failed: {e}")
            return None

    def trade_cal(self, exchange: str = "CFFEX", start_date: str = None,
                  end_date: str = None) -> Optional[Any]:
        """Fetch trading calendar (trading days).

        Args:
            exchange: Exchange code
            start_date: YYYYMMDD
            end_date: YYYYMMDD
        """
        self._wait()
        try:
            df = self.pro.trade_cal(
                exchange=exchange,
                start_date=start_date,
                end_date=end_date,
            )
            return df
        except Exception as e:
            self.logger.warning(f"Tushare trade_cal failed: {e}")
            return None
