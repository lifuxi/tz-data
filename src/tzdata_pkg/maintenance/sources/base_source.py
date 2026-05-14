"""
Base data source adapter.
Defines the interface for all data source implementations.
"""
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BaseDataSource(ABC):
    """Abstract base class for data source adapters."""
    
    def __init__(self, source_name: str, config: dict):
        """
        Initialize data source.
        
        Args:
            source_name: Name of the data source (e.g., 'tushare', 'cffex')
            config: Configuration dictionary (API keys, endpoints, etc.)
        """
        self.source_name = source_name
        self.config = config
        logger.info(f"Initialized data source: {source_name}")
    
    @abstractmethod
    def fetch_daily_quotes(
        self,
        contract_code: str,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """
        Fetch daily quotes for a contract.
        
        Args:
            contract_code: Contract code (e.g., 'IM2506')
            start_date: Start date
            end_date: End date
        
        Returns:
            List of daily quote dictionaries with keys:
            - trade_date: str (YYYY-MM-DD)
            - open: float
            - high: float
            - low: float
            - close: float
            - settle: float
            - volume: int
            - turnover: float
            - open_interest: int
        """
        pass
    
    @abstractmethod
    def fetch_minute_quotes(
        self,
        contract_code: str,
        trade_date: date,
        frequency: str = '1min'
    ) -> list[dict]:
        """
        Fetch minute-level quotes for a contract.
        
        Args:
            contract_code: Contract code
            trade_date: Trading date
            frequency: Frequency ('1min', '5min', etc.)
        
        Returns:
            List of minute quote dictionaries with keys:
            - trade_time: str (HH:MM:SS)
            - open: float
            - high: float
            - low: float
            - close: float
            - volume: int
            - turnover: float
            - open_interest: int
        """
        pass
    
    @abstractmethod
    def fetch_top20_holdings(
        self,
        contract_code: str,
        trade_date: date
    ) -> list[dict]:
        """
        Fetch top 20 member holdings for a contract.
        
        Args:
            contract_code: Contract code
            trade_date: Trading date
        
        Returns:
            List of holding dictionaries with keys:
            - member_name: str
            - rank: int
            - long_volume: int
            - short_volume: int
            - long_change: int
            - short_change: int
        """
        pass
    
    @abstractmethod
    def get_latest_date(
        self,
        contract_code: str,
        data_type: str
    ) -> Optional[date]:
        """
        Get the latest available date from the remote source.
        
        Args:
            contract_code: Contract code
            data_type: Type of data ('daily', 'minute', 'holdings')
        
        Returns:
            Latest available date, or None if not available
        """
        pass
    
    def validate_credentials(self) -> bool:
        """
        Validate API credentials or connection.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        return True
    
    def get_rate_limit_info(self) -> dict:
        """
        Get rate limit information for this data source.
        
        Returns:
            Dictionary with rate limit info:
            - requests_per_minute: int
            - requests_per_day: int
            - current_usage: int
        """
        return {
            'requests_per_minute': 60,
            'requests_per_day': 10000,
            'current_usage': 0
        }
    
    def __repr__(self):
        return f"{self.__class__.__name__}(source='{self.source_name}')"
