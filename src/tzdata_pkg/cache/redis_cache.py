"""
Redis cache adapter for tz-data (L2).

Adapted from tz2.0's src/analysis/redis_cache.py with tz-data-specific config.
Features: pickle + base64 serialization, TTL, key versioning, stampede prevention.
"""
import base64
import hashlib
import pickle
import threading
import time
from typing import Any, Callable

import structlog

from tzdata_pkg.cache import config

logger = structlog.get_logger("tzdata_cache")

_CACHE_VERSION = 1
_KEY_PREFIX = "tzdata"


class RedisCache:
    """
    Redis cache layer for tz-data. Gracefully degrades if Redis is unavailable.
    """

    def __init__(self, redis_url: str | None = None):
        if redis_url is None:
            redis_url = f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/{config.REDIS_CACHE_DB}"

        self._client = None
        self._connected = False
        self._lock_timeout = 10
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()

        if not config.CACHE_ENABLED:
            logger.info("Redis cache disabled by config")
            return

        try:
            import redis

            self._client = redis.Redis.from_url(
                redis_url,
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._client.ping()
            self._connected = True
            logger.info("tz-data Redis cache connected")
        except Exception as e:
            logger.warning(f"tz-data Redis cache unavailable, L2 disabled: {e}")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get(self, key: str) -> Any | None:
        if not self._connected:
            return None
        try:
            data = self._client.get(self._versioned_key(key))
            if data is None:
                self._misses += 1
                return None
            self._hits += 1
            return pickle.loads(base64.b64decode(data))
        except Exception as e:
            logger.debug(f"Redis get failed for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if not self._connected:
            return
        try:
            serialized = base64.b64encode(pickle.dumps(value))
            self._client.setex(self._versioned_key(key), ttl, serialized)
        except Exception as e:
            logger.debug(f"Redis set failed for {key}: {e}")

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: int = 300,
        timeout: int | None = None,
    ) -> Any:
        """Get from cache or compute, with distributed lock for stampede prevention."""
        value = self.get(key)
        if value is not None:
            return value

        lock_key = f"{self._versioned_key(key)}:lock"
        acquired = self._acquire_lock(lock_key, timeout or self._lock_timeout)

        if acquired:
            try:
                value = self.get(key)
                if value is not None:
                    return value
                value = compute_fn()
                self.set(key, value, ttl)
                return value
            finally:
                self._release_lock(lock_key)
        else:
            logger.warning(f"Cache stampede lock timeout for {key}, computing uncached")
            return compute_fn()

    def delete(self, key: str) -> bool:
        if not self._connected:
            return False
        try:
            return bool(self._client.delete(self._versioned_key(key)))
        except Exception:
            return False

    def delete_by_prefix(self, prefix: str) -> int:
        if not self._connected:
            return 0
        try:
            pattern = f"{self._versioned_key(prefix)}*"
            keys = self._client.keys(pattern)
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.debug(f"Redis delete_by_prefix failed: {e}")
            return 0

    def clear_all(self) -> None:
        if not self._connected:
            return
        try:
            self._client.flushdb()
            logger.info("tz-data Redis cache flushed")
        except Exception as e:
            logger.warning(f"Redis flushdb failed: {e}")

    def get_stats(self) -> dict:
        return {
            "connected": self._connected,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
            "version": _CACHE_VERSION,
        }

    def _versioned_key(self, key: str) -> str:
        return f"v{_CACHE_VERSION}:{_KEY_PREFIX}:{key}"

    def _acquire_lock(self, lock_key: str, timeout: int) -> bool:
        if not self._connected:
            return False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._client.set(lock_key, "1", nx=True, ex=timeout):
                return True
            time.sleep(0.1)
        return False

    def _release_lock(self, lock_key: str) -> None:
        if self._connected:
            try:
                self._client.delete(lock_key)
            except Exception:
                pass
