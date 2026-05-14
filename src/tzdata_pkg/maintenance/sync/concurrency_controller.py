"""
Task concurrency controller for Celery workers.
Implements rate limiting and concurrency control for data sync tasks
to avoid triggering API rate limits from data sources.
"""
import logging
import threading
import time
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, rate: float, capacity: int = 1):
        """
        Args:
            rate: Tokens per second (requests per second)
            capacity: Max burst capacity
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for a token and acquire it.

        Args:
            timeout: Max wait time (None = wait forever)

        Returns:
            True if token acquired, False if timeout
        """
        deadline = None if timeout is None else time.monotonic() + timeout

        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_refill = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True

            if deadline is not None and time.monotonic() >= deadline:
                return False

            time.sleep(0.1)


class ConcurrencyController:
    """
    Controls concurrent task execution to prevent API overload.

    Manages:
    - Per-source rate limits (e.g., Tushare: 200 req/min)
    - Global max concurrent tasks
    - Per-catalog serialization (one sync at a time per catalog)
    """

    # Default rate limits by source (requests per minute)
    SOURCE_RATE_LIMITS = {
        'tushare': 200,     # Tushare API limit
        'cffex': 30,        # CFFEX website, be gentle
        'shfe': 30,         # SHFE website
        'wind': 1000,       # Wind API (high limit)
    }

    # Max concurrent sync tasks globally
    MAX_CONCURRENT_SYNCS = 3

    # Per-catalog lock to prevent duplicate syncs
    _catalog_locks: dict[int, threading.Lock] = {}
    _global_semaphore: threading.Semaphore = None
    _rate_limiters: dict[str, RateLimiter] = {}
    _init_lock = threading.Lock()

    @classmethod
    def _init_semaphore(cls):
        if cls._global_semaphore is None:
            cls._global_semaphore = threading.Semaphore(cls.MAX_CONCURRENT_SYNCS)

    @classmethod
    def get_catalog_lock(cls, catalog_id: int) -> threading.Lock:
        """Get or create a per-catalog lock to prevent duplicate syncs."""
        with cls._init_lock:
            if catalog_id not in cls._catalog_locks:
                cls._catalog_locks[catalog_id] = threading.Lock()
            return cls._catalog_locks[catalog_id]

    @classmethod
    @contextmanager
    def acquire_sync_slot(cls, timeout: Optional[float] = None):
        """
        Acquire a global sync slot. Blocks if at max concurrency.

        Args:
            timeout: Max wait time for a slot

        Yields:
            True if slot acquired

        Raises:
            TimeoutError if timeout exceeded
        """
        cls._init_semaphore()

        acquired = cls._global_semaphore.acquire(timeout=timeout or 3600)
        if not acquired:
            raise TimeoutError("No sync slot available within timeout")

        try:
            logger.info(
                f"Sync slot acquired. "
                f"Active: {cls.MAX_CONCURRENT_SYNCS - cls._global_semaphore._value}/{cls.MAX_CONCURRENT_SYNCS}"
            )
            yield True
        finally:
            cls._global_semaphore.release()

    @classmethod
    def get_rate_limiter(cls, source_name: str) -> RateLimiter:
        """Get or create a rate limiter for a data source."""
        with cls._init_lock:
            if source_name not in cls._rate_limiters:
                rpm = cls.SOURCE_RATE_LIMITS.get(source_name, 60)
                rps = rpm / 60.0
                cls._rate_limiters[source_name] = RateLimiter(rate=rps, capacity=max(5, int(rps * 2)))
                logger.info(f"Rate limiter created for {source_name}: {rpm} req/min")
            return cls._rate_limiters[source_name]

    @classmethod
    def wait_for_rate_limit(cls, source_name: str, timeout: float = 120.0) -> bool:
        """
        Wait for rate limiter token.

        Args:
            source_name: Data source name
            timeout: Max wait time

        Returns:
            True if token acquired
        """
        limiter = cls.get_rate_limiter(source_name)
        return limiter.acquire(timeout=timeout)

    @classmethod
    def get_status(cls) -> dict:
        """Get current concurrency and rate limit status."""
        cls._init_semaphore()
        active = cls.MAX_CONCURRENT_SYNCS - cls._global_semaphore._value
        return {
            'max_concurrent': cls.MAX_CONCURRENT_SYNCS,
            'active_syncs': active,
            'available_slots': cls.MAX_CONCURRENT_SYNCS - active,
            'rate_limiters': {
                name: {
                    'tokens': round(limiter.tokens, 1),
                    'rate_per_min': round(limiter.rate * 60, 0)
                }
                for name, limiter in cls._rate_limiters.items()
            }
        }
