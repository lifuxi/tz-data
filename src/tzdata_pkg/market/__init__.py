"""
Realtime market data module for tz-data.

Handles multi-source data ingestion, normalization, quality validation,
and real-time snapshot distribution via Redis.
"""
from tzdata_pkg.market.models import UnifiedMarketData
from tzdata_pkg.market.event_logger import MarketEventLogger
from tzdata_pkg.market.status_service import StatusService
from tzdata_pkg.market.quality_validator import QualityValidator
from tzdata_pkg.market.adapter import MarketDataAdapter

__all__ = [
    "UnifiedMarketData",
    "MarketEventLogger",
    "StatusService",
    "QualityValidator",
    "MarketDataAdapter",
]
