import pandas as pd
import chardet
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging


@dataclass
class CFFEXParseResult:
    """Parse result structure."""
    data: pd.DataFrame
    stats: Dict[str, Any]
    trade_date: str
    data_type: str
    record_count: int
    columns: list


class CFFEXCSVParser:
    """CFFEX CSV parser."""

    DAILY_COLUMN_MAPPING = {
        "交易日": "trade_date",
        "合约代码": "instrument_id",
        "开盘价": "open_price",
        "最高价": "high_price",
        "最低价": "low_price",
        "收盘价": "close_price",
        "涨跌": "change",
        "涨跌幅": "change_pct",
        "涨跌1": "change",
        "涨跌2": "change_pct",
        "结算价": "settlement_price",
        "今结算": "settlement_price",
        "前结算价": "pre_settle",
        "前结算": "pre_settle",
        "成交量": "volume",
        "成交金额": "turnover",
        "持仓量": "open_interest",
        "持仓变化": "oi_change",
        "日持仓变化": "oi_change",
        "行权价": "strike_price",
        "执行价": "strike_price",
        "合约标的": "underlying",
        "期权类型": "option_type",
        "合约月份": "contract_month",
        "到期日": "expire_date",
        "Delta": "delta",
    }

    POSITION_COLUMN_MAPPING = {
        "交易日": "trade_date",
        "合约代码": "instrument_id",
        "期货公司会员简称": "member_name",
        "会员简称": "member_name",
        "多头持仓量": "long_volume",
        "多头持仓": "long_volume",
        "空头持仓量": "short_volume",
        "空头持仓": "short_volume",
        "多头增减": "long_change",
        "多头变化": "long_change",
        "空头增减": "short_change",
        "空头变化": "short_change",
    }

    STAT_FIELDS = ["volume", "turnover", "open_interest", "oi_change"]

    def __init__(self):
        self.logger = logging.getLogger("CFFEXCSVParser")

    def detect_encoding(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            raw_data = f.read(10000)
        result = chardet.detect(raw_data)
        encoding = result.get("encoding", "gbk")
        if encoding and encoding.lower() in ["gb2312", "gb18030"]:
            encoding = "gbk"
        return encoding or "gbk"

    def read_csv(self, file_path: str, **kwargs) -> pd.DataFrame:
        encoding = self.detect_encoding(file_path)
        try:
            df = pd.read_csv(file_path, encoding=encoding, **kwargs)
        except UnicodeDecodeError:
            for enc in ["gbk", "utf-8", "gb18030", "latin1"]:
                try:
                    df = pd.read_csv(file_path, encoding=enc, **kwargs)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Unable to parse file encoding: {file_path}")
        return df

    def standardize_columns(self, df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
        standard_columns = [
            "instrument_id", "open_price", "high_price", "low_price",
            "volume", "turnover", "open_interest", "oi_change",
            "settlement_price", "close_price", "pre_settle",
            "change", "change_pct", "delta",
        ]
        if len(df.columns) == len(standard_columns):
            df.columns = standard_columns
            return df
        new_columns = {}
        for col in df.columns:
            col_stripped = col.strip()
            if col_stripped in mapping:
                new_columns[col] = mapping[col_stripped]
            else:
                for key, value in mapping.items():
                    if key in col_stripped or col_stripped in key:
                        new_columns[col] = value
                        break
        df = df.rename(columns=new_columns)
        return df

    def extract_stats(self, df: pd.DataFrame, stat_fields: list = None) -> Dict[str, Any]:
        stat_fields = stat_fields or self.STAT_FIELDS
        stats = {}
        for field in stat_fields:
            if field in df.columns:
                values = pd.to_numeric(df[field], errors="coerce")
                stats[f"total_{field}"] = values.sum()
                stats[f"max_{field}"] = values.max()
                stats[f"min_{field}"] = values.min()
                stats[f"mean_{field}"] = values.mean()
        if "instrument_id" in df.columns:
            stats["contract_count"] = df["instrument_id"].nunique()
        return stats

    def _format_trade_date(self, trade_date: str) -> str:
        if trade_date and len(trade_date) == 8:
            return f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        return trade_date

    def parse_daily_csv(self, file_path: str, trade_date: str = None) -> CFFEXParseResult:
        self.logger.info(f"Parsing daily CSV: {file_path}")
        df = self.read_csv(file_path)
        if df.empty:
            return CFFEXParseResult(
                data=df, stats={}, trade_date=trade_date or "",
                data_type="daily", record_count=0, columns=[],
            )
        df = self.standardize_columns(df, self.DAILY_COLUMN_MAPPING)
        if not trade_date:
            if "trade_date" in df.columns:
                trade_date = str(df["trade_date"].iloc[0])
            else:
                import re
                match = re.search(r"(\d{8})", Path(file_path).name)
                if match:
                    trade_date = match.group(1)
        trade_date = self._format_trade_date(trade_date)
        if trade_date:
            df["trade_date"] = trade_date
        numeric_cols = [
            "open_price", "high_price", "low_price", "close_price",
            "settlement_price", "volume", "turnover", "open_interest",
            "oi_change", "strike_price",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        stats = self.extract_stats(df)
        stats["trade_date"] = trade_date
        if "instrument_id" in df.columns:
            agg_dict = {"volume": "sum"}
            if "turnover" in df.columns:
                agg_dict["turnover"] = "sum"
            if "open_interest" in df.columns:
                agg_dict["open_interest"] = "last"
            contract_stats = df.groupby("instrument_id").agg(agg_dict).to_dict("records")
            stats["contract_stats"] = contract_stats
        return CFFEXParseResult(
            data=df, stats=stats, trade_date=trade_date,
            data_type="daily", record_count=len(df), columns=df.columns.tolist(),
        )

    def parse_monthly_csv(self, file_path: str, year_month: str = None) -> CFFEXParseResult:
        self.logger.info(f"Parsing monthly CSV: {file_path}")
        result = self.parse_daily_csv(file_path, year_month)
        result.data_type = "monthly"
        return result

    def parse_position_csv(self, file_path: str, product: str = "MO") -> CFFEXParseResult:
        self.logger.info(f"Parsing position CSV: {file_path}")
        df = self.read_csv(file_path)
        if df.empty:
            return CFFEXParseResult(
                data=df, stats={}, trade_date="",
                data_type="position", record_count=0, columns=[],
            )
        df = self.standardize_columns(df, self.POSITION_COLUMN_MAPPING)
        df["product"] = product
        trade_date = ""
        if "trade_date" in df.columns:
            trade_date = str(df["trade_date"].iloc[0])
            trade_date = self._format_trade_date(trade_date)
        numeric_cols = ["long_volume", "short_volume", "long_change", "short_change"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "long_volume" in df.columns and "short_volume" in df.columns:
            df["net_position"] = df["long_volume"] - df["short_volume"]
        stats = {
            "trade_date": trade_date,
            "product": product,
            "member_count": df["member_name"].nunique() if "member_name" in df.columns else 0,
            "instrument_count": df["instrument_id"].nunique() if "instrument_id" in df.columns else 0,
            "total_long": df["long_volume"].sum() if "long_volume" in df.columns else 0,
            "total_short": df["short_volume"].sum() if "short_volume" in df.columns else 0,
        }
        if "instrument_id" in df.columns:
            contract_summary = df.groupby("instrument_id").agg({
                "long_volume": "sum",
                "short_volume": "sum",
                "member_name": "count",
            }).rename(columns={"member_name": "member_count"})
            stats["contract_summary"] = contract_summary.to_dict("index")
        return CFFEXParseResult(
            data=df, stats=stats, trade_date=trade_date,
            data_type="position", record_count=len(df), columns=df.columns.tolist(),
        )

    def parse_csv(self, file_path: str, data_type: str = "daily", **kwargs) -> CFFEXParseResult:
        if data_type in ["daily", "weekly"]:
            return self.parse_daily_csv(file_path, kwargs.get("trade_date"))
        elif data_type == "monthly":
            return self.parse_monthly_csv(file_path, kwargs.get("year_month"))
        elif data_type == "position":
            return self.parse_position_csv(file_path, kwargs.get("product", "MO"))
        else:
            raise ValueError(f"Unsupported data type: {data_type}")


def parse_cffex_csv(file_path: str, data_type: str = "daily", **kwargs) -> CFFEXParseResult:
    """Quick CFFEX CSV parser."""
    parser = CFFEXCSVParser()
    return parser.parse_csv(file_path, data_type, **kwargs)
