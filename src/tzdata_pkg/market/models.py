"""
Unified market data model.

All data sources are normalized to this single dataclass.
Option-specific fields are None for futures/index.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class UnifiedMarketData:
    # ========== 通用标识 ==========
    symbol: str = ""
    exchange: str = ""
    asset_type: str = ""          # FUTURE / OPTION / INDEX
    timestamp: int = 0            # 毫秒级 Unix 时间戳

    # ========== 通用行情 ==========
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    pre_close: float | None = None
    bid_price1: float | None = None
    bid_volume1: int | None = None
    ask_price1: float | None = None
    ask_volume1: int | None = None

    # ========== 期权结构性字段 ==========
    option_type: str | None = None        # CALL / PUT
    strike_price: float | None = None
    expiry_date: str | None = None
    underlying_symbol: str | None = None
    underlying_price: float | None = None

    # ========== 期权估值与风险 ==========
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    vega: float | None = None
    theta: float | None = None
    rho: float | None = None

    # ========== 计算辅助 ==========
    moneyness: str | None = None          # ITM / ATM / OTM
    days_to_expiry: int | None = None
    theoretical_price: float | None = None

    # ========== 质量标记 ==========
    data_source: str = ""                 # ctp, tushare, akshare, ...
    is_backfill: bool = False
    data_quality: str = "normal"          # normal / degraded / suspect

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "UnifiedMarketData":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})
