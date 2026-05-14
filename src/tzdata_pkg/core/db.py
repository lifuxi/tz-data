"""
SQLite connection pool and configuration.
Provides thread-safe connection management with WAL mode and proper pragmas.
"""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from tzdata_pkg.core.exceptions import DataAccessException


class SQLitePool:
    """Thread-safe SQLite connection pool with WAL mode."""

    def __init__(self, db_path: str | Path, max_connections: int = 5):
        self.db_path = Path(db_path)
        self.max_connections = max_connections
        self._local = threading.local()
        self._lock = threading.Lock()
        self._active = 0

    def _init_connection(self, conn: sqlite3.Connection) -> None:
        """Configure SQLite pragmas for a new connection."""
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.row_factory = sqlite3.Row

    def get_connection(self) -> sqlite3.Connection:
        """Get a connection (thread-local, reuses existing)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            with self._lock:
                if self._active >= self.max_connections:
                    raise DataAccessException(
                        f"Connection pool exhausted (max={self.max_connections})",
                        source=str(self.db_path),
                    )
                self._active += 1
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                timeout=30,
                check_same_thread=False,
            )
            self._init_connection(self._local.conn)
        return self._local.conn

    def release(self) -> None:
        """Release the thread-local connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None
            with self._lock:
                self._active -= 1

    @contextmanager
    def connection(self) -> sqlite3.Connection:
        """Context manager for a connection (auto-release)."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            # Don't close thread-local connection, just let it be reused
            pass

    @contextmanager
    def transaction(self) -> sqlite3.Connection:
        """Context manager for a transaction (auto-commit/rollback)."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close_all(self) -> None:
        """Close the thread-local connection."""
        self.release()


def ensure_table_exists(
    conn: sqlite3.Connection,
    table_name: str,
    create_sql: str,
) -> None:
    """Create table if it doesn't exist using raw SQL."""
    conn.execute(create_sql)
    conn.commit()
