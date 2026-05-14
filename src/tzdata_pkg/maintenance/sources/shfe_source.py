"""
SHFE (Shanghai Futures Exchange) data source adapter.
Fetches data from SHFE official website via web scraping.
"""
from datetime import date, timedelta
from typing import Optional
import requests
import logging

from tzdata_pkg.maintenance.sources.base_source import BaseDataSource

logger = logging.getLogger(__name__)

# SHFE API endpoints
SHFE_DAILY_URL = "http://www.shfe.com.cn/data/dailydata/kx/kx_{}.dat"
SHFE_SETTLEMENT_URL = "http://www.shfe.com.cn/data/dailydata/ck/rb{}.dat"


class SHFESource(BaseDataSource):
    """SHFE official website data source."""

    def __init__(self, config: dict = None):
        super().__init__('shfe', config or {})
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _fetch_shfe_daily(self, contract_code: str, trade_date: date) -> Optional[dict]:
        """
        Fetch daily quote from SHFE official data.

        SHFE publishes daily data in JSON format.
        URL pattern: http://www.shfe.com.cn/data/dailydata/kx/kx_YYYYMMDD.dat
        """
        try:
            date_str = trade_date.strftime('%Y%m%d')
            url = SHFE_DAILY_URL.format(date_str)

            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return None

            data = resp.json()
            if 'o_cur_instrument' not in data:
                return None

            for item in data['o_cur_instrument']:
                # SHFE contract codes: au2506, ag2506, cu2506, etc.
                inst_id = item.get('DELIVERYMONTH', '')
                product = item.get('PRODUCTID', '').strip()

                if inst_id == contract_code or product == contract_code.lower():
                    return {
                        'trade_date': date_str,
                        'open': self._safe_float(item.get('OPENPRICE')),
                        'high': self._safe_float(item.get('HIGHESTPRICE')),
                        'low': self._safe_float(item.get('LOWESTPRICE')),
                        'close': self._safe_float(item.get('CLOSEPRICE')),
                        'settle': self._safe_float(item.get('SETTLEMENTPRI')),
                        'volume': self._safe_int(item.get('VOLUME')),
                        'turnover': self._safe_float(item.get('TURNOVER')),
                        'open_interest': self._safe_int(item.get('OPENINTEREST')),
                    }
            return None
        except Exception as e:
            logger.warning(f"SHFE daily fetch failed: {e}")
            return None

    def _safe_float(self, val) -> Optional[float]:
        try:
            if val is None or val == '' or val == '-':
                return None
            return float(val)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, val) -> int:
        try:
            if val is None or val == '' or val == '-':
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
        """Fetch daily quotes for a date range from SHFE."""
        results = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Skip weekends
                quote = self._fetch_shfe_daily(contract_code, current)
                if quote:
                    results.append(quote)
            current += timedelta(days=1)

        logger.info(f"SHFE: fetched {len(results)} daily quotes for {contract_code}")
        return results

    def fetch_minute_quotes(
        self,
        contract_code: str,
        trade_date: date,
        frequency: str = '1min'
    ) -> list[dict]:
        """
        SHFE does not provide minute-level data via public API.
        This method is not supported for SHFE.
        """
        logger.warning("SHFE does not provide minute-level data")
        return []

    def fetch_top20_holdings(
        self,
        contract_code: str,
        trade_date: date
    ) -> list[dict]:
        """
        Fetch top 20 holdings from SHFE daily settlement report.

        SHFE publishes member rankings in the settlement data.
        URL pattern: http://www.shfe.com.cn/data/dailydata/ck/rbYYYYMMDD.dat
        """
        try:
            date_str = trade_date.strftime('%Y%m%d')
            url = SHFE_SETTLEMENT_URL.format(date_str)

            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []

            # SHFE settlement data has 'o_cur_item' list with member rankings
            items = data.get('o_cur_item', [])
            for item in items:
                # Filter by contract/product
                product_id = item.get('PRODUCTID', '').strip()
                delivery_month = item.get('DELIVERYMONTH', '')

                if product_id == contract_code.lower() or delivery_month == contract_code:
                    results.append({
                        'member_name': item.get('MEMBERNAME', ''),
                        'rank': self._safe_int(item.get('RANK')),
                        'long_volume': self._safe_int(item.get('BSVOL')),
                        'short_volume': self._safe_int(item.get('SSVOL')),
                        'long_change': self._safe_int(item.get('BVOLCHG')),
                        'short_change': self._safe_int(item.get('SVOLCHG')),
                    })

            return results
        except Exception as e:
            logger.warning(f"SHFE holdings fetch failed: {e}")
            return []

    def get_latest_date(
        self,
        contract_code: str,
        data_type: str
    ) -> Optional[date]:
        """Get the latest trading date from SHFE."""
        try:
            today = date.today()
            for i in range(15):
                check_date = today - timedelta(days=i)
                if check_date.weekday() >= 5:
                    continue

                date_str = check_date.strftime('%Y%m%d')
                url = SHFE_DAILY_URL.format(date_str)

                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('o_cur_instrument'):
                        return check_date
            return None
        except Exception:
            return None

    def validate_credentials(self) -> bool:
        """Check if SHFE website is accessible."""
        try:
            resp = self.session.get("http://www.shfe.com.cn/", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False


# Auto-register
from tzdata_pkg.maintenance.sources.source_manager import SourceManager
SourceManager.register_source('shfe', SHFESource)
