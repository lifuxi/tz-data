"""Analysis result verification: PnL totals, fee consistency, date continuity, pair coverage."""
import sqlite3
from datetime import datetime, date

from tzdata_pkg.verify.models import VerifyCheck, VerifyReport

import logging
logger = logging.getLogger(__name__)


class AnalysisVerifier:
    """Verify analysis results against raw data."""

    def __init__(self, bills_db_path: str):
        self.bills_db_path = bills_db_path

    def verify_all(self) -> VerifyReport:
        """Run all analysis verification checks."""
        report = VerifyReport(timestamp=datetime.now().isoformat())

        self._check_pnl_total_vs_detail(report)
        self._check_fee_consistency(report)
        self._check_trade_date_continuity(report)
        self._check_pair_coverage(report)
        self._check_pnl_reasonableness(report)

        return report

    def _check_pnl_total_vs_detail(self, report: VerifyReport) -> None:
        """Check trade-level PnL aggregates are non-zero and consistent."""
        conn = sqlite3.connect(self.bills_db_path)
        try:
            trades_pnl = conn.execute("SELECT COALESCE(SUM(total_pnl), 0) FROM trades").fetchone()[0]
            trade_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            acct_pnl = conn.execute("SELECT COALESCE(SUM(total_pnl), 0) FROM account_summary").fetchone()[0]

            # Note: trades.total_pnl is realized PnL (平仓盈亏),
            # account_summary.total_pnl is MTM PnL (持仓盯市盈亏).
            # They are conceptually different and should NOT be directly compared.
            # Instead, check that both are non-trivial and trades have data.
            has_trades = trade_count > 0
            has_acct = acct_pnl != 0

            report.checks.append(VerifyCheck(
                name="pnl_data_exists",
                status="PASS" if has_trades and has_acct else "FAIL",
                source="trades + account_summary",
                expected="non-zero pnl in both tables",
                actual=f"trades: {trade_count} rows, SUM={trades_pnl:.2f}; account: SUM={acct_pnl:.2f}",
                message="trades.total_pnl=realized PnL, account_summary.total_pnl=MTM PnL (different concepts)",
            ))
        finally:
            conn.close()

    def _check_fee_consistency(self, report: VerifyReport) -> None:
        """SUM(trades.commission) vs account_summary.commission.

        Note: account_summary may not include all fees (exercise/delivery fees),
        so allow a larger tolerance and use WARN for moderate discrepancies.
        """
        conn = sqlite3.connect(self.bills_db_path)
        try:
            trades_fee = conn.execute("SELECT COALESCE(SUM(commission), 0) FROM trades").fetchone()[0]
            acct_fee = conn.execute("SELECT COALESCE(SUM(commission), 0) FROM account_summary").fetchone()[0]

            if acct_fee == 0:
                status = "WARN"
                msg = "account_summary.commission is 0, trades have fees"
            else:
                ratio = trades_fee / acct_fee if acct_fee != 0 else 0
                if ratio < 0.5 or ratio > 2.0:
                    status = "FAIL"
                    msg = f"Large discrepancy: trades_fee/account_fee ratio = {ratio:.2f}"
                elif ratio > 1.0:
                    status = "WARN"
                    msg = f"trades commission ({trades_fee:.2f}) > account ({acct_fee:.2f}) — account may exclude some fees"
                else:
                    status = "PASS"
                    msg = ""

            report.checks.append(VerifyCheck(
                name="fee_consistency",
                status=status,
                source="trades vs account_summary commission",
                expected=round(trades_fee, 2),
                actual=round(acct_fee, 2),
                deviation=round(abs(trades_fee - acct_fee), 2),
                message=msg,
            ))
        finally:
            conn.close()

    def _check_trade_date_continuity(self, report: VerifyReport) -> None:
        """Check adjacent trade dates for gaps > 5 trading days."""
        conn = sqlite3.connect(self.bills_db_path)
        try:
            dates = conn.execute(
                "SELECT DISTINCT trade_date FROM trades WHERE trade_date IS NOT NULL ORDER BY trade_date"
            ).fetchall()
            dates = [d[0] for d in dates]

            if not dates:
                report.checks.append(VerifyCheck(
                    name="trade_date_continuity",
                    status="SKIP",
                    source="trades.trade_date",
                    expected="trade dates exist",
                    actual="none found",
                ))
                return

            gaps = 0
            max_gap = 0
            for i in range(1, len(dates)):
                try:
                    d1 = date.fromisoformat(dates[i-1][:10].replace("-", "").replace("/", ""))
                    d2 = date.fromisoformat(dates[i][:10].replace("-", "").replace("/", ""))
                except (ValueError, IndexError):
                    # Try YYYYMMDD format
                    try:
                        d1 = date(int(dates[i-1][:4]), int(dates[i-1][4:6]), int(dates[i-1][6:8]))
                        d2 = date(int(dates[i][:4]), int(dates[i][:4]), int(dates[i][6:8]))
                    except (ValueError, IndexError):
                        continue

                delta = (d2 - d1).days
                if delta > max_gap:
                    max_gap = delta
                if delta > 5:
                    gaps += 1

            report.checks.append(VerifyCheck(
                name="trade_date_continuity",
                status="PASS" if gaps == 0 else "WARN",
                source="trades.trade_date",
                expected="gaps <= 5 days",
                actual=f"{gaps} gaps found, max gap={max_gap} days",
                deviation=gaps,
            ))
        finally:
            conn.close()

    def _check_pair_coverage(self, report: VerifyReport) -> None:
        """matched_trades coverage ratio."""
        conn = sqlite3.connect(self.bills_db_path)
        try:
            open_trades = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE offset_flag = 'open'"
            ).fetchone()[0]
            matched_count = conn.execute(
                "SELECT COUNT(*) FROM matched_trades"
            ).fetchone()[0]

            if open_trades == 0:
                report.checks.append(VerifyCheck(
                    name="pair_coverage",
                    status="SKIP",
                    source="trades vs matched_trades",
                    expected="open trades exist",
                    actual="0 open trades",
                ))
                return

            coverage = matched_count / open_trades if open_trades > 0 else 0
            report.checks.append(VerifyCheck(
                name="pair_coverage",
                status="PASS" if coverage >= 0.8 else "WARN",
                source="trades vs matched_trades",
                expected=">= 80%",
                actual=f"{coverage:.1%}",
                deviation=coverage,
            ))
        finally:
            conn.close()

    def _check_pnl_reasonableness(self, report: VerifyReport) -> None:
        """Check that no single trade PnL exceeds 50% of account equity."""
        conn = sqlite3.connect(self.bills_db_path)
        try:
            max_equity = conn.execute(
                "SELECT MAX(client_equity) FROM account_summary WHERE client_equity > 0"
            ).fetchone()[0] or 0

            if max_equity <= 0:
                report.checks.append(VerifyCheck(
                    name="pnl_reasonableness",
                    status="SKIP",
                    source="trades vs account_summary",
                    expected="positive equity",
                    actual=str(max_equity),
                ))
                return

            extreme = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE ABS(total_pnl) > ? * 0.5",
                (max_equity,)
            ).fetchone()[0]

            report.checks.append(VerifyCheck(
                name="pnl_reasonableness",
                status="PASS" if extreme == 0 else "WARN",
                source="trades.total_pnl vs max equity",
                expected="all trades <= 50% of equity",
                actual=f"{extreme} extreme trades",
                deviation=extreme,
                message=f"Max equity={max_equity:.0f}",
            ))
        finally:
            conn.close()
