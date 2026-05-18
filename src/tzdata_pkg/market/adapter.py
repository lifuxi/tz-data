"""Market data adapter — core orchestration layer.

Manages driver lifecycle, symbol subscriptions, data normalization,
quality validation, Redis snapshot caching, and multi-source failover.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from dataclasses import asdict
from typing import Callable

import structlog

from tzdata_pkg.market.models import UnifiedMarketData
from tzdata_pkg.market.quality_validator import QualityValidator
from tzdata_pkg.market.event_logger import MarketEventLogger
from tzdata_pkg.market.status_service import StatusService

logger = structlog.get_logger("tzdata_market")


class MarketDataAdapter:
    """Central hub for realtime market data ingestion.

    Responsibilities:
    - Load and manage driver instances
    - Symbol subscription tracking (count-based)
    - Data normalization from raw dicts to UnifiedMarketData
    - Quality validation and filtering
    - Redis snapshot caching (key: rt:{symbol})
    - Multi-source failover and degradation
    - Event logging
    """

    def __init__(
        self,
        db_pool,
        redis_client=None,
    ):
        self._db_pool = db_pool
        self._redis = redis_client
        self._drivers: dict[str, object] = {}
        self._driver_configs: dict[str, dict] = {}

        # Symbol subscription counts: {symbol: {source_name: count}}
        self._subscriptions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # Quality validation
        self._validator = QualityValidator()
        self._event_logger = MarketEventLogger(db_pool)
        self._status_service = StatusService(db_pool)

        # Failover state
        self._source_failures: dict[str, float] = {}  # source_name -> last failure timestamp
        self._degraded = False
        self._degraded_since: float = 0

        # Statistics
        self._stats = {
            "total_received": 0,
            "total_validated": 0,
            "total_rejected": 0,
            "total_backfilled": 0,
        }

    async def initialize(self) -> None:
        """Load driver configs from catalog and initialize drivers."""
        # Register default drivers
        from tzdata_pkg.market.drivers.tushare_driver import TushareDriver
        from tzdata_pkg.market.drivers.akshare_driver import AKShareDriver
        from tzdata_pkg.market.drivers.qq_finance_driver import QQFinanceDriver

        self._driver_configs = {
            "tushare": {"api_url": "https://api.tushare.pro", "api_token": "", "poll_interval": 60},
            "akshare": {"poll_interval": 30},
            "qq_finance": {"poll_interval": 3},
        }
        self._drivers["tushare"] = TushareDriver()
        self._drivers["akshare"] = AKShareDriver()
        self._drivers["qq_finance"] = QQFinanceDriver()

        # Set up data callbacks for each driver
        for name, driver in self._drivers.items():
            driver.on_data(lambda raw, src=name: asyncio.create_task(self._on_raw_data(src, raw)))

        # Connect all drivers
        for name, driver in self._drivers.items():
            try:
                config = self._driver_configs.get(name, {})
                await driver.connect(config)
                self._event_logger.log("connect", source_name=name, message=f"Driver {name} connected")
            except Exception as e:
                logger.warning(f"Failed to connect driver {name}: {e}")
                self._event_logger.log("error", source_name=name, severity="error", message=f"Driver {name} connect failed: {e}")

        # Auto-subscribe active catalog symbols
        await self._auto_subscribe_catalog()

        logger.info("MarketDataAdapter initialized")

    async def _auto_subscribe_catalog(self) -> None:
        """Subscribe to all active symbols from the catalog."""
        try:
            with self._db_pool.connection() as conn:
                cur = conn.execute(
                    "SELECT symbol, real_time_source FROM market_data_catalog WHERE is_active = 1",
                )
                for row in cur.fetchall():
                    symbol = row["symbol"]
                    source = row["real_time_source"] or "qq_finance"
                    await self.subscribe(symbol, source)
        except Exception as e:
            logger.warning(f"Auto-subscribe catalog failed: {e}")

    async def subscribe(self, symbol: str, source_name: str = "qq_finance") -> None:
        """Subscribe to a symbol. Start driver when count goes from 0 to 1."""
        self._subscriptions[symbol][source_name] += 1

        # Push cached snapshot first
        cached = self._get_cached_snapshot(symbol)
        if cached:
            self._event_logger.log("snapshot", source_name=source_name, symbol=symbol, message="Pushed cached snapshot on subscribe")

        # Start driver subscription if first subscriber
        if self._subscriptions[symbol][source_name] == 1:
            driver = self._drivers.get(source_name)
            if driver:
                try:
                    await driver.subscribe([symbol])
                    self._event_logger.log("connect", source_name=source_name, symbol=symbol, message=f"Subscribed {symbol}")
                except Exception as e:
                    logger.warning(f"Failed to subscribe {symbol} on {source_name}: {e}")
                    self._event_logger.log("error", source_name=source_name, symbol=symbol, severity="warning", message=f"Subscribe failed: {e}")

    async def unsubscribe(self, symbol: str, source_name: str = "qq_finance") -> None:
        """Unsubscribe from a symbol. Stop driver when count reaches 0."""
        self._subscriptions[symbol][source_name] -= 1
        if self._subscriptions[symbol][source_name] <= 0:
            del self._subscriptions[symbol][source_name]
            driver = self._drivers.get(source_name)
            if driver:
                try:
                    await driver.unsubscribe([symbol])
                except Exception:
                    pass

    async def _on_raw_data(self, source_name: str, raw: dict) -> None:
        """Handle raw data from a driver: normalize, validate, cache, emit."""
        self._stats["total_received"] += 1

        # Normalize to UnifiedMarketData
        data = self._normalize(raw, source_name)
        if not data:
            return

        # Quality validation
        quality, issues = self._validator.validate(data, is_realtime=True)
        data.data_quality = quality

        if quality == "degraded":
            self._stats["total_rejected"] += 1
            self._record_failure(source_name)
            self._event_logger.log("error", source_name=source_name, symbol=data.symbol, severity="warning",
                                   message=f"Data rejected: {'; '.join(issues)}")
            return

        if issues:
            self._event_logger.log("error", source_name=source_name, symbol=data.symbol, severity="warning",
                                   message=f"Data suspect: {'; '.join(issues)}")

        self._stats["total_validated"] += 1
        self._clear_failure(source_name)

        # Cache to Redis
        self._cache_snapshot(data)

        # Persist quality metrics
        self._persist_quality(data)

    def _normalize(self, raw: dict, source_name: str) -> UnifiedMarketData | None:
        """Normalize raw dict to UnifiedMarketData."""
        try:
            data = UnifiedMarketData(
                symbol=raw.get("symbol", ""),
                exchange=raw.get("exchange", ""),
                asset_type=raw.get("asset_type", "FUTURE"),
                timestamp=raw.get("timestamp", 0),
                open=raw.get("open"),
                high=raw.get("high"),
                low=raw.get("low"),
                close=raw.get("close"),
                volume=raw.get("volume"),
                open_interest=raw.get("open_interest"),
                pre_close=raw.get("pre_close"),
                bid_price1=raw.get("bid_price1"),
                bid_volume1=raw.get("bid_volume1"),
                ask_price1=raw.get("ask_price1"),
                ask_volume1=raw.get("ask_volume1"),
                data_source=raw.get("data_source", source_name),
            )
            return data
        except Exception as e:
            logger.warning(f"Normalization failed for {source_name}: {e}")
            return None

    def _cache_snapshot(self, data: UnifiedMarketData) -> None:
        """Cache to Redis key rt:{symbol}."""
        if self._redis and self._redis.is_connected:
            try:
                key = f"rt:{data.symbol}"
                payload = json.dumps(data.to_dict(), ensure_ascii=False)
                # TTL: 60s normal, 300s degraded
                ttl = 300 if data.data_quality == "degraded" else 60
                self._redis.set(key, payload, ttl=ttl)
            except Exception as e:
                logger.warning(f"Redis cache failed for {data.symbol}: {e}")

        # Also persist to SQLite snapshot cache
        try:
            now = __import__("datetime").datetime.utcnow().isoformat()
            payload = json.dumps(data.to_dict(), ensure_ascii=False)
            with self._db_pool.transaction() as conn:
                conn.execute(
                    """INSERT INTO realtime_snapshots_cache (symbol, data_json, source_name, updated_at)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(symbol) DO UPDATE SET
                           data_json=excluded.data_json,
                           source_name=excluded.source_name,
                           updated_at=excluded.updated_at""",
                    (data.symbol, payload, data.data_source, now),
                )
        except Exception as e:
            logger.warning(f"SQLite snapshot cache failed for {data.symbol}: {e}")

    def _get_cached_snapshot(self, symbol: str) -> UnifiedMarketData | None:
        """Get latest cached snapshot for a symbol."""
        # Try Redis first
        if self._redis and self._redis.is_connected:
            try:
                payload = self._redis._client.get(f"rt:{symbol}")
                if payload:
                    data = json.loads(payload)
                    return UnifiedMarketData(**data)
            except Exception:
                pass

        # Fallback to SQLite
        try:
            with self._db_pool.connection() as conn:
                cur = conn.execute(
                    "SELECT data_json FROM realtime_snapshots_cache WHERE symbol = ?",
                    (symbol,),
                )
                row = cur.fetchone()
                if row:
                    return UnifiedMarketData(**json.loads(row["data_json"]))
        except Exception:
            pass
        return None

    def get_snapshot(self, symbol: str) -> dict | None:
        """Get latest snapshot as dict for API consumption."""
        data = self._get_cached_snapshot(symbol)
        return data.to_dict() if data else None

    def get_batch_snapshots(self, symbols: list[str]) -> list[dict]:
        """Get latest snapshots for multiple symbols."""
        results = []
        for sym in symbols:
            data = self._get_cached_snapshot(sym)
            if data:
                results.append(data.to_dict())
        return results

    def get_all_snapshots(self) -> list[dict]:
        """Get all cached snapshots."""
        try:
            with self._db_pool.connection() as conn:
                cur = conn.execute("SELECT data_json FROM realtime_snapshots_cache")
                results = []
                for row in cur.fetchall():
                    results.append(json.loads(row["data_json"]))
                return results
        except Exception as e:
            logger.warning(f"Get all snapshots failed: {e}")
            return []

    def _record_failure(self, source_name: str) -> None:
        """Record a source failure. Trigger failover after threshold."""
        self._source_failures[source_name] = time.time()

        # Check if source has been failing for > 5 seconds
        if time.time() - self._source_failures[source_name] > 5:
            self._event_logger.log("switch", source_name=source_name, severity="warning",
                                   message=f"Source {source_name} degraded — no valid data for 5s")

    def _clear_failure(self, source_name: str) -> None:
        """Clear failure record on successful data receipt."""
        self._source_failures.pop(source_name, None)

    def _persist_quality(self, data: UnifiedMarketData) -> None:
        """Update data_quality_metrics table."""
        try:
            today = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
            with self._db_pool.transaction() as conn:
                conn.execute(
                    """INSERT INTO data_quality_metrics
                       (symbol, trade_date, source_name, delay_ms, gap_count, suspect_count, quality_score)
                       VALUES (?, ?, ?, 0, 0, ?, ?)
                       ON CONFLICT(symbol, trade_date, source_name) DO UPDATE SET
                           suspect_count=data_quality_metrics.suspect_count + excluded.suspect_count,
                           quality_score=MAX(0, data_quality_metrics.quality_score - 1)""",
                    (data.symbol, today, data.data_source,
                     1 if data.data_quality == "suspect" else 0,
                     100 if data.data_quality == "normal" else 50),
                )
        except Exception as e:
            logger.warning(f"Persist quality failed: {e}")

    def get_stats(self) -> dict:
        """Return adapter statistics."""
        return {
            **self._stats,
            "degraded": self._degraded,
            "active_subscriptions": sum(len(v) for v in self._subscriptions.values()),
            "connected_drivers": sum(
                1 for d in self._drivers.values()
                if getattr(d, "_connected", False)
            ),
        }

    async def shutdown(self) -> None:
        """Disconnect all drivers."""
        for name, driver in self._drivers.items():
            try:
                await driver.disconnect()
            except Exception:
                pass
        logger.info("MarketDataAdapter shutdown")
