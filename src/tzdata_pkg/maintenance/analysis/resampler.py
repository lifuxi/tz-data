"""
OHLCV K线重采样引擎。

从 1 分钟数据聚合生成 5min/15min/30min/60min 多周期 K 线。
使用 pandas resample 进行 OHLCV 聚合，自动处理交易时间段。
"""
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

TARGET_FREQUENCIES = ["5min", "15min", "30min", "60min"]

# 中国期货交易所日盘交易时段 (Asia/Shanghai)
# 09:00-11:30, 13:00-15:00 (中金所股指期货)
# 09:00-11:30, 13:30-15:00 (中金所国债期货)
CFFEX_TRADING_SESSIONS = [
    ("09:00", "11:30"),
    ("13:00", "15:00"),
]


class OHLCVResampler:
    """OHLCV K 线重采样引擎。"""

    @staticmethod
    def build_datetime_index(
        trade_date: str,
        trade_time: str,
        date_format: str = "%Y%m%d",
    ) -> pd.Timestamp:
        """将 trade_date + trade_time 组合为 pandas datetime index。

        支持 YYYYMMDD 和 YYYY-MM-DD 两种日期格式。
        时间格式为 HH:MM:SS 或 HH:MM。
        """
        if "-" in trade_date:
            date_part = trade_date.replace("-", "")
        else:
            date_part = trade_date

        time_part = trade_time.replace(" ", "")
        if len(time_part) == 5:
            time_part += ":00"

        dt_str = f"{date_part}T{time_part}"
        return pd.Timestamp(dt_str)

    @staticmethod
    def resample_from_1min(
        df_1min: pd.DataFrame,
        target_freq: str,
        contract_code: str,
        exchange: str = "CFFEX",
    ) -> pd.DataFrame:
        """将 1 分钟 OHLCV 数据聚合为目标周期。

        Args:
            df_1min: 1 分钟数据，必须包含 trade_date, trade_time, open, high,
                     low, close, volume, turnover, open_interest 列
            target_freq: "5min", "15min", "30min", "60min"
            contract_code: 合约代码
            exchange: 交易所代码

        Returns:
            重采样后的 DataFrame，index 为 datetime，包含 OHLCV 列 + metadata
        """
        if df_1min.empty:
            return pd.DataFrame()

        df = df_1min.copy()

        # 构建 datetime index
        df["dt"] = df.apply(
            lambda r: OHLCVResampler.build_datetime_index(
                str(r["trade_date"]), str(r["trade_time"])
            ),
            axis=1,
        )
        df = df.set_index("dt").sort_index()

        agg_dict = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "turnover": "sum",
            "open_interest": "last",
        }

        # 只聚合有 close 值的行
        df = df.dropna(subset=["close"])
        if df.empty:
            return pd.DataFrame()

        resampled = df.resample(target_freq).agg(agg_dict)
        resampled = resampled.dropna(subset=["close"])  # 去除空 K 线

        if resampled.empty:
            return pd.DataFrame()

        # 重建 trade_date / trade_time 列
        resampled["trade_date"] = resampled.index.strftime("%Y%m%d")
        resampled["trade_time"] = resampled.index.strftime("%H:%M:%S")
        resampled["contract_code"] = contract_code
        resampled["exchange"] = exchange
        resampled["frequency"] = target_freq
        resampled["source"] = "resampled"
        resampled["vwap"] = resampled["turnover"] / resampled["volume"].replace(0, float("nan"))

        return resampled

    @staticmethod
    def resample_daily_to_weekly(
        df_daily: pd.DataFrame,
        product_code: str,
    ) -> pd.DataFrame:
        """将日线数据聚合为周线（备用功能）。"""
        if df_daily.empty:
            return pd.DataFrame()

        df = df_daily.copy()
        df["dt"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d")
        df = df.set_index("dt").sort_index()

        agg_dict = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "turnover": "sum",
            "open_interest": "last",
        }

        resampled = df.resample("W").agg(agg_dict)
        resampled = resampled.dropna(subset=["close"])

        if resampled.empty:
            return pd.DataFrame()

        resampled["trade_date"] = resampled.index.strftime("%Y%m%d")
        resampled["trade_time"] = "00:00:00"
        resampled["contract_code"] = product_code
        resampled["frequency"] = "1w"
        resampled["source"] = "resampled_weekly"

        return resampled

    @staticmethod
    def validate_resample(
        original_count: int,
        resampled_count: int,
        target_freq: str,
    ) -> dict:
        """验证重采样结果的合理性。"""
        expected_ratio = {
            "5min": 240,   # 1min → 5min: ~240 bars/day → ~48 bars/day
            "15min": 240,
            "30min": 240,
            "60min": 240,
        }

        ratio_map = {
            "5min": 5,
            "15min": 15,
            "30min": 30,
            "60min": 60,
        }

        ratio = ratio_map.get(target_freq, 5)
        expected = max(1, original_count // ratio)

        return {
            "original_bars": original_count,
            "resampled_bars": resampled_count,
            "expected_approx": expected,
            "ratio": f"{resampled_count}/{original_count:.0f}" if original_count > 0 else "N/A",
            "valid": 0.5 * expected <= resampled_count <= expected * 1.5 if expected > 0 else True,
        }
