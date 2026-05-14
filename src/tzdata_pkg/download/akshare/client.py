"""
Akshare unified client.

Wraps akshare API calls for index, ETF, futures, and component stock data.
Handles encoding issues and provides consistent DataFrame responses.
"""
import logging
import time
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Column mapping for ETF data (Chinese → English)
ETF_COLUMN_MAP = {
    '日期': 'date',
    '开盘': 'open',
    '收盘': 'close',
    '最高': 'high',
    '最低': 'low',
    '成交量': 'volume',
    '成交额': 'amount',
    '涨跌幅': 'pct_change',
    '涨跌额': 'change',
    '换手率': 'turnover_rate',
}

# Column mapping for component stocks
COMPONENT_COLUMN_MAP = {
    '成分代码': 'code',
    '成分名称': 'name',
    '纳入日期': 'include_date',
}

# Retry config for akshare API calls
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def _retry_call(fn, *args, max_retries=MAX_RETRIES, **kwargs):
    """Call akshare API with retry on connection errors."""
    last_err = None
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                delay = RETRY_DELAY * (attempt + 1)
                logger.warning(f"akshare call failed (attempt {attempt+1}/{max_retries}): {e}, retrying in {delay}s")
                time.sleep(delay)
    raise last_err


class AkshareClient:
    """Unified akshare client for MO signal data sources."""

    def __init__(self):
        self.logger = logging.getLogger(f"{self.__class__.__name__}")

    def fetch_index_daily(self, symbol: str) -> pd.DataFrame:
        """
        Fetch index daily bar data.

        Args:
            symbol: Index code with exchange prefix (e.g. 'sh000852' for CSI 1000)

        Returns:
            DataFrame with columns: date, open, close, high, low, volume
        """
        import akshare as ak
        self.logger.info(f"Fetching index daily: {symbol}")
        # Use sina source (more reliable than em on this environment)
        df = _retry_call(ak.stock_zh_index_daily, symbol=symbol)
        if df is None or df.empty:
            return pd.DataFrame()
        # Normalize columns (sina uses volume in 100x scale)
        if 'volume' in df.columns:
            df = df.copy()
            df['volume'] = df['volume'] / 100
        return df

    def fetch_etf_daily(self, etf_code: str,
                        start_date: str = "20200101",
                        end_date: str = "20300101",
                        adjust: str = "qfq") -> pd.DataFrame:
        """
        Fetch ETF daily bar data.

        Args:
            etf_code: ETF code (e.g. '512100')
            start_date: Start date YYYYMMDD
            end_date: End date YYYYMMDD
            adjust: Adjust type — qfq (前复权), hfq (后复权), '' (none)

        Returns:
            DataFrame with Chinese column names (日期, 开盘, 收盘, etc.)
        """
        import akshare as ak
        self.logger.info(f"Fetching ETF daily: {etf_code}")
        df = _retry_call(
            ak.fund_etf_hist_em, symbol=etf_code, period="daily",
            start_date=start_date, end_date=end_date, adjust=adjust
        )
        if df is None or df.empty:
            return pd.DataFrame()
        return df

    def fetch_futures_daily(self, symbol: str) -> pd.DataFrame:
        """
        Fetch futures daily bar data (main contract continuous).

        Args:
            symbol: Futures symbol (e.g. 'IM0' for IM main contract)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, hold, settle
        """
        import akshare as ak
        self.logger.info(f"Fetching futures daily: {symbol}")
        df = _retry_call(ak.futures_zh_daily_sina, symbol=symbol)
        if df is None or df.empty:
            return pd.DataFrame()
        return df

    def fetch_component_stocks(self, index_code: str) -> pd.DataFrame:
        """
        Fetch index component stock list.

        Args:
            index_code: Index code (e.g. '000852' for CSI 1000)

        Returns:
            DataFrame with columns: code, name, include_date
        """
        import akshare as ak
        self.logger.info(f"Fetching components for index: {index_code}")
        df = _retry_call(ak.index_stock_cons, symbol=index_code)
        if df is None or df.empty:
            return pd.DataFrame()
        return df

    def fetch_a50_daily(self, symbol: str = 'FEF') -> pd.DataFrame:
        """
        Fetch A50 futures daily bar data.

        Args:
            symbol: A50 futures symbol (default 'FEF' for SGX FTSE China A50)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, position, s
        """
        import akshare as ak
        self.logger.info(f"Fetching A50 daily: {symbol}")
        df = _retry_call(ak.futures_foreign_hist, symbol=symbol)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
