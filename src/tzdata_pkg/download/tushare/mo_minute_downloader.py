"""Tushare MO option minute bar downloader.

Fetches minute-level bars from Tushare opt_mins API and stores in:
  - tzdata_trading.db → mo_minute_quotes
"""

import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd

from tzdata_pkg.download.tushare.client import TushareClient
from tzdata_pkg.core.db import SQLitePool
from tzdata_pkg.config import TZDATA_TRADING_DB, get_tushare_config

logger = logging.getLogger(__name__)

SUPPORTED_FREQS = ("1min", "5min", "15min", "30min", "60min")


class MOMinuteDownloader:
    """MO option minute data downloader.

    Downloads minute bars for all MO option contracts from Tushare,
    stores to tzdata_trading.db.mo_minute_quotes.
    """

    def __init__(self, token: str = None, freq: str = "1min"):
        if not token:
            cfg = get_tushare_config()
            token = cfg.get("token", "")
        if not token:
            raise ValueError("TUSHARE_TOKEN not configured")

        self._client = TushareClient(token=token, rate_limit=0.5)
        self.freq = freq
        self._pool = SQLitePool(str(TZDATA_TRADING_DB))
        self._ensure_table()

    def _ensure_table(self):
        with self._pool.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mo_minute_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_time TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    contract_code TEXT NOT NULL,
                    underlying TEXT DEFAULT 'MO',
                    option_type TEXT,
                    strike REAL,
                    expire_date TEXT,
                    open REAL, high REAL, low REAL, close REAL,
                    volume REAL, turnover REAL, open_interest REAL,
                    frequency TEXT DEFAULT '1min',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(trade_time, contract_code, frequency)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mo_min_time ON mo_minute_quotes(trade_time)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mo_min_contract ON mo_minute_quotes(contract_code)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mo_min_date ON mo_minute_quotes(trade_date)"
            )

    def get_mo_contracts(self) -> List[Dict[str, Any]]:
        """Get all MO option contracts from local master table (avoids Tushare rate limit)."""
        import sqlite3
        from tzdata_pkg.config import TZDATA_TRADING_DB

        try:
            conn = sqlite3.connect(str(TZDATA_TRADING_DB))
            rows = conn.execute("""
                SELECT ts_code, contract_code, underlying, expiry_date, strike_price,
                       option_type, list_date, delist_date
                FROM mo_contract_master
                WHERE underlying = 'MO' AND status = 'active'
                ORDER BY expiry_date, strike_price, option_type
            """).fetchall()
            conn.close()

            result = []
            for r in rows:
                exp = r[3] or ''
                if len(exp) == 10:
                    exp = exp.replace('-', '')
                result.append({
                    "ts_code": r[0],
                    "contract_code": r[1],
                    "strike": r[4] or 0.0,
                    "option_type": r[5],
                    "expire_date": exp,
                    "list_date": r[6] or '',
                })

            logger.info(f"Found {len(result)} MO option contracts from local master")
            return result
        except Exception:
            # Fallback to Tushare if master table doesn't exist
            logger.warning("Local master not available, falling back to Tushare")
            return self._get_mo_contracts_from_tushare()

    def _get_mo_contracts_from_tushare(self) -> List[Dict[str, Any]]:
        """Fallback: Get MO contracts from Tushare opt_basic."""
        df = self._client.opt_basic(exchange="CFFEX")
        if df is None or df.empty:
            logger.warning("No option contracts returned from Tushare")
            return []

        ts_codes = df.get("ts_code", pd.Series(dtype=str))
        if isinstance(ts_codes, pd.Series):
            mask = ts_codes.str.startswith("MO", na=False)
            contracts_df = df[mask]
        else:
            return []

        result = []
        for _, row in contracts_df.iterrows():
            ts_code = row.get("ts_code", "")
            if not ts_code:
                continue
            result.append({
                "ts_code": ts_code,
                "contract_code": self._extract_contract(ts_code),
                "strike": self._parse_strike(ts_code),
                "option_type": self._parse_opt_type(ts_code),
                "expire_date": str(row.get("delist_date", "")),
                "list_date": str(row.get("list_date", "")),
            })

        logger.info(f"Found {len(result)} MO option contracts from Tushare")
        return result

    def download_contract(
        self,
        ts_code: str,
        start_date: date,
        end_date: date,
        contract_code: str = None,
        strike: float = None,
        opt_type: str = None,
        expire_date: str = None,
    ) -> int:
        """Download minute bars for a single contract, split by month."""
        if self.freq not in SUPPORTED_FREQS:
            raise ValueError(f"Unsupported frequency: {self.freq}")

        # Parse from ts_code if not provided
        contract_code = contract_code or self._extract_contract(ts_code)
        strike = strike if strike is not None else self._parse_strike(ts_code)
        opt_type = opt_type or self._parse_opt_type(ts_code)

        if not expire_date:
            expire_date = ""
        elif len(expire_date) == 8 and expire_date.isdigit():
            expire_date = f"{expire_date[:4]}-{expire_date[4:6]}-{expire_date[6:8]}"

        current = start_date
        total_count = 0

        while current <= end_date:
            # Month boundary
            if current.month == 12:
                month_end = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = current.replace(month=current.month + 1, day=1) - timedelta(days=1)

            actual_end = min(month_end, end_date)
            sd = current.strftime("%Y%m%d")
            ed = actual_end.strftime("%Y%m%d")

            df = self._client.opt_mins(
                ts_code=ts_code,
                freq=self.freq,
                start_date=sd,
                end_date=ed,
            )

            if df is not None and not df.empty:
                stored = self._store_data(df, contract_code, strike, opt_type, expire_date)
                total_count += stored
                logger.debug(f"  {ts_code} {sd}-{ed}: {stored} bars")

            # Next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)

            time.sleep(0.5)  # Rate limit

        return total_count

    def download_all_contracts(
        self,
        start_date: date,
        end_date: date,
        active_only: bool = True,
    ) -> Dict[str, int]:
        """Download minute bars for all MO contracts."""
        contracts = self.get_mo_contracts()
        if not contracts:
            logger.warning("No MO contracts to download")
            return {}

        # Filter active contracts (not yet delisted)
        if active_only:
            today_str = date.today().strftime("%Y%m%d")
            contracts = [
                c for c in contracts
                if not c["expire_date"] or c["expire_date"] >= today_str
                or c["expire_date"] == "0000-00-00"
            ]
            logger.info(f"Filtering to {len(contracts)} active contracts")

        results = {}
        for i, c in enumerate(contracts):
            ts_code = c["ts_code"]
            logger.info(f"[{i+1}/{len(contracts)}] Downloading {ts_code} ({c['contract_code']})")
            try:
                count = self.download_contract(
                    ts_code, start_date, end_date,
                    contract_code=c.get("contract_code"),
                    strike=c.get("strike"),
                    opt_type=c.get("option_type"),
                    expire_date=c.get("expire_date", ""),
                )
                results[c["contract_code"]] = count
            except Exception as e:
                logger.error(f"Failed to download {ts_code}: {e}")
                results[c["contract_code"]] = 0
            time.sleep(0.3)

        return results

    def download_incremental(self) -> Dict[str, int]:
        """Incremental sync: download only new data since last sync date."""
        with self._pool.transaction() as conn:
            row = conn.execute(
                "SELECT MAX(trade_date) FROM mo_minute_quotes WHERE frequency = ?",
                (self.freq,),
            ).fetchone()
            if row and row[0]:
                last_date = datetime.strptime(row[0], "%Y%m%d").date()
                start_date = last_date + timedelta(days=1)
            else:
                # No data yet, default to 30 days ago
                start_date = date.today() - timedelta(days=30)

        end_date = date.today()
        if start_date > end_date:
            logger.info("Minute data already up to date")
            return {}

        logger.info(f"Incremental sync: {start_date} to {end_date}")
        return self.download_all_contracts(start_date, end_date)

    def _store_data(
        self,
        df: pd.DataFrame,
        contract_code: str,
        strike: float,
        opt_type: str,
        expire_date: str,
    ) -> int:
        """Store minute bars to mo_minute_quotes table."""
        count = 0
        with self._pool.transaction() as conn:
            for _, row in df.iterrows():
                try:
                    trade_time = str(row.get("trade_time", ""))
                    if not trade_time:
                        continue

                    # Normalize: '2025-01-15 09:30:00' -> trade_date='20250115'
                    if " " in trade_time:
                        trade_date = trade_time.split(" ", 1)[0].replace("-", "")
                    elif len(trade_time) >= 8:
                        trade_date = trade_time[:8]
                    else:
                        continue

                    conn.execute("""
                        INSERT OR REPLACE INTO mo_minute_quotes
                        (trade_time, trade_date, contract_code, underlying,
                         option_type, strike, expire_date,
                         open, high, low, close, volume, turnover, open_interest, frequency)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade_time,
                        trade_date,
                        contract_code,
                        "MO",
                        opt_type,
                        strike if strike > 0 else None,
                        expire_date if expire_date else None,
                        self._safe_float(row.get("open")),
                        self._safe_float(row.get("high")),
                        self._safe_float(row.get("low")),
                        self._safe_float(row.get("close")),
                        self._safe_float(row.get("vol")),
                        self._safe_float(row.get("amount")),
                        self._safe_float(row.get("oi")),
                        self.freq,
                    ))
                    count += 1
                except Exception as e:
                    logger.debug(f"Failed to store minute bar: {e}")
        return count

    @staticmethod
    def _extract_contract(ts_code: str) -> str:
        """MO2505C8500.CFFEX or MO2505-C-8500.CFFEX -> MO2505-C-8500"""
        base = ts_code.split(".")[0] if "." in ts_code else ts_code
        # Already has dashes: MO2505-C-8500
        if "-" in base:
            return base
        # Compact format: MO2505C8500
        match = re.match(r"^([A-Z]+)(\d{4,6})([CP])(\d+)$", base)
        if match:
            return f"{match.group(1)}{match.group(2)}-{match.group(3)}-{match.group(4)}"
        return base

    @staticmethod
    def _parse_strike(ts_code: str) -> float:
        base = ts_code.split(".")[0] if "." in ts_code else ts_code
        # With dashes: MO2505-C-8500
        if "-" in base:
            parts = base.split("-")
            if len(parts) >= 3:
                try:
                    return float(parts[-1])
                except ValueError:
                    pass
        # Compact: MO2505C8500
        match = re.match(r"^[A-Z]+\d{4,6}[CP](\d+)$", base)
        if match:
            return float(match.group(1))
        return 0.0

    @staticmethod
    def _parse_opt_type(ts_code: str) -> str:
        base = ts_code.split(".")[0] if "." in ts_code else ts_code
        # With dashes
        if "-" in base:
            parts = base.split("-")
            if len(parts) >= 2:
                cp = parts[1].upper()
                if cp == "C":
                    return "call"
                elif cp == "P":
                    return "put"
        # Compact
        match = re.match(r"^[A-Z]+\d{4,6}([CP])", base)
        if match:
            return "call" if match.group(1) == "C" else "put"
        return None

    @staticmethod
    def _safe_float(val):
        try:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            return float(val)
        except Exception:
            return None

    def close(self):
        self._pool.release()
