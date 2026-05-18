"""Abstract base class for realtime market data stream drivers."""

from abc import ABC, abstractmethod
from typing import Callable


class BaseMarketDriver(ABC):
    """Base interface for realtime streaming data sources.

    Each driver connects to a specific data source (CTP, Tushare, AKShare, etc.),
    subscribes to symbols, and fires callbacks with raw market data dicts.
    The MarketDataAdapter normalizes these into UnifiedMarketData.
    """

    SOURCE_NAME: str = "base"

    @abstractmethod
    async def connect(self, config: dict) -> None:
        """Establish connection to the data source."""
        ...

    @abstractmethod
    async def subscribe(self, symbols: list[str]) -> None:
        """Subscribe to market data for the given symbols."""
        ...

    @abstractmethod
    async def unsubscribe(self, symbols: list[str]) -> None:
        """Unsubscribe from market data for the given symbols."""
        ...

    @abstractmethod
    def on_data(self, callback: Callable[[dict], None]) -> None:
        """Register a callback to receive raw market data dicts.

        The callback receives a dict with at minimum:
        - symbol, exchange, timestamp, open, high, low, close, volume
        Additional fields depend on the source and asset type.
        """
        ...

    @abstractmethod
    async def heartbeat(self) -> dict:
        """Return driver health metrics: status, latency_ms, error_count, symbols_count."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect from the data source."""
        ...
