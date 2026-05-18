"""Generic option IV downloader for MO/IO/HO.

Generalized from mo_iv_downloader.py to support all CFFEX index options.
Data flow:
  - Underlying price: option_sim_underlying_daily
  - Option close: mo_minute_quotes (MO) / io_minute_quotes (IO) / ho_minute_quotes (HO)
  - Contract info: mo_contract_master / io_contract_master / ho_contract_master
Stores to tzdata_trading.db → mo_daily_iv_quotes (with underlying column).
"""

import logging
import sqlite3
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from tzdata_pkg.config import TZDATA_TRADING_DB
from tzdata_pkg.core.db import SQLitePool

logger = logging.getLogger(__name__)


class OptionIVDownloader:
    """Download IV data for MO/IO/HO from Tushare opt_daily API."""

    VARIETY_MAP = {
        'MO': {'exchange': 'CFFEX', 'underlying': '000852', 'quote_table': 'mo_minute_quotes',
               'contract_table': 'mo_contract_master'},
        'IO': {'exchange': 'CFFEX', 'underlying': '000300', 'quote_table': 'io_minute_quotes',
               'contract_table': 'io_contract_master'},
        'HO': {'exchange': 'CFFEX', 'underlying': '000016', 'quote_table': 'ho_minute_quotes',
               'contract_table': 'ho_contract_master'},
    }

    RISK_FREE_RATE = 0.02

    def __init__(self, varieties: List[str] = None):
        self._pool = SQLitePool(str(TZDATA_TRADING_DB))
        self.varieties = varieties or ['MO']

    def download_daily(self, trade_date: str, varieties: List[str] = None) -> Dict[str, dict]:
        """Download IV data for all (or specified) varieties on a given date.

        Args:
            trade_date: YYYY-MM-DD or YYYYMMDD
            varieties: List of varieties to process (default: all configured)

        Returns:
            Per-variety result dict.
        """
        from tzdata_pkg.core.bs_model import bs_iv, bs_greeks

        td = trade_date.replace("-", "")[:8]
        td_iso = self._to_iso(trade_date)
        result = {}

        for variety in (varieties or self.varieties):
            cfg = self.VARIETY_MAP.get(variety)
            if not cfg:
                result[variety] = {"status": "error", "reason": f"unknown variety: {variety}"}
                continue

            try:
                success, failed = self._calc_iv_single(
                    td, td_iso, cfg, bs_iv, bs_greeks,
                )
                result[variety] = {"success": success, "failed": failed}
            except Exception as e:
                logger.warning(f"IV download failed for {variety} on {td}: {e}")
                result[variety] = {"status": "error", "error": str(e)}

        logger.info(f"IV download {td}: {result}")
        return result

    def _calc_iv_single(self, td: str, td_iso: str, cfg: dict, bs_iv_fn, bs_greeks_fn) -> tuple:
        """Calculate IV for one variety on one date. Returns (success, failed)."""
        variety = next(k for k, v in self.VARIETY_MAP.items() if v == cfg)
        S = self._get_underlying_price(cfg['underlying'], td_iso)
        if S is None or S <= 0:
            logger.warning(f"No underlying price for {variety} ({cfg['underlying']}) on {td_iso}")
            return 0, 0

        contracts = self._get_option_closes(cfg['quote_table'], td)
        if not contracts:
            logger.info(f"No option data for {variety} on {td}")
            return 0, 0

        contract_info = self._get_contract_info(cfg['contract_table'], variety)

        success_count = 0
        fail_count = 0

        with self._pool.transaction() as conn:
            for contract_code, opt_close in contracts:
                try:
                    info = contract_info.get(contract_code, {})
                    strike = info.get("strike_price")
                    opt_type = info.get("option_type")
                    expire_date = info.get("expiry_date")

                    if not strike or strike <= 0:
                        fail_count += 1
                        continue

                    T = self._time_to_expiry(datetime.strptime(td, "%Y%m%d").date(), expire_date)
                    if T is None or T <= 1e-6 or T > 5.0:
                        fail_count += 1
                        continue

                    iv = bs_iv_fn(opt_close, S, strike, T, self.RISK_FREE_RATE, opt_type)
                    if iv is None or iv <= 0 or iv > 5.0:
                        fail_count += 1
                        continue

                    greeks = bs_greeks_fn(S, strike, T, self.RISK_FREE_RATE, iv, opt_type)
                    exp_normalized = self._normalize_date(expire_date)

                    conn.execute("""
                        INSERT OR REPLACE INTO mo_daily_iv_quotes
                        (trade_date, contract_code, underlying, option_type,
                         strike, expire_date, iv, delta, gamma, theta, vega,
                         option_price, underlying_price, risk_free_rate, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        td,
                        contract_code,
                        variety,
                        opt_type,
                        strike,
                        exp_normalized,
                        iv,
                        greeks.get("delta"),
                        greeks.get("gamma"),
                        greeks.get("theta"),
                        greeks.get("vega"),
                        opt_close,
                        S,
                        self.RISK_FREE_RATE,
                        "bs_calc",
                    ))
                    success_count += 1

                except Exception as e:
                    logger.debug(f"IV calc failed for {contract_code}: {e}")
                    fail_count += 1

        if success_count > 0:
            logger.info(
                f"[{td_iso}] {variety}: {success_count} IVs calculated, "
                f"underlying={cfg['underlying']}@{S:.2f}"
            )

        return success_count, fail_count

    def backfill(self, start_date: str, end_date: str, varieties: List[str] = None) -> dict:
        """Full backfill for historical dates."""
        from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator

        dc = DateCalculator()
        sd = self._normalize_date(start_date)
        ed = self._normalize_date(end_date)
        current = datetime.strptime(sd, "%Y-%m-%d").date()
        end = datetime.strptime(ed, "%Y-%m-%d").date()

        total_success = 0
        total_fail = 0

        for variety in (varieties or self.varieties):
            cfg = self.VARIETY_MAP.get(variety)
            if not cfg:
                continue

            while current <= end:
                try:
                    is_trading = dc.is_trading_day(current, exchange_code='CFFEX')
                except Exception:
                    is_trading = True

                if is_trading:
                    td_num = current.strftime("%Y%m%d")
                    td_iso = current.isoformat()
                    success, failed = self._calc_iv_single(td_num, td_iso, cfg, None, None)
                    # Fallback to mo_iv_downloader logic if needed
                    from tzdata_pkg.core.bs_model import bs_iv, bs_greeks
                    success, failed = self._calc_iv_single(
                        td_num, td_iso, cfg, bs_iv, bs_greeks,
                    )
                    total_success += success
                    total_fail += failed

                current += timedelta(days=1)

            current = datetime.strptime(sd, "%Y-%m-%d").date()

        logger.info(
            f"IV backfill {sd} to {ed}: "
            f"{total_success} total OK, {total_fail} failed"
        )
        return {"total_success": total_success, "total_fail": total_fail}

    def download_incremental(self, varieties: List[str] = None) -> dict:
        """Incremental IV sync — calculate since last stored date."""
        with self._pool.transaction() as conn:
            row = conn.execute(
                "SELECT MAX(trade_date) FROM mo_daily_iv_quotes"
            ).fetchone()

            if row and row[0]:
                last_date = datetime.strptime(row[0], "%Y%m%d").date()
                start_date = last_date + timedelta(days=1)
            else:
                start_date = date.today() - timedelta(days=30)

        end_date = date.today()
        if start_date > end_date:
            logger.info("IV data already up to date")
            return {"status": "up_to_date"}

        logger.info(f"IV incremental sync: {start_date} to {end_date}")
        return self.backfill(
            start_date.isoformat(), end_date.isoformat(),
            varieties=varieties or self.varieties,
        )

    def _get_underlying_price(self, code: str, date_str: str) -> Optional[float]:
        conn = sqlite3.connect(str(TZDATA_TRADING_DB))
        try:
            row = conn.execute("""
                SELECT close FROM option_sim_underlying_daily
                WHERE underlying = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 1
            """, (code, date_str)).fetchone()
            if row and row[0]:
                return float(row[0])
        finally:
            conn.close()
        return None

    def _get_option_closes(self, table: str, date_str: str) -> list:
        conn = sqlite3.connect(str(TZDATA_TRADING_DB))
        try:
            # Check table exists
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            if not exists:
                return []

            rows = conn.execute(f"""
                SELECT m.contract_code, m.close
                FROM {table} m
                INNER JOIN (
                    SELECT contract_code, MAX(trade_time) as max_time
                    FROM {table}
                    WHERE trade_date = ?
                    GROUP BY contract_code
                ) latest ON m.contract_code = latest.contract_code
                        AND m.trade_time = latest.max_time
                WHERE m.trade_date = ?
                ORDER BY m.contract_code
            """, (date_str, date_str)).fetchall()
            return rows
        finally:
            conn.close()

    def _get_contract_info(self, table: str, variety: str) -> Dict[str, dict]:
        conn = sqlite3.connect(str(TZDATA_TRADING_DB))
        try:
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            if not exists:
                return {}

            rows = conn.execute(f"""
                SELECT contract_code, strike_price, option_type, expiry_date
                FROM {table} WHERE underlying = ?
            """, (variety,)).fetchall()
            return {
                r[0]: {
                    "strike_price": r[1],
                    "option_type": r[2],
                    "expiry_date": r[3],
                }
                for r in rows
            }
        finally:
            conn.close()

    @staticmethod
    def _time_to_expiry(current_date: date, expiry_date_str: str) -> Optional[float]:
        if not expiry_date_str:
            return None
        try:
            if "-" in expiry_date_str:
                exp_date = date.fromisoformat(expiry_date_str)
            elif len(expiry_date_str) == 8 and expiry_date_str.isdigit():
                exp_date = date(
                    int(expiry_date_str[:4]),
                    int(expiry_date_str[4:6]),
                    int(expiry_date_str[6:8]),
                )
            else:
                return None
            days = (exp_date - current_date).days
            if days <= 0:
                return None
            return days / 365.0
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        if "-" in date_str:
            return date_str[:10]
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str

    @staticmethod
    def _to_iso(date_str: str) -> str:
        if "-" in date_str:
            return date_str[:10]
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str
