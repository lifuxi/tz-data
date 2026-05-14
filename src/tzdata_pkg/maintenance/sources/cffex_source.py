"""
CFFEX (China Financial Futures Exchange) data source adapter.
Fetches data from CFFEX official website via web scraping.
"""
from datetime import date, timedelta
from typing import Optional
import requests
import logging

from tzdata_pkg.maintenance.sources.base_source import BaseDataSource

logger = logging.getLogger(__name__)

# CFFEX API endpoints
CFFEX_DAILY_URL = "http://www.cffex.com.cn/sj/dayquotdata/"
CFFEX_SETTLEMENT_URL = "http://www.cffex.com.cn/sj/hqsj/"


class CFFEXSource(BaseDataSource):
    """CFFEX official website data source."""

    def __init__(self, config: dict = None):
        super().__init__('cffex', config or {})
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _fetch_cffex_daily(self, contract_code: str, trade_date: date) -> Optional[dict]:
        """
        Fetch daily quote from CFFEX settlement data.

        CFFEX publishes daily settlement data in JSON format.
        URL pattern: http://www.cffex.com.cn/sj/dayquotdata/YYYYMM/index.json
        """
        try:
            year_month = trade_date.strftime('%Y%m')
            url = f"{CFFEX_DAILY_URL}{year_month}/index.json"

            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return None

            data_list = resp.json()
            date_str = trade_date.strftime('%Y%m%d')

            # CFFEX contract codes: IM, IF, IC, IH, MO, HO
            # API returns: {"instrument_id": "IM2506", "close_price": "xxx", ...}
            for item in data_list:
                if item.get('data_time') == date_str:
                    inst_id = item.get('instrument_id', '')
                    if inst_id == contract_code or inst_id.startswith(contract_code.split('.')[0]):
                        return {
                            'trade_date': date_str,
                            'open': self._safe_float(item.get('open_price')),
                            'high': self._safe_float(item.get('highest_price')),
                            'low': self._safe_float(item.get('lowest_price')),
                            'close': self._safe_float(item.get('close_price')),
                            'settle': self._safe_float(item.get('settlement_price')),
                            'volume': self._safe_int(item.get('volume')),
                            'turnover': self._safe_float(item.get('turnover')),
                            'open_interest': self._safe_int(item.get('open_interest')),
                        }
            return None
        except Exception as e:
            logger.warning(f"CFFEX daily fetch failed: {e}")
            return None

    def _safe_float(self, val) -> Optional[float]:
        try:
            if val is None or val == '' or val == '--' or val == '':
                return None
            return float(val)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, val) -> int:
        try:
            if val is None or val == '' or val == '--':
                return 0
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    def fetch_daily_quotes(
        self,
        contract_code: str,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """Fetch daily quotes for a date range from CFFEX."""
        results = []
        current = start_date
        while current <= end_date:
            quote = self._fetch_cffex_daily(contract_code, current)
            if quote:
                results.append(quote)
            current += timedelta(days=1)

        logger.info(f"CFFEX: fetched {len(results)} daily quotes for {contract_code}")
        return results

    def fetch_minute_quotes(
        self,
        contract_code: str,
        trade_date: date,
        frequency: str = '1min'
    ) -> list[dict]:
        """
        CFFEX does not provide minute-level data via public API.
        This method is not supported for CFFEX.
        """
        logger.warning("CFFEX does not provide minute-level data")
        return []

    def fetch_top20_holdings(
        self,
        contract_code: str,
        trade_date: date
    ) -> list[dict]:
        """
        Fetch top 20 holdings from CFFEX daily settlement report.

        CFFEX publishes member holdings in the daily settlement data.
        """
        try:
            year_month = trade_date.strftime('%Y%m')
            date_str = trade_date.strftime('%Y%m%d')
            url = f"{CFFEX_SETTLEMENT_URL}{year_month}/{date_str}.json"

            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []

            for item in data:
                if item.get('instrument_id') == contract_code:
                    results.append({
                        'member_name': item.get('member_name', ''),
                        'rank': self._safe_int(item.get('rank')),
                        'long_volume': self._safe_int(item.get('buy_volume')),
                        'short_volume': self._safe_int(item.get('sell_volume')),
                        'long_change': self._safe_int(item.get('buy_volume_chg')),
                        'short_change': self._safe_int(item.get('sell_volume_chg')),
                    })

            return results
        except Exception as e:
            logger.warning(f"CFFEX holdings fetch failed: {e}")
            return []

    def get_latest_date(
        self,
        contract_code: str,
        data_type: str
    ) -> Optional[date]:
        """Get the latest trading date from CFFEX by checking recent settlement data."""
        try:
            today = date.today()
            # Check last 15 days for latest data
            for i in range(15):
                check_date = today - timedelta(days=i)
                if check_date.weekday() >= 5:
                    continue

                year_month = check_date.strftime('%Y%m')
                date_str = check_date.strftime('%Y%m%d')
                url = f"{CFFEX_DAILY_URL}{year_month}/index.json"

                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    data_list = resp.json()
                    for item in data_list:
                        if item.get('data_time') == date_str:
                            return check_date
            return None
        except Exception:
            return None

    def validate_credentials(self) -> bool:
        """Check if CFFEX website is accessible."""
        try:
            resp = self.session.get("http://www.cffex.com.cn/", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False


# Auto-register
from tzdata_pkg.maintenance.sources.source_manager import SourceManager
SourceManager.register_source('cffex', CFFEXSource)
