"""
Database path registry and initialization.
Manages paths for the 3 unified databases and provides connection pools.
"""
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

    def close_all(self) -> None:
        """Close all connection pools."""
        for pool in self._pools.values():
            pool.close_all()
        self._pools.clear()
