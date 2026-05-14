"""SQLite connection pool and SHFE connection pool singleton."""

import sqlite3
import logging
import threading
import time
from contextlib import contextmanager
from queue import Queue, Empty


class SQLitePool:
    """SQLite connection pool."""

    def __init__(self, db_path: str, pool_size: int = 5, timeout: int = 30):
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool: Queue = Queue()
        self._lock = threading.Lock()
        self._created = 0
        self.logger = logging.getLogger("SQLitePool")
        for _ in range(pool_size):
            self._pool.put(self._create_connection())

    def _create_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def acquire(self):
        try:
            conn = self._pool.get_nowait()
            return conn
        except Empty:
            with self._lock:
                if self._created < self.pool_size * 2:
                    conn = self._create_connection()
                    self._created += 1
                    return conn
            conn = self._pool.get(timeout=self.timeout)
            return conn

    def release(self, conn):
        self._pool.put(conn)

    @contextmanager
    def connection(self):
        conn = self.acquire()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.release(conn)

    def get_stats(self) -> dict:
        return {"db_path": self.db_path, "pool_size": self.pool_size, "created": self._created, "available": self._pool.qsize()}


class SHFEConnectionPool:
    """Singleton connection pool manager for SHFE."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._pools = {}
        self.logger = logging.getLogger("SHFEConnectionPool")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def initialize(self, db_paths: dict = None, pool_size: int = 5):
        from tzdata_pkg.config import get_shfe_config
        config = get_shfe_config()
        paths = db_paths or {"shfe": config["storage"]["db_path"]}
        for name, db_path in paths.items():
            self._pools[name] = SQLitePool(db_path, pool_size)
            self.logger.info(f"Initialized pool '{name}': {db_path}")

    def get_pool(self, name: str = "shfe") -> SQLitePool:
        if name not in self._pools:
            raise ValueError(f"Pool '{name}' not initialized")
        return self._pools[name]

    @contextmanager
    def connection(self, name: str = "shfe"):
        with self.get_pool(name).connection() as conn:
            yield conn

    def get_stats(self) -> dict:
        return {name: pool.get_stats() for name, pool in self._pools.items()}

    def close_all(self):
        self._pools.clear()
        self.logger.info("All pools closed")


def get_shfe_pool(name: str = "shfe") -> SQLitePool:
    return SHFEConnectionPool.get_instance().get_pool(name)
