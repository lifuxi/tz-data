"""
CFFEX (China Financial Futures Exchange) data source adapter.
Fetches data from CFFEX official website via CSV download.

URL pattern (verified 2026-05):
  Daily:    http://www.cffex.com.cn/sj/hqsj/rtj/{YM}/{DD}/{YYYYMMDD}_1.csv
  Position: http://www.cffex.com.cn/sj/ccpm/{YM}/{DD}/{PRODUCT}_1.csv
  Monthly:  http://www.cffex.com.cn/sj/hqsj/ytj/{YM}/{YM}_1.csv
"""
import csv
import io
from datetime import date, timedelta
from typing import Optional
import requests
import logging

from tzdata_pkg.maintenance.sources.base_source import BaseDataSource

logger = logging.getLogger(__name__)

# CFFEX URL patterns (GBK encoding)
CFFEX_DAILY_URL = "http://www.cffex.com.cn/sj/hqsj/rtj/{year_month}/{day}/{date}_1.csv"
CFFEX_MONTHLY_URL = "http://www.cffex.com.cn/sj/hqsj/ytj/{year_month}/{year_month}_1.csv"
CFFEX_POSITION_URL = "http://www.cffex.com.cn/sj/ccpm/{year_month}/{day}/{product}_1.csv"

# Column mapping from CFFEX CSV headers to internal field names
CFFEX_COLUMN_MAP = {
    '合约代码': 'instrument_id',
    '今开盘': 'open',
    '最高价': 'high',
    '最低价': 'low',
    '今收盘': 'close',
    '今结算': 'settle',
    '前结算': 'prev_settle',
    '成交量': 'volume',
    '成交金额': 'turnover',
    '持仓量': 'open_interest',
    '持仓变化': 'oi_change',
    '涨跌1': 'daily_change',
    '涨跌2': 'daily_change_pct',
    'Delta': 'delta',
}


class CFFEXSource(BaseDataSource):
    """CFFEX official website data source using CSV download."""

    def __init__(self, config: dict = None):
        super().__init__('cffex', config or {})
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _download_csv(self, url: str) -> Optional[list[dict]]:
        """Download and parse a GBK-encoded CSV from CFFEX."""
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return None

            # Check if response is actually CSV (not HTML error page)
            content_type = resp.headers.get('Content-Type', '')
            if 'html' in content_type.lower() and 'csv' not in content_type.lower():
                # Double-check: try to detect HTML content
                text = resp.content[:200].decode('utf-8', errors='replace')
                if '<!DOCTYPE' in text or '<html' in text:
                    return None

            # Decode GBK (CFFEX uses GBK encoding)
            text = resp.content.decode('gbk', errors='replace')
            if not text.strip():
                return None

            reader = csv.DictReader(io.StringIO(text))
            rows = []
            for row in reader:
                mapped = {}
                for cn_col, en_col in CFFEX_COLUMN_MAP.items():
                    if cn_col in row:
                        val = row[cn_col].strip()
                        mapped[en_col] = self._parse_value(val, en_col)
                if mapped.get('instrument_id'):
                    rows.append(mapped)
            return rows
        except Exception as e:
            logger.warning(f"CFFEX CSV download/parse failed: {e}")
            return None

    def _parse_value(self, val: str, field: str):
        """Parse a CSV value with proper type conversion."""
        if val is None or val == '' or val == '--':
            return None
        if field in ('volume', 'open_interest', 'oi_change'):
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return 0
        elif field in ('open', 'high', 'low', 'close', 'settle', 'prev_settle',
                       'turnover', 'daily_change', 'daily_change_pct', 'delta'):
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return val

    def _build_daily_url(self, trade_date: date) -> str:
        """Build URL for daily settlement data CSV."""
        return CFFEX_DAILY_URL.format(
            year_month=trade_date.strftime('%Y%m'),
            day=trade_date.strftime('%d'),
            date=trade_date.strftime('%Y%m%d'),
        )

    def _build_position_url(self, trade_date: date, product: str) -> str:
        """Build URL for position ranking CSV."""
        return CFFEX_POSITION_URL.format(
            year_month=trade_date.strftime('%Y%m'),
            day=trade_date.strftime('%d'),
            product=product.upper(),
        )

    def fetch_daily_quotes(
        self,
        contract_code: str,
        start_date: date,
        end_date: date
    ) -> list[dict]:
        """Fetch daily quotes for a date range from CFFEX.

        For futures products (IM/IC/IF/IH), options are filtered out.
        For options products (MO/HO/IO), option contracts are kept.
        """
        # Determine if this is an options product
        is_option_product = contract_code.upper() in ('MO', 'HO', 'IO')
        results = []
        current = start_date
        while current <= end_date:
            url = self._build_daily_url(current)
            rows = self._download_csv(url)
            if rows:
                date_str = current.strftime('%Y-%m-%d')
                product_code = contract_code.upper() if contract_code else ''

                for row in rows:
                    # Filter by product if contract_code specified
                    inst_id = row.get('instrument_id', '')
                    if product_code and not inst_id.startswith(product_code):
                        continue
                    # Skip options only for futures products (not for options products like MO/HO/IO)
                    if not is_option_product and ('-C-' in inst_id or '-P-' in inst_id):
                        continue

                    results.append({
                        'exchange': 'CFFEX',
                        'contract_code': inst_id,
                        'trade_date': date_str,
                        'open': row.get('open'),
                        'high': row.get('high'),
                        'low': row.get('low'),
                        'close': row.get('close'),
                        'settle': row.get('settle'),
                        'prev_settle': row.get('prev_settle'),
                        'volume': row.get('volume', 0),
                        'turnover': row.get('turnover'),
                        'open_interest': row.get('open_interest', 0),
                        'daily_change': row.get('daily_change'),
                        'daily_change_pct': row.get('daily_change_pct'),
                        'source': 'exchange',
                    })

            current += timedelta(days=1)

        logger.info(f"CFFEX: fetched {len(results)} daily quotes for {contract_code}")
        return results

    def fetch_minute_quotes(
        self,
        contract_code: str,
        trade_date: date,
        frequency: str = '1min'
    ) -> list[dict]:
        """CFFEX does not provide minute-level data via public API."""
        logger.warning("CFFEX does not provide minute-level data")
        return []

    def fetch_top20_holdings(
        self,
        contract_code: str,
        trade_date: date
    ) -> list[dict]:
        """Fetch top 20 holdings from CFFEX position ranking CSV.

        CSV structure (3 header rows + data):
        Row 0: 交易日期,合约系列,排名,成交量排名,,,持买单量排名,,,持卖单量排名,,
        Row 1: ,,,会员简称,成交量,比上一交易日增减,,,会员简称,持买单量,比上一交易日增减,,
        Row 2: (sub-header continuation)
        Data:  20260515,MO2605,1,会员A,76186,-4087,会员B,0,-10122,会员C,0,-12231
        """
        product = contract_code.upper() if contract_code else 'MO'
        url = self._build_position_url(trade_date, product)

        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return []

            content_type = resp.headers.get('Content-Type', '')
            if 'html' in content_type.lower() and 'csv' not in content_type.lower():
                text = resp.content[:200].decode('utf-8', errors='replace')
                if '<!DOCTYPE' in text or '<html' in text:
                    return []

            text = resp.content.decode('gbk', errors='replace')
            if not text.strip():
                return []

            lines = text.strip().split('\n')
            if len(lines) < 4:
                return []

            # Skip 3 header rows, parse data with csv.reader
            reader = csv.reader(io.StringIO('\n'.join(lines[3:])))
            results = []
            date_str = trade_date.strftime('%Y-%m-%d')

            for row in reader:
                if len(row) < 12:
                    continue

                inst_id = row[1].strip()  # 合约系列
                rank = row[2].strip()     # 排名
                if not inst_id or not rank:
                    continue

                # Long side: columns 3-5 (member, volume, change)
                long_member = row[3].strip()
                long_vol = self._safe_int(row[4])
                long_chg = self._safe_int(row[5])

                # Short side: columns 6-8 (member, volume, change)
                short_member = row[6].strip()
                short_vol = self._safe_int(row[7])
                short_chg = self._safe_int(row[8])

                # Also capture volume ranking: columns 9-11
                vol_member = row[9].strip() if len(row) > 9 else ''
                vol_val = self._safe_int(row[10]) if len(row) > 10 else 0
                vol_chg = self._safe_int(row[11]) if len(row) > 11 else 0

                # Emit one record per side (long + short)
                if long_member:
                    results.append({
                        'exchange': 'CFFEX',
                        'trade_date': date_str,
                        'contract_code': inst_id,
                        'product': product,
                        'member_name': long_member,
                        'side': 'long',
                        'rank': self._safe_int(rank),
                        'volume': long_vol,
                        'volume_change': long_chg,
                        'source': 'exchange',
                    })
                if short_member:
                    results.append({
                        'exchange': 'CFFEX',
                        'trade_date': date_str,
                        'contract_code': inst_id,
                        'product': product,
                        'member_name': short_member,
                        'side': 'short',
                        'rank': self._safe_int(rank),
                        'volume': short_vol,
                        'volume_change': short_chg,
                        'source': 'exchange',
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
        """Get the latest trading date from CFFEX by probing daily CSV URLs."""
        today = date.today()
        # Check last 15 weekdays
        for i in range(15):
            check_date = today - timedelta(days=i)
            if check_date.weekday() >= 5:
                continue

            if data_type == 'daily':
                url = self._build_daily_url(check_date)
            else:
                url = self._build_daily_url(check_date)

            try:
                resp = self.session.get(url, timeout=15, stream=True)
                if resp.status_code == 200:
                    # Check if it's actually CSV data (not HTML error page)
                    content_type = resp.headers.get('Content-Type', '')
                    content = resp.content
                    if len(content) > 500:
                        if 'csv' in content_type.lower():
                            return check_date
                        # Also check content for CSV header
                        try:
                            text = content[:500].decode('gbk', errors='replace')
                            if '合约代码' in text:
                                return check_date
                        except Exception:
                            pass
            except Exception:
                continue

        return None

    def validate_credentials(self) -> bool:
        """Check if CFFEX website is accessible."""
        try:
            resp = self.session.get("http://www.cffex.com.cn/", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _safe_int(val) -> int:
        try:
            if val is None or val == '' or val == '--':
                return 0
            return int(float(val))
        except (ValueError, TypeError):
            return 0


# Auto-register
from tzdata_pkg.maintenance.sources.source_manager import SourceManager
SourceManager.register_source('cffex', CFFEXSource)
