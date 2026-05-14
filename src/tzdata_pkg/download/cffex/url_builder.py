from datetime import datetime, date, timedelta
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class CFFEXURLInfo:
    """URL info structure."""
    url: str
    data_type: str
    trade_date: str
    product: Optional[str] = None
    filename: Optional[str] = None


class CFFEXURLBuilder:
    """CFFEX URL builder."""

    BASE_URL = "http://www.cffex.com.cn/sj/"

    URL_PATTERNS = {
        "daily": "hqsj/rtj/{year_month}/{day}/{date}_1.csv",
        "weekly": "hqsj/ztj/{year_month}/{day}/{date}_1.csv",
        "monthly": "hqsj/ytj/{year_month}/{year_month}_1.csv",
        "position": "ccpm/{year_month}/{day}/{product}_1.csv",
    }

    def __init__(self, base_url: str = None):
        self.base_url = base_url or self.BASE_URL

    def build_daily_url(self, trade_date: date) -> CFFEXURLInfo:
        year_month = trade_date.strftime("%Y%m")
        day = trade_date.strftime("%d")
        date_str = trade_date.strftime("%Y%m%d")
        relative_path = self.URL_PATTERNS["daily"].format(
            year_month=year_month, day=day, date=date_str
        )
        return CFFEXURLInfo(
            url=self.base_url + relative_path,
            data_type="daily",
            trade_date=date_str,
            filename=f"daily_{date_str}.csv",
        )

    def build_weekly_url(self, trade_date: date) -> CFFEXURLInfo:
        year_month = trade_date.strftime("%Y%m")
        day = trade_date.strftime("%d")
        date_str = trade_date.strftime("%Y%m%d")
        relative_path = self.URL_PATTERNS["weekly"].format(
            year_month=year_month, day=day, date=date_str
        )
        return CFFEXURLInfo(
            url=self.base_url + relative_path,
            data_type="weekly",
            trade_date=date_str,
            filename=f"weekly_{date_str}.csv",
        )

    def build_monthly_url(self, year_month: str) -> CFFEXURLInfo:
        relative_path = self.URL_PATTERNS["monthly"].format(year_month=year_month)
        return CFFEXURLInfo(
            url=self.base_url + relative_path,
            data_type="monthly",
            trade_date=year_month,
            filename=f"monthly_{year_month}.csv",
        )

    def build_position_url(self, trade_date: date, product: str) -> CFFEXURLInfo:
        year_month = trade_date.strftime("%Y%m")
        day = trade_date.strftime("%d")
        date_str = trade_date.strftime("%Y%m%d")
        relative_path = self.URL_PATTERNS["position"].format(
            year_month=year_month, day=day, product=product
        )
        return CFFEXURLInfo(
            url=self.base_url + relative_path,
            data_type="position",
            trade_date=date_str,
            product=product,
            filename=f"position_{product}_{date_str}.csv",
        )

    def build_url(self, data_type: str, trade_date: date, product: str = None) -> CFFEXURLInfo:
        if data_type == "daily":
            return self.build_daily_url(trade_date)
        elif data_type == "weekly":
            return self.build_weekly_url(trade_date)
        elif data_type == "monthly":
            return self.build_monthly_url(trade_date.strftime("%Y%m"))
        elif data_type == "position":
            if not product:
                raise ValueError("position type requires product parameter")
            return self.build_position_url(trade_date, product)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def build_batch_urls(self, data_type: str, start_date: date, end_date: date,
                         product: str = None) -> List[CFFEXURLInfo]:
        urls = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Mon-Fri
                try:
                    url_info = self.build_url(data_type, current, product)
                    urls.append(url_info)
                except ValueError:
                    pass
            current += timedelta(days=1)
        return urls

    def build_monthly_batch_urls(self, start_year: int, end_year: int) -> List[CFFEXURLInfo]:
        urls = []
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                year_month = f"{year}{month:02d}"
                urls.append(self.build_monthly_url(year_month))
        return urls

    @staticmethod
    def parse_date_from_url(url: str) -> Optional[str]:
        import re
        match = re.search(r"(\d{8})", url)
        if match:
            return match.group(1)
        match = re.search(r"/(\d{6})_\d?\.csv", url)
        if match:
            return match.group(1)
        return None


def build_cffex_url(data_type: str, trade_date: date, product: str = None) -> str:
    """Quick CFFEX URL builder."""
    builder = CFFEXURLBuilder()
    url_info = builder.build_url(data_type, trade_date, product)
    return url_info.url
