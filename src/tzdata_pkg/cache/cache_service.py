"""
Two-tier cache service for tz-data: L1 (in-memory) + L2 (Redis).
Provides caching with automatic promotion, tag-based invalidation, and hit/miss tracking.
"""
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import structlog

from tzdata_pkg.cache import config
from tzdata_pkg.cache.redis_cache import RedisCache

logger = structlog.get_logger("tzdata_cache_service")


class AnalysisCache:
    """In-memory L1 cache with TTL."""

    def __init__(self, default_ttl: int = 300):
        self.cache: dict[str, dict] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        if key not in self.cache:
            return None
        item = self.cache[key]
        if time.time() > item["expiry"]:
            del self.cache[key]
            return None
        return item["value"]

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expiry = time.time() + (ttl or self.default_ttl)
        self.cache[key] = {"value": value, "expiry": expiry}

    def delete(self, key: str) -> bool:
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear(self) -> None:
        self.cache.clear()
        logger.info("L1 cache cleared")

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [k for k, v in self.cache.items() if now > v["expiry"]]
        for k in expired:
            del self.cache[k]
        return len(expired)

    def get_stats(self) -> dict:
        now = time.time()
        total = len(self.cache)
        expired = sum(1 for v in self.cache.values() if now > v["expiry"])
        return {
            "total_entries": total,
            "active_entries": total - expired,
            "expired_entries": expired,
        }


class TieredCache:
    """Two-tier cache: L1 (memory) + L2 (Redis)."""

    def __init__(self, default_ttl: int = 300):
        self.l1 = AnalysisCache(default_ttl)
        self.l2 = RedisCache() if config.CACHE_ENABLED else None
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
        self._tags: dict[str, set[str]] = {}

    def get(self, key: str) -> Any | None:
        val = self.l1.get(key)
        if val is not None:
            self._hits += 1
            return val

        if self.l2 and self.l2.is_connected:
            val = self.l2.get(key)
            if val is not None:
                self.l1.set(key, val)
                self._hits += 1
                return val

        self._misses += 1
        return None

    def set(
        self, key: str, value: Any, ttl: int | None = None, tags: list[str] | None = None
    ) -> None:
        effective_ttl = ttl or self.default_ttl
        self.l1.set(key, value, effective_ttl)
        if self.l2 and self.l2.is_connected:
            self.l2.set(key, value, effective_ttl)
        if tags:
            for tag in tags:
                self._tags.setdefault(tag, set()).add(key)

    def delete(self, key: str) -> bool:
        l1_ok = self.l1.delete(key)
        l2_ok = True
        if self.l2 and self.l2.is_connected:
            l2_ok = self.l2.delete(key)
        for tag_keys in self._tags.values():
            tag_keys.discard(key)
        return l1_ok or l2_ok

    def invalidate_by_tag(self, tag: str) -> int:
        keys = self._tags.pop(tag, set())
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        logger.info(f"Invalidated {count} entries with tag: {tag}")
        return count

    def invalidate_on_data_change(self) -> None:
        self.clear()
        logger.info("Cache invalidated due to data change")

    def clear(self) -> None:
        self.l1.clear()
        if self.l2 and self.l2.is_connected:
            self.l2.clear_all()
        self._tags.clear()
        self._hits = 0
        self._misses = 0

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get_stats(self) -> dict:
        l1_stats = self.l1.get_stats()
        return {
            "l1_entries": l1_stats["active_entries"],
            "l2_connected": self.l2.is_connected if self.l2 else False,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
            "tags": list(self._tags.keys()),
        }


# Global cache instance
analysis_cache = TieredCache(default_ttl=config.CACHE_DEFAULT_TTL)


def cache_result(key_prefix: str, ttl: int | None = None, tags: list[str] | None = None):
    """
    Decorator to cache function results in the tiered cache.
    Skips the first positional arg (assumed to be db/session or self).
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if args and len(args) > 0:
                cache_args = str(args[1:]) if len(args) > 1 else "no_extra_args"
            else:
                cache_args = "no_args"
            cache_key = f"{key_prefix}:{func.__name__}:{cache_args}:{str(sorted(kwargs.items()))}"

            cached_result = analysis_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache HIT for {cache_key}")
                return cached_result

            logger.debug(f"Cache MISS for {cache_key}")
            result = func(*args, **kwargs)
            analysis_cache.set(cache_key, result, ttl, tags)
            return result

        return wrapper

    return decorator


def invalidate_cache(key_prefix: str) -> None:
    keys_to_delete = [
        key for key in list(analysis_cache.l1.cache.keys()) if key.startswith(key_prefix)
    ]
    count = 0
    for key in keys_to_delete:
        if analysis_cache.delete(key):
            count += 1
    logger.info(f"Invalidated {count} cache entries with prefix: {key_prefix}")
