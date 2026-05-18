"""Daily IV benchmark computation.

Computes ATM IV, HV, skew, term structure, percentile, PCR for each
variety (MO/IO/HO) and stores results in iv_benchmark table.
"""

import json
import logging
import math
from datetime import date, datetime
from typing import Optional

import sqlite3

from tzdata_pkg.config import TZDATA_TRADING_DB
from tzdata_pkg.analysis.hv_calculator import HVCalculator

logger = logging.getLogger(__name__)

UNDERLYING_MAP = {
    "MO": "000852",
    "IO": "000300",
    "HO": "000016",
}


class IVBenchmarkDownloader:
    """Compute daily IV benchmark derivatives and store in iv_benchmark table."""

    # IV regime thresholds (percentile bands)
    REGIME_THRESHOLDS = {
        "very_low": 10,
        "low": 30,
        "normal": 70,
        "high": 90,
        "very_high": 100,
    }

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(TZDATA_TRADING_DB)
        self.hv_calc = HVCalculator(db_path=self.db_path)
        self._ensure_tables()

    def _ensure_tables(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS iv_benchmark (
                    trade_date       TEXT NOT NULL,
                    variety          TEXT NOT NULL,
                    atm_iv           REAL,
                    atm_strike       REAL,
                    spot_price       REAL,
                    hv_20            REAL,
                    hv_60            REAL,
                    iv_hv_spread     REAL,
                    skew_25delta     REAL,
                    term_structure   TEXT,
                    iv_percentile_1y REAL,
                    iv_regime        TEXT,
                    pcr_volume       REAL,
                    pcr_oi           REAL,
                    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (trade_date, variety)
                );
                CREATE INDEX IF NOT EXISTS idx_iv_benchmark_date ON iv_benchmark(trade_date);
                CREATE INDEX IF NOT EXISTS idx_iv_benchmark_variety ON iv_benchmark(variety);
            """)
        finally:
            conn.close()

    def compute_daily(self, trade_date: str) -> dict:
        """Compute all benchmark metrics for a single date across all varieties.

        Args:
            trade_date: Date string, YYYY-MM-DD or YYYYMMDD

        Returns:
            Dict with per-variety success/failure counts.
        """
        td_num = trade_date.replace("-", "")[:8]
        td_iso = self._normalize_date(trade_date)
        results = {}

        for variety in ["MO", "IO", "HO"]:
            try:
                row = self._compute_single(variety, td_num, td_iso)
                if row:
                    results[variety] = row
                else:
                    results[variety] = {"status": "skipped", "reason": "no_data"}
            except Exception as e:
                logger.warning(f"Failed to compute {variety} benchmark for {td_num}: {e}")
                results[variety] = {"status": "error", "error": str(e)}

        logger.info(f"IV benchmark {td_num}: {len(results)} varieties processed")
        return results

    def _compute_single(self, variety: str, td_num: str, td_iso: str) -> Optional[dict]:
        """Compute benchmark for one variety on one date."""
        conn = sqlite3.connect(self.db_path)
        try:
            # 1. ATM IV — find contract closest to ATM
            atm_iv, atm_strike, spot = self._get_atm_iv(conn, variety, td_iso)
            if atm_iv is None or spot is None:
                return None

            # 2. HV
            hv_20 = self.hv_calc.calculate_hv(variety, window=20)
            hv_60 = self.hv_calc.calculate_hv(variety, window=60)

            # 3. IV-HV spread
            iv_hv_spread = None
            if hv_20 is not None and atm_iv is not None:
                iv_hv_spread = round(atm_iv - hv_20, 4)

            # 4. Skew (25-delta)
            skew = self._compute_skew_25delta(conn, variety, td_num, spot)

            # 5. Term structure
            term_struct = self._compute_term_structure(conn, variety, td_num)

            # 6. IV percentile (1-year window)
            iv_pct = self._compute_iv_percentile(conn, variety, td_iso)

            # 7. Regime classification
            regime = self._classify_regime(iv_pct)

            # 8. PCR
            pcr = self.hv_calc.calculate_pcr(variety, td_iso)

            # Store (use ISO date for consistency)
            conn.execute("""
                INSERT OR REPLACE INTO iv_benchmark
                (trade_date, variety, atm_iv, atm_strike, spot_price,
                 hv_20, hv_60, iv_hv_spread, skew_25delta, term_structure,
                 iv_percentile_1y, iv_regime, pcr_volume, pcr_oi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                td_iso,
                variety,
                round(atm_iv, 4) if atm_iv else None,
                round(atm_strike, 1) if atm_strike else None,
                round(spot, 2),
                round(hv_20, 4) if hv_20 else None,
                round(hv_60, 4) if hv_60 else None,
                iv_hv_spread,
                round(skew, 4) if skew else None,
                json.dumps(term_struct) if term_struct else None,
                round(iv_pct, 2) if iv_pct is not None else None,
                regime,
                pcr.get("pcr_volume"),
                pcr.get("pcr_oi"),
            ))
            conn.commit()

            # Dual-write to QuestDB
            self._write_questdb_benchmark(td_iso, variety, round(atm_iv, 4) if atm_iv else None,
                round(atm_strike, 1) if atm_strike else None, round(spot, 2),
                round(hv_20, 4) if hv_20 else None, round(hv_60, 4) if hv_60 else None,
                iv_hv_spread, round(skew, 4) if skew else None,
                json.dumps(term_struct) if term_struct else None,
                round(iv_pct, 2) if iv_pct is not None else None, regime,
                pcr.get("pcr_volume"), pcr.get("pcr_oi"))

            return {
                "status": "ok",
                "atm_iv": atm_iv,
                "hv_20": hv_20,
                "skew": skew,
                "regime": regime,
            }
        finally:
            conn.close()

    def _get_atm_iv(self, conn, variety: str, td_iso: str) -> tuple:
        """Find ATM IV: contract whose strike is closest to spot price.

        Returns (atm_iv, atm_strike, spot_price) or (None, None, None).
        """
        code = UNDERLYING_MAP.get(variety)
        td_num = td_iso.replace("-", "")[:8]

        # Get spot price
        row = conn.execute("""
            SELECT close FROM option_sim_underlying_daily
            WHERE underlying = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 1
        """, (code, td_iso)).fetchone()
        if not row or not row[0]:
            return None, None, None

        spot = float(row[0])

        # Find contract closest to ATM (YYYYMMDD in mo_daily_iv_quotes)
        rows = conn.execute("""
            SELECT iv, strike FROM mo_daily_iv_quotes
            WHERE trade_date = ? AND underlying = ?
              AND iv IS NOT NULL AND iv > 0 AND strike IS NOT NULL
        """, (td_num, variety)).fetchall()

        if not rows:
            return None, None, spot

        # Pick contract with minimum |strike - spot|
        best = min(rows, key=lambda r: abs(r[1] - spot))
        return float(best[0]), float(best[1]), spot

    def _compute_skew_25delta(self, conn, variety: str, td_num: str, spot: float) -> Optional[float]:
        """Compute 25-delta skew: OTM Put IV - OTM Call IV."""
        rows = conn.execute("""
            SELECT option_type, iv, delta FROM mo_daily_iv_quotes
            WHERE trade_date = ? AND underlying = ?
              AND iv IS NOT NULL AND delta IS NOT NULL
        """, (td_num, variety)).fetchall()

        puts = [(float(r[2]), float(r[1])) for r in rows if r[0] == 'P']
        calls = [(float(r[2]), float(r[1])) for r in rows if r[0] == 'C']

        put_25iv = self._interp_delta_iv(puts, target=-0.25)
        call_25iv = self._interp_delta_iv(calls, target=0.25)

        if put_25iv is not None and call_25iv is not None:
            return put_25iv - call_25iv
        return None

    @staticmethod
    def _interp_delta_iv(delta_iv_pairs: list, target: float) -> Optional[float]:
        """Interpolate IV at target delta from sorted (delta, iv) pairs."""
        if len(delta_iv_pairs) < 2:
            return None

        sorted_pairs = sorted(delta_iv_pairs, key=lambda x: x[0])
        deltas = [p[0] for p in sorted_pairs]
        ivs = [p[1] for p in sorted_pairs]

        for i in range(len(deltas) - 1):
            if deltas[i] <= target <= deltas[i + 1]:
                t = (target - deltas[i]) / (deltas[i + 1] - deltas[i])
                return ivs[i] + t * (ivs[i + 1] - ivs[i])

        return None

    def _compute_term_structure(self, conn, variety: str, td_num: str) -> Optional[dict]:
        """Compute ATM IV term structure: {month_label: iv}."""
        code = UNDERLYING_MAP.get(variety)
        td_iso = self._normalize_date(td_num)
        row = conn.execute("""
            SELECT close FROM option_sim_underlying_daily
            WHERE underlying = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 1
        """, (code, td_iso)).fetchone()
        if not row or not row[0]:
            return None
        spot = float(row[0])

        rows = conn.execute("""
            SELECT expire_date, strike, iv FROM mo_daily_iv_quotes
            WHERE trade_date = ? AND underlying = ?
              AND iv IS NOT NULL AND strike IS NOT NULL
              AND expire_date IS NOT NULL
        """, (td_num, variety)).fetchall()

        if not rows:
            return None

        # Group by expiry month
        from collections import defaultdict
        month_contracts = defaultdict(list)

        for expire_date, strike, iv in rows:
            month_label = expire_date[:7]  # YYYY-MM
            month_contracts[month_label].append((float(strike), float(iv)))

        term_struct = {}
        for month_label in sorted(month_contracts):
            contracts = month_contracts[month_label]
            best = min(contracts, key=lambda c: abs(c[0] - spot))
            term_struct[month_label] = round(best[1], 4)

        return term_struct if term_struct else None

    def _compute_iv_percentile(self, conn, variety: str, trade_date: str) -> Optional[float]:
        """Compute IV percentile rank over trailing 1 year."""
        td = self._normalize_date(trade_date)
        rows = conn.execute("""
            SELECT atm_iv FROM iv_benchmark
            WHERE variety = ? AND trade_date <= ?
              AND atm_iv IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT 252
        """, (variety, td)).fetchall()

        ivs = [float(r[0]) for r in rows]
        if len(ivs) < 20:
            return None

        current = ivs[0]
        count_below = sum(1 for v in ivs if v < current)
        return (count_below / len(ivs)) * 100

    def _classify_regime(self, iv_pct: Optional[float]) -> str:
        """Classify IV regime from percentile rank."""
        if iv_pct is None:
            return "normal"
        if iv_pct < 10:
            return "very_low"
        if iv_pct < 30:
            return "low"
        if iv_pct < 70:
            return "normal"
        if iv_pct < 90:
            return "high"
        return "very_high"

    def _write_questdb_benchmark(self, trade_date: str, variety: str, atm_iv, atm_strike,
                                  spot_price, hv_20, hv_60, iv_hv_spread, skew_25delta,
                                  term_structure, iv_percentile_1y, iv_regime,
                                  pcr_volume, pcr_oi):
        """Dual-write iv_benchmark to QuestDB via ILP over TCP."""
        try:
            import socket
            ts_ns = int(datetime.strptime(trade_date, "%Y-%m-%d").timestamp() * 1e9)
            fields = []
            if atm_iv is not None:
                fields.append(f"atm_iv={atm_iv}")
            if atm_strike is not None:
                fields.append(f"atm_strike={atm_strike}")
            fields.append(f"spot_price={spot_price}")
            if hv_20 is not None:
                fields.append(f"hv_20={hv_20}")
            if hv_60 is not None:
                fields.append(f"hv_60={hv_60}")
            if iv_hv_spread is not None:
                fields.append(f"iv_hv_spread={iv_hv_spread}")
            if skew_25delta is not None:
                fields.append(f"skew_25delta={skew_25delta}")
            if term_structure:
                escaped = term_structure.replace("\\", "\\\\").replace('"', '\\"')
                fields.append(f'term_structure="{escaped}"')
            if iv_percentile_1y is not None:
                fields.append(f"iv_percentile_1y={iv_percentile_1y}")
            if iv_regime:
                fields.append(f'iv_regime="{iv_regime}"')
            if pcr_volume is not None:
                fields.append(f"pcr_volume={pcr_volume}")
            if pcr_oi is not None:
                fields.append(f"pcr_oi={pcr_oi}")

            ilp = f"iv_benchmark,variety={variety} {','.join(fields)} {ts_ns}\n"

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("localhost", 9009))
            sock.sendall(ilp.encode("utf-8"))
            sock.close()
        except Exception as e:
            logger.debug(f"QuestDB dual-write failed for benchmark: {e}")

    def compute_backfill(self, start_date: str, end_date: str) -> dict:
        """Backfill benchmarks for a date range.

        Args:
            start_date: YYYY-MM-DD or YYYYMMDD
            end_date: YYYY-MM-DD or YYYYMMDD

        Returns:
            Summary of processed dates.
        """
        from tzdata_pkg.maintenance.metadata.date_calculator import DateCalculator

        dc = DateCalculator()
        sd = self._normalize_date(start_date)
        ed = self._normalize_date(end_date)

        current = datetime.strptime(sd, "%Y-%m-%d").date()
        end = datetime.strptime(ed, "%Y-%m-%d").date()

        success_dates = 0
        skip_dates = 0

        while current <= end:
            td_str = current.isoformat()
            try:
                is_trading = dc.is_trading_day(current, exchange_code='CFFEX')
            except Exception:
                is_trading = True

            if is_trading:
                result = self.compute_daily(td_str)
                ok_count = sum(1 for v in result.values() if v.get("status") == "ok")
                if ok_count > 0:
                    success_dates += 1
                    logger.info(f"IV benchmark backfill {td_str}: {ok_count} varieties OK")
                else:
                    skip_dates += 1
            else:
                skip_dates += 1

            current += datetime.strptime("1900-01-01", "%Y-%m-%d").date() - datetime.strptime("1900-01-01", "%Y-%m-%d").date()
            from datetime import timedelta
            current += timedelta(days=1)

        logger.info(
            f"IV benchmark backfill {sd} to {ed}: "
            f"{success_dates} dates OK, {skip_dates} skipped"
        )
        return {"success_dates": success_dates, "skipped_dates": skip_dates}

    @staticmethod
    def _normalize_date(d: str) -> str:
        if "-" in d:
            return d[:10]
        if len(d) == 8 and d.isdigit():
            return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        return d
