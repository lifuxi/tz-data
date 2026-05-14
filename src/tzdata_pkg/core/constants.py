"""
Constants for exchange codes, product definitions, and data types.
"""
from enum import Enum


class Exchange(str, Enum):
    """Supported Chinese futures exchanges."""

    CFFEX = "CFFEX"  # China Financial Futures Exchange
    SHFE = "SHFE"    # Shanghai Futures Exchange
    DCE = "DCE"      # Dalian Commodity Exchange
    CZCE = "CZCE"    # Zhengzhou Commodity Exchange
    INE = "INE"      # Shanghai International Energy Exchange


class DataType(str, Enum):
    """Supported data types for download."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    POSITION = "position"
    MINUTE = "minute"


# CFFEX product definitions
CFFEX_PRODUCTS = {
    "MO": {"name": "中证1000期权", "type": "option", "underlying": "MO"},
    "IM": {"name": "中证1000期货", "type": "futures", "underlying": "IM"},
    "IO": {"name": "沪深300期权", "type": "option", "underlying": "IO"},
    "HO": {"name": "上证50期权", "type": "option", "underlying": "HO"},
    "IC": {"name": "中证500期货", "type": "futures", "underlying": "IC"},
    "IF": {"name": "沪深300期货", "type": "futures", "underlying": "IF"},
    "IH": {"name": "上证50期货", "type": "futures", "underlying": "IH"},
}

# SHFE product definitions
SHFE_PRODUCTS = {
    "AU": {"name": "黄金", "type": "futures"},
    "AG": {"name": "白银", "type": "futures"},
    "CU": {"name": "铜", "type": "futures"},
    "AL": {"name": "铝", "type": "futures"},
    "ZN": {"name": "锌", "type": "futures"},
    "SN": {"name": "锡", "type": "futures"},
}

# All products by exchange
PRODUCTS_BY_EXCHANGE = {
    Exchange.CFFEX: CFFEX_PRODUCTS,
    Exchange.SHFE: SHFE_PRODUCTS,
    Exchange.DCE: {},
    Exchange.CZCE: {},
    Exchange.INE: {},
}
