"""
Tushare data source adapter.
Implements BaseDataSource for Tushare API.
"""
from datetime import date
from typing import Optional
import pandas as pd
import tushare as ts

from tzdata_pkg.maintenance.sources.base_source import BaseDataSource

class TushareSource(BaseDataSource):
    """Tushare API data source adapter."""
    
    def __init__(self, config: dict):
        """
        Initialize Tushare source.
        
        Args:
            config: Configuration dictionary with keys:
                - 'token': Tushare API token
                - 'pro_api': Optional custom API object
        """
        super().__init__('tushare', config)
        
        # Set Tushare token
        token = config.get('token')
        if not token:
            raise ValueError("Tushare token is required in config")
        
        ts.set_token(token)
        self.pro = config.get('pro_api') or ts.pro_api()
    
    def fetch_daily_quotes(
        self,
        contract_code: str,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """
        Fetch daily quotes from Tushare.
        
        Args:
            contract_code: Contract code (e.g., 'IM.CFX')
            start_date: Start date
            end_date: End date
        
        Returns:
            List of daily quote dictionaries
        """
        try:
            # Convert date objects to string format
            start_str = start_date.strftime('%Y%m%d')
            end_str = end_date.strftime('%Y%m%d')
            
            # Fetch data from Tushare
            df = self.pro.fut_daily(
                ts_code=contract_code,
                start_date=start_str,
                end_date=end_str
            )
            
            # Convert DataFrame to list of dictionaries
            result = []
            for _, row in df.iterrows():
                quote = {
                    'trade_date': row['trade_date'],
                    'open': float(row['open']) if pd.notna(row['open']) else None,
                    'high': float(row['high']) if pd.notna(row['high']) else None,
                    'low': float(row['low']) if pd.notna(row['low']) else None,
                    'close': float(row['close']) if pd.notna(row['close']) else None,
                    'settle': float(row['settle']) if pd.notna(row['settle']) else None,
                    'volume': int(row['vol']) if pd.notna(row['vol']) else 0,
                    'turnover': float(row['amount']) if pd.notna(row['amount']) else 0.0,
                    'open_interest': int(row['oi']) if pd.notna(row['oi']) else 0
                }
                result.append(quote)
            
            return result
            
        except Exception as e:
            # Handle Tushare-specific exceptions
            if "invalid token" in str(e).lower():
                raise ValueError("Invalid Tushare token") from e
            elif "limited" in str(e).lower() or "rate" in str(e).lower():
                raise RuntimeError("Tushare rate limit exceeded") from e
            else:
                raise RuntimeError(f"Tushare API error: {e}") from e
    
    def fetch_minute_quotes(
        self,
        contract_code: str,
        trade_date: date,
        frequency: str = '1min'
    ) -> list[dict]:
        """
        Fetch minute quotes from Tushare.
        
        Args:
            contract_code: Contract code
            trade_date: Trading date
            frequency: Frequency ('1min', '5min', etc.)
        
        Returns:
            List of minute quote dictionaries
        """
        try:
            # Convert date to string
            date_str = trade_date.strftime('%Y%m%d')
            
            # Tushare minute data API
            df = self.pro.fut_minutely(
                ts_code=contract_code,
                trade_date=date_str,
                freq=frequency
            )
            
            result = []
            for _, row in df.iterrows():
                quote = {
                    'trade_time': row['time'],
                    'open': float(row['open']) if pd.notna(row['open']) else None,
                    'high': float(row['high']) if pd.notna(row['high']) else None,
                    'low': float(row['low']) if pd.notna(row['low']) else None,
                    'close': float(row['close']) if pd.notna(row['close']) else None,
                    'volume': int(row['vol']) if pd.notna(row['vol']) else 0,
                    'turnover': float(row['amount']) if pd.notna(row['amount']) else 0.0,
                    'open_interest': int(row['oi']) if pd.notna(row['oi']) else 0
                }
                result.append(quote)
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Tushare minute data API error: {e}") from e
    
    def fetch_top20_holdings(
        self,
        contract_code: str,
        trade_date: date
    ) -> list[dict]:
        """
        Fetch top 20 holdings from Tushare.
        
        Args:
            contract_code: Contract code
            trade_date: Trading date
        
        Returns:
            List of holding dictionaries
        """
        try:
            date_str = trade_date.strftime('%Y%m%d')
            
            # Fetch futures holdings data
            df = self.pro.fut_holding(
                trade_date=date_str,
                ts_code=contract_code
            )
            
            result = []
            for _, row in df.iterrows():
                holding = {
                    'member_name': row['broker'],
                    'rank': int(row['broker_rank']) if pd.notna(row['broker_rank']) else 0,
                    'long_volume': int(row['long_vol']) if pd.notna(row['long_vol']) else 0,
                    'short_volume': int(row['short_vol']) if pd.notna(row['short_vol']) else 0,
                    'long_change': int(row['long_vol_chg']) if pd.notna(row['long_vol_chg']) else 0,
                    'short_change': int(row['short_vol_chg']) if pd.notna(row['short_vol_chg']) else 0
                }
                result.append(holding)
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Tushare holdings API error: {e}") from e
    
    def get_latest_date(
        self,
        contract_code: str,
        data_type: str
    ) -> Optional[date]:
        """
        Get the latest available date from Tushare.
        
        Args:
            contract_code: Contract code
            data_type: Type of data ('daily', 'minute', 'holdings')
        
        Returns:
            Latest available date, or None if not available
        """
        try:
            today = date.today().strftime('%Y%m%d')
            
            # Get the latest trading date by fetching recent data
            df = self.pro.fut_daily(
                ts_code=contract_code,
                start_date='20250101',  # Start from early 2025
                end_date=today
            )
            
            if df.empty:
                return None
            
            # Get the latest date from the fetched data
            latest_date_str = df['trade_date'].max()
            if latest_date_str:
                # Convert string date to date object
                year = int(latest_date_str[:4])
                month = int(latest_date_str[4:6])
                day = int(latest_date_str[6:8])
                return date(year, month, day)
            
            return None
            
        except Exception:
            # If API call fails, return None
            return None
