"""Cross-database consistency checks between bills.db and tzdata_trading.db."""
import sqlite3
from datetime import datetime

from tzdata_pkg.verify.models import VerifyCheck, VerifyReport

import logging
logger = logging.getLogger(__name__)


class CrossDBChecker:
    """Check consistency between bills.db and tzdata_trading.db."""

    def __init__(self, bills_db_path: str, trading_db_path: str):
        self.bills_db_path = bills_db_path
        self.trading_db_path = trading_db_path

    def check_all(self) -> VerifyReport:
        """Run all cross-database consistency checks."""
        report = VerifyReport(timestamp=datetime.now().isoformat())

        self._check_trades_count(report)
        self._check_trades_sums(report)
        self._check_matched_trades(report)
        self._check_account_summary(report)
        self._check_positions_summary(report)

        return report

    def _check_trades_count(self, report: VerifyReport) -> None:
        """Compare trade counts between databases."""
        bills_count = self._count(self.bills_db_path, "trades")
        trading_count = self._count(self.trading_db_path, "trades")

        report.checks.append(VerifyCheck(
            name="trades_count",
            status="PASS" if bills_count == trading_count else "FAIL",
            source="trades table",
            expected=bills_count,
            actual=trading_count,
            deviation=abs(bills_count - trading_count),
        ))

    def _check_trades_sums(self, report: VerifyReport) -> None:
        """Compare trade amount aggregates between databases."""
        bills_sums = self._sums(self.bills_db_path, "trades", ["total_pnl", "commission", "turnover"])
        trading_sums = self._sums(self.trading_db_path, "trades", ["total_pnl", "commission", "turnover"])

        for col in ["total_pnl", "commission", "turnover"]:
            b_val = bills_sums.get(col, 0) or 0
            t_val = trading_sums.get(col, 0) or 0
            dev = abs(b_val - t_val)
            report.checks.append(VerifyCheck(
                name=f"trades_sum_{col}",
                status="PASS" if dev < 0.01 else "FAIL",
                source=f"trades.{col}",
                expected=round(b_val, 2),
                actual=round(t_val, 2),
                deviation=round(dev, 2),
            ))

    def _check_matched_trades(self, report: VerifyReport) -> None:
        """Compare matched trade counts."""
        bills_count = self._count(self.bills_db_path, "matched_trades")
        trading_count = self._count(self.trading_db_path, "matched_trades")

        report.checks.append(VerifyCheck(
            name="matched_trades_count",
            status="PASS" if bills_count == trading_count else "FAIL",
            source="matched_trades table",
            expected=bills_count,
            actual=trading_count,
            deviation=abs(bills_count - trading_count),
        ))

        # Also check net PnL sums
        bills_pnl = self._single(self.bills_db_path, "SELECT COALESCE(SUM(net_pnl),0) FROM matched_trades")
        trading_pnl = self._single(self.trading_db_path, "SELECT COALESCE(SUM(net_pnl),0) FROM matched_trades")
        dev = abs(bills_pnl - trading_pnl)
        report.checks.append(VerifyCheck(
            name="matched_trades_net_pnl",
            status="PASS" if dev < 0.01 else "FAIL",
            source="matched_trades.net_pnl",
            expected=round(bills_pnl, 2),
            actual=round(trading_pnl, 2),
            deviation=round(dev, 2),
        ))

    def _check_account_summary(self, report: VerifyReport) -> None:
        """Compare account summary row by row."""
        bills_rows = self._query(self.bills_db_path, "SELECT year, month, account_id, balance_b_f, balance_c_f, client_equity FROM account_summary ORDER BY year, month")
        trading_rows = self._query(self.trading_db_path, "SELECT year, month, account_id, balance_b_f, balance_c_f, client_equity FROM account_summary ORDER BY year, month")

        if not bills_rows and not trading_rows:
            report.checks.append(VerifyCheck(
                name="account_summary",
                status="SKIP",
                source="account_summary",
                expected="data exists",
                actual="both empty",
            ))
            return

        # Compare by (year, month) key
        bills_map = {(r[0], r[1]): r for r in bills_rows}
        trading_map = {(r[0], r[1]): r for r in trading_rows}

        all_keys = sorted(set(bills_map.keys()) | set(trading_map.keys()))
        mismatches = 0

        for key in all_keys:
            b_row = bills_map.get(key)
            t_row = trading_map.get(key)
            if not b_row or not t_row:
                mismatches += 1
                continue
            # Compare key fields
            for i, field_name in [(3, "balance_b_f"), (4, "balance_c_f"), (5, "client_equity")]:
                if abs((b_row[i] or 0) - (t_row[i] or 0)) > 0.01:
                    mismatches += 1
                    break

        report.checks.append(VerifyCheck(
            name="account_summary_consistency",
            status="PASS" if mismatches == 0 else "FAIL",
            source="account_summary",
            expected=f"{len(all_keys)} rows matching",
            actual=f"{mismatches} mismatches",
            deviation=mismatches,
        ))

    def _check_positions_summary(self, report: VerifyReport) -> None:
        """Compare positions summary aggregates."""
        bills_count = self._count(self.bills_db_path, "positions_summary")
        trading_count = self._count(self.trading_db_path, "positions_summary")

        report.checks.append(VerifyCheck(
            name="positions_summary_count",
            status="PASS" if bills_count == trading_count else "FAIL",
            source="positions_summary table",
            expected=bills_count,
            actual=trading_count,
            deviation=abs(bills_count - trading_count),
        ))

    def _count(self, db_path: str, table: str) -> int:
        try:
            return self._single(db_path, f"SELECT COUNT(*) FROM {table}")
        except Exception:
            return -1

    def _sums(self, db_path: str, table: str, columns: list[str]) -> dict:
        try:
            col_exprs = ", ".join(f"COALESCE(SUM({c}), 0) as {c}" for c in columns)
            return dict(self._query(db_path, f"SELECT {col_exprs} FROM {table}")[0])
        except Exception:
            return {}

    def _single(self, db_path: str, query: str):
        conn = sqlite3.connect(db_path)
        result = conn.execute(query).fetchone()[0]
        conn.close()
        return result

    def _query(self, db_path: str, query: str) -> list:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(query).fetchall()
        conn.close()
        return rows
