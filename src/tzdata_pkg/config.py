"""
Configuration management for tz-data.

All paths are derived from TZ_DATA_DIR environment variable.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any


def _get_system_config_value(key: str) -> str:
    """Read a system config value from the market DB. Returns empty string if not found."""
    import sqlite3
    data_dir = get_data_dir()
    db_path = data_dir / "tzdata_market.db"
    if not db_path.exists():
        return ""
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT config_value FROM system_config WHERE config_key = ?", (key,)
        ).fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""


# Wrap with lru_cache after the function is defined
_get_system_config_value = lru_cache(maxsize=64)(_get_system_config_value)


def invalidate_config_cache(key: str | None = None) -> None:
    """Clear config cache. If key is None, clear all."""
    _get_system_config_value.cache_clear()


def _set_system_config_value(key: str, value: str, config_type: str = "text", description: str = "") -> bool:
    """Set a system config value in the market DB. Returns True on success."""
    import sqlite3
    data_dir = get_data_dir()
    db_path = data_dir / "tzdata_market.db"
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            INSERT INTO system_config (config_key, config_value, config_type, description)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(config_key) DO UPDATE SET
                config_value = excluded.config_value,
                config_type = excluded.config_type,
                description = excluded.description
        """, (key, value, config_type, description))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_data_dir() -> Path:
    """Return the shared data directory.

    Resolved in order:
    1. TZ_DATA_DIR environment variable
    2. Default: tz-data package data directory
    """
    env_path = os.environ.get("TZ_DATA_DIR")
    if env_path:
        return Path(env_path)
    return Path(r"C:\myspace\tz-data\data")


def get_cffex_config() -> Dict[str, Any]:
    """CFFEX data download configuration with paths derived from data_dir."""
    data_dir = get_data_dir()
    cffex_dir = data_dir / "cffex"

    return {
        "base_url": "http://www.cffex.com.cn/sj/",
        "products": {
            "MO": {"name": "中证1000期权", "exchange": "CFFEX", "enabled": True, "type": "option"},
            "IM": {"name": "中证1000期货", "exchange": "CFFEX", "enabled": True, "type": "futures"},
            "IO": {"name": "沪深300期权", "exchange": "CFFEX", "enabled": False, "type": "option"},
            "HO": {"name": "上证50期权", "exchange": "CFFEX", "enabled": False, "type": "option"},
            "IC": {"name": "中证500期货", "exchange": "CFFEX", "enabled": False, "type": "futures"},
            "IF": {"name": "沪深300期货", "exchange": "CFFEX", "enabled": False, "type": "futures"},
            "IH": {"name": "上证50期货", "exchange": "CFFEX", "enabled": False, "type": "futures"},
        },
        "data_types": {
            "daily": {"name": "日线数据", "frequency": "daily", "enabled": True},
            "weekly": {"name": "周线数据", "frequency": "weekly", "enabled": True},
            "monthly": {"name": "月线数据", "frequency": "monthly", "enabled": True},
            "position": {"name": "成交持仓排名", "frequency": "daily", "enabled": True},
        },
        "download": {
            "timeout": 30,
            "max_retries": 3,
            "retry_delays": [1, 2, 4],
            "request_delay": 0.5,
            "chunk_size": 8192,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        "storage": {
            "csv_dir": str(cffex_dir / "raw"),
            "db_path": str(cffex_dir / "cffex.db"),
            "log_dir": str(data_dir / "logs" / "cffex"),
            "checksum_file": str(cffex_dir / ".checksums.json"),
        },
        "partition": {"start_year": 2024, "auto_create_table": True, "index_on_create": True},
        "batch": {"days_per_batch": 30, "empty_file_threshold": 5, "save_csv": True, "verify_after_batch": True},
        "validation": {"enable_checksum": True, "verify_integrity": True, "min_records_per_day": 10},
    }


def get_shfe_config() -> Dict[str, Any]:
    """SHFE data download configuration with paths derived from data_dir."""
    data_dir = get_data_dir()
    shfe_dir = data_dir / "shfe"

    return {
        "products": {
            "AU": {"name": "黄金", "enabled": True, "type": "futures"},
            "AG": {"name": "白银", "enabled": True, "type": "futures"},
            "CU": {"name": "铜", "enabled": True, "type": "futures"},
            "AL": {"name": "铝", "enabled": True, "type": "futures"},
            "ZN": {"name": "锌", "enabled": True, "type": "futures"},
            "SN": {"name": "锡", "enabled": True, "type": "futures"},
        },
        "storage": {
            "csv_dir": str(shfe_dir / "raw"),
            "db_path": str(shfe_dir / "shfe.db"),
            "log_dir": str(data_dir / "logs" / "shfe"),
        },
    }


def get_tushare_config() -> Dict[str, Any]:
    """Tushare configuration.

    Token is read from system_config DB first, then falls back to TUSHARE_TOKEN env.
    """
    data_dir = get_data_dir()
    tushare_dir = data_dir / "tushare"

    # Try DB first
    token = _get_system_config_value("tushare.token")
    # Fallback to environment variable
    if not token:
        token = os.environ.get("TUSHARE_TOKEN", "")

    return {
        "token": token,
        "storage": {
            "db_path": str(tushare_dir / "options.db"),
            "log_dir": str(data_dir / "logs" / "tushare"),
        },
        "enabled_underlyings": ["MO", "HO", "IO"],
        "frequencies": ["1min", "5min", "15min", "30min", "60min"],
    }


def get_cfmmc_config() -> Dict[str, Any]:
    """CFMMC bill download configuration."""
    data_dir = get_data_dir()
    cfmmc_dir = data_dir / "cfmmc"

    return {
        "cookie_dir": str(cfmmc_dir / "cookies"),
        "storage": {
            "raw_dir": str(data_dir / "bills" / "raw"),
            "log_dir": str(data_dir / "logs" / "cfmmc"),
        },
    }


# Database path constants (derived from get_data_dir)
DATA_DIR = get_data_dir()

# Unified DB paths (3-DB architecture)
TZDATA_MARKET_DB = DATA_DIR / "tzdata_market.db"
TZDATA_TRADING_DB = DATA_DIR / "tzdata_trading.db"
TZDATA_ANALYSIS_DB = DATA_DIR / "tzdata_analysis.db"

# Legacy DB paths (deprecated — all migrated and deleted 2026-05-18)
# Aliases kept for backward compatibility.
BILLS_DB = TZDATA_TRADING_DB  # was bills.db
INSTITUTION_DB = TZDATA_ANALYSIS_DB  # was institution.db
TRADING_DB = DATA_DIR / "trading.db"
CFFEX_HOLDINGS_DB = DATA_DIR / "cffex_holdings.db"
TUSHARE_DB = DATA_DIR / "tushare" / "options.db"
