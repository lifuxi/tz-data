"""
Database path registry and initialization.
Manages paths for the 3 unified databases and provides connection pools.
Also manages the QuestDB time-series database connection.
"""
import os
from pathlib import Path

from tzdata_pkg.config import get_data_dir
from tzdata_pkg.core.db import SQLitePool
from tzdata_pkg.core.exceptions import DataAccessException


# Default DB filenames
MARKET_DB = "tzdata_market.db"
TRADING_DB = "tzdata_trading.db"
ANALYSIS_DB = "tzdata_analysis.db"


class DBRegistry:
    """Registry for unified tz-data databases."""

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else get_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._pools: dict[str, SQLitePool] = {}
        self._questdb_conn = None

    @property
    def market_db_path(self) -> Path:
        return self.data_dir / MARKET_DB

    @property
    def trading_db_path(self) -> Path:
        return self.data_dir / TRADING_DB

    @property
    def analysis_db_path(self) -> Path:
        return self.data_dir / ANALYSIS_DB

    def get_pool(self, db_name: str = "market") -> SQLitePool:
        """Get or create a connection pool for the specified database."""
        if db_name not in self._pools:
            path = self._db_path(db_name)
            self._pools[db_name] = SQLitePool(path)
            self._init_schema(db_name, path)
        return self._pools[db_name]

    def _db_path(self, db_name: str) -> Path:
        paths = {
            "market": self.market_db_path,
            "trading": self.trading_db_path,
            "analysis": self.analysis_db_path,
        }
        if db_name not in paths:
            raise DataAccessException(f"Unknown database: {db_name}")
        return paths[db_name]

    def _init_schema(self, db_name: str, path: Path) -> None:
        """Load and execute schema SQL for the database."""
        schema_files = {
            "market": "market.sql",
            "trading": "trading.sql",
            "analysis": "analysis.sql",
        }
        sql_file = schema_files.get(db_name)
        if not sql_file:
            return

        schema_path = Path(__file__).parent / "schemas" / sql_file
        if not schema_path.exists():
            return

        import sqlite3
        conn = sqlite3.connect(str(path))
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            sql_text = schema_path.read_text(encoding="utf-8")
            conn.executescript(sql_text)
        finally:
            conn.close()

    def get_questdb_connection(self):
        """Get QuestDB connection via PostgreSQL wire protocol (psycopg2).

        QuestDB exposes PostgreSQL-compatible SQL interface on port 8812.
        Connection params from env: QUESTDB_HOST, QUESTDB_PORT, QUESTDB_DB.
        """
        if self._questdb_conn is None:
            import psycopg2
            host = os.getenv("QUESTDB_HOST", "localhost")
            port = int(os.getenv("QUESTDB_PORT", "8812"))
            dbname = os.getenv("QUESTDB_DB", "questdb")
            self._questdb_conn = psycopg2.connect(
                host=host,
                port=port,
                user="admin",
                password="quest",
                dbname=dbname,
            )
            self._questdb_conn.autocommit = True
        return self._questdb_conn

    def close_questdb(self):
        """Close QuestDB connection."""
        if self._questdb_conn is not None:
            self._questdb_conn.close()
            self._questdb_conn = None

    def close_all(self) -> None:
        """Close all connection pools and QuestDB connection."""
        for pool in self._pools.values():
            pool.close_all()
        self._pools.clear()
        self.close_questdb()

    def init_questdb_schema(self) -> bool:
        """Initialize QuestDB tables via HTTP API (port 9000).

        QuestDB doesn't support CREATE TABLE IF NOT EXISTS via PostgreSQL wire
        protocol for all table types, so we use the REST exec endpoint.
        Returns True if initialization succeeded, False if QuestDB is unavailable.
        """
        try:
            import httpx
            host = os.getenv("QUESTDB_HOST", "localhost")
            port = os.getenv("QUESTDB_HTTP_PORT", "9000")
            schema_path = Path(__file__).parent / "schemas" / "questdb.sql"
            if not schema_path.exists():
                return False

            sql_text = schema_path.read_text(encoding="utf-8")
            # QuestDB exec endpoint takes a single statement at a time
            statements = [s.strip() for s in sql_text.split(";") if s.strip()]

            for stmt in statements:
                resp = httpx.get(
                    f"http://{host}:{port}/exec",
                    params={"query": stmt},
                    timeout=10,
                )
                resp.raise_for_status()

            return True
        except ImportError:
            return False
        except Exception:
            return False
