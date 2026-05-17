"""MO option implied volatility downloader.

Calculates IV from option close prices using Black-Scholes formula.
Data sources:
  - Option close: mo_minute_quotes (last bar of each day)
  - Underlying price: option_sim_underlying_daily (000852)
  - Contract info: mo_contract_master
Stores to tzdata_trading.db → mo_daily_iv_quotes.
"""

import logging
import sqlite3
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from tzdata_pkg.config import TZDATA_TRADING_DB
from tzdata_pkg.core.db import SQLitePool

logger = logging.getLogger(__name__)


class MOIVDownloader:
    """MO option IV calculator and downloader."""

    RISK_FREE_RATE = 0.02  # ~2% annual risk-free rate

    def __init__(self):
        self._pool = SQLitePool(str(TZDATA_TRADING_DB))
        self._ensure_table()

    def _ensure_table(self):
        with self._pool.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mo_daily_iv_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date TEXT NOT NULL,
                    contract_code TEXT NOT NULL,
                    underlying TEXT DEFAULT 'MO',
                    option_type TEXT,
                    strike REAL,
                    expire_date TEXT,
                    iv REAL,
                    delta REAL,
                    gamma REAL,
                    theta REAL,
                    vega REAL,
                    option_price REAL,
                    underlying_price REAL,
                    risk_free_rate REAL DEFAULT 0.02,
                    source TEXT DEFAULT 'bs_calc',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(trade_date, contract_code, source)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iv_date ON mo_daily_iv_quotes(trade_date)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iv_contract ON mo_daily_iv_quotes(contract_code)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_iv_underlying ON mo_daily_iv_quotes(underlying)"
            )

    def calculate_iv(self, trade_date: date) -> Dict[str, int]:
        """Calculate IV for all MO contracts on a given trading day.

        Returns dict with counts of successfully calculated IVs.
        """
        from tzdata_pkg.core.bs_model import bs_iv, bs_greeks

        date_str_iso = trade_date.isoformat()  # YYYY-MM-DD
        date_str_num = trade_date.strftime("%Y%m%d")  # YYYYMMDD

        # Get underlying price (000852)
        S = self._get_underlying_price(date_str_iso)
        if S is None or S <= 0:
            logger.warning(f"No underlying price for {date_str_iso}, skipping IV calc")
            return {"skipped": 1, "reason": "no_underlying_price"}

        # Get option close prices (last bar of the day per contract)
        contracts = self._get_option_closes(date_str_num)
        if not contracts:
            logger.info(f"No option data for {date_str_num}")
            return {"skipped": 1, "reason": "no_option_data"}

        # Get contract master info
        contract_info = self._get_contract_info()

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

                    # Time to expiry
                    T = self._time_to_expiry(trade_date, expire_date)
                    if T is None or T <= 1e-6 or T > 5.0:
                        fail_count += 1
                        continue

                    # Calculate IV
                    iv = bs_iv(opt_close, S, strike, T, self.RISK_FREE_RATE, opt_type)
                    if iv is None or iv <= 0 or iv > 5.0:
                        fail_count += 1
                        continue

                    # Calculate Greeks
                    greeks = bs_greeks(S, strike, T, self.RISK_FREE_RATE, iv, opt_type)

                    # Normalize expire_date
                    exp_normalized = self._normalize_date(expire_date)

                    conn.execute("""
                        INSERT OR REPLACE INTO mo_daily_iv_quotes
                        (trade_date, contract_code, underlying, option_type,
                         strike, expire_date, iv, delta, gamma, theta, vega,
                         option_price, underlying_price, risk_free_rate, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        date_str_num,
                        contract_code,
                        "MO",
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

        logger.info(
            f"IV calc {date_str_num}: {success_count} OK, {fail_count} failed, "
            f"underlying=000852@{S:.2f}"
        )
        return {"success": success_count, "failed": fail_count, "trade_date": date_str_num}

    def backfill(self, start_date: date, end_date: date) -> Dict[str, int]:
        """Backfill IV data for a date range.

        Processes in monthly chunks for performance — each chunk fetches
        option closes and underlying prices in one query, then calculates
        IV in memory.
        """
        from tzdata_pkg.core.bs_model import bs_iv, bs_greeks
        from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator

        dc = DateCalculator()
        total_success = 0
        total_fail = 0

        import sqlite3
        local_conn = sqlite3.connect(str(TZDATA_TRADING_DB))
        local_conn.execute("PRAGMA journal_mode=WAL")
        local_conn.execute("PRAGMA busy_timeout=10000")

        # Iterate by month to keep queries manageable
        current = start_date
        while current <= end_date:
            # Month boundaries
            if current.month == 12:
                month_end = date(current.year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(current.year, current.month + 1, 1) - timedelta(days=1)

            chunk_end = min(month_end, end_date)
            start_num = current.strftime("%Y%m%d")
            end_num = chunk_end.strftime("%Y%m%d")

            # Bulk load chunk data
            underlying_prices = self._load_underlying_prices(start_num, end_num)
            option_closes = self._load_option_closes_chunk(start_num, end_num)
            contract_info = self._get_contract_info()

            # Process each trading day in the chunk
            day = current
            while day <= chunk_end:
                try:
                    is_trading = dc.is_trading_day(day, exchange_code='CFFEX')
                except Exception:
                    is_trading = True

                if is_trading:
                    date_num = day.strftime("%Y%m%d")
                    date_iso = day.isoformat()

                    S = underlying_prices.get(date_iso)
                    day_contracts = option_closes.get(date_num)

                    if S and S > 0 and day_contracts:
                        success_count, fail_count = self._calc_iv_for_day(
                            local_conn, day, date_num, date_iso, S,
                            day_contracts, contract_info, bs_iv, bs_greeks,
                        )
                        total_success += success_count
                        total_fail += fail_count

                        if success_count > 0:
                            logger.info(
                                f"[{date_iso}] {success_count} IVs calculated, "
                                f"underlying=000852@{S:.2f}"
                            )

                day += timedelta(days=1)

            current = chunk_end + timedelta(days=1)

        local_conn.close()
        logger.info(
            f"IV backfill {start_date} to {end_date}: "
            f"{total_success} total OK, {total_fail} failed"
        )
        return {"total_success": total_success, "total_fail": total_fail}

    def _calc_iv_for_day(self, local_conn, current, date_num, date_iso, S,
                          day_contracts, contract_info, bs_iv, bs_greeks):
        """Calculate and store IV for one day's contracts."""
        success_count = 0
        fail_count = 0

        for contract_code, opt_close in day_contracts:
            try:
                info = contract_info.get(contract_code, {})
                strike = info.get("strike_price")
                opt_type = info.get("option_type")
                expire_date = info.get("expiry_date")

                if not strike or strike <= 0:
                    fail_count += 1
                    continue

                T = self._time_to_expiry(current, expire_date)
                if T is None or T <= 1e-6 or T > 5.0:
                    fail_count += 1
                    continue

                iv = bs_iv(opt_close, S, strike, T, self.RISK_FREE_RATE, opt_type)
                if iv is None or iv <= 0 or iv > 5.0:
                    fail_count += 1
                    continue

                greeks = bs_greeks(S, strike, T, self.RISK_FREE_RATE, iv, opt_type)
                exp_normalized = self._normalize_date(expire_date)

                local_conn.execute("""
                    INSERT OR REPLACE INTO mo_daily_iv_quotes
                    (trade_date, contract_code, underlying, option_type,
                     strike, expire_date, iv, delta, gamma, theta, vega,
                     option_price, underlying_price, risk_free_rate, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_num,
                    contract_code,
                    "MO",
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

        local_conn.commit()
        return success_count, fail_count

    def _load_underlying_prices(self, start_num: str, end_num: str) -> Dict[str, float]:
        """Load all 000852 closing prices in date range. Returns {YYYY-MM-DD: price}."""
        import sqlite3
        conn = sqlite3.connect(str(TZDATA_TRADING_DB))
        try:
            sd = f"{start_num[:4]}-{start_num[4:6]}-{start_num[6:]}"
            ed = f"{end_num[:4]}-{end_num[4:6]}-{end_num[6:]}"
            rows = conn.execute("""
                SELECT trade_date, close FROM option_sim_underlying_daily
                WHERE underlying = '000852'
                  AND trade_date >= ? AND trade_date <= ?
            """, (sd, ed)).fetchall()
            return {r[0]: float(r[1]) for r in rows if r[1]}
        finally:
            conn.close()

    def _load_option_closes_chunk(self, start_num: str, end_num: str) -> Dict[str, list]:
        """Load last-bar close per contract per day for a date range.

        Returns {YYYYMMDD: [(contract_code, close), ...]}.
        Uses GROUP BY + MAX for efficient last-bar extraction.
        """
        import sqlite3
        conn = sqlite3.connect(str(TZDATA_TRADING_DB))
        try:
            rows = conn.execute("""
                SELECT m.trade_date, m.contract_code, m.close
                FROM mo_minute_quotes m
                INNER JOIN (
                    SELECT trade_date, contract_code, MAX(trade_time) as max_time
                    FROM mo_minute_quotes
                    WHERE trade_date >= ? AND trade_date <= ?
                    GROUP BY trade_date, contract_code
                ) latest ON m.trade_date = latest.trade_date
                        AND m.contract_code = latest.contract_code
                        AND m.trade_time = latest.max_time
                WHERE m.trade_date >= ? AND m.trade_date <= ?
                ORDER BY m.trade_date, m.contract_code
            """, (start_num, end_num, start_num, end_num)).fetchall()

            result = {}
            for trade_date, contract_code, close in rows:
                result.setdefault(trade_date, []).append((contract_code, close))
            return result
        finally:
            conn.close()

    def download_incremental(self) -> Dict[str, int]:
        """Incremental IV sync — calculate since last stored date."""
        with self._pool.transaction() as conn:
            row = conn.execute(
                "SELECT MAX(trade_date) FROM mo_daily_iv_quotes"
            ).fetchone()

            if row and row[0]:
                last_date = datetime.strptime(row[0], "%Y%m%d").date()
                start_date = last_date + timedelta(days=1)
            else:
                # No data yet, go back 30 days
                start_date = date.today() - timedelta(days=30)

        end_date = date.today()
        if start_date > end_date:
            logger.info("IV data already up to date")
            return {"status": "up_to_date"}

        logger.info(f"IV incremental sync: {start_date} to {end_date}")
        return self.backfill(start_date, end_date)

    def _get_underlying_price(self, date_str_iso: str) -> Optional[float]:
        """Get 000852 closing price for the given date."""
        import sqlite3
        conn = sqlite3.connect(str(TZDATA_TRADING_DB))
        try:
            # Try exact date match first
            row = conn.execute("""
                SELECT close FROM option_sim_underlying_daily
                WHERE underlying = '000852' AND trade_date = ?
            """, (date_str_iso,)).fetchone()
            if row and row[0]:
                return float(row[0])

            # Fallback: get the most recent available date
            row = conn.execute("""
                SELECT close FROM option_sim_underlying_daily
                WHERE underlying = '000852' AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 1
            """, (date_str_iso,)).fetchone()
            if row and row[0]:
                return float(row[0])
        finally:
            conn.close()
        return None

    def _get_option_closes(self, date_str_num: str) -> list:
        """Get last-bar close price per contract for the given date."""
        import sqlite3
        conn = sqlite3.connect(str(TZDATA_TRADING_DB))
        try:
            rows = conn.execute("""
                SELECT m.contract_code, m.close
                FROM mo_minute_quotes m
                INNER JOIN (
                    SELECT contract_code, MAX(trade_time) as max_time
                    FROM mo_minute_quotes
                    WHERE trade_date = ?
                    GROUP BY contract_code
                ) latest ON m.contract_code = latest.contract_code
                        AND m.trade_time = latest.max_time
                WHERE m.trade_date = ?
                ORDER BY m.contract_code
            """, (date_str_num, date_str_num)).fetchall()
            return rows
        finally:
            conn.close()

    def _get_contract_info(self) -> Dict[str, dict]:
        """Get all MO contract info from master table."""
        import sqlite3
        conn = sqlite3.connect(str(TZDATA_TRADING_DB))
        try:
            rows = conn.execute("""
                SELECT contract_code, strike_price, option_type, expiry_date
                FROM mo_contract_master WHERE underlying = 'MO'
            """).fetchall()
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
        """Calculate time to expiry in years."""
        if not expiry_date_str:
            return None

        try:
            # Handle YYYY-MM-DD format
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
    def _normalize_date(date_str: str) -> Optional[str]:
        """Normalize date to YYYY-MM-DD format."""
        if not date_str:
            return None
        if "-" in date_str:
            return date_str[:10]
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str

    def close(self):
        self._pool.release()
