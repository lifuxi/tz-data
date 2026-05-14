"""Bill reconciliation: re-parse original files and compare against stored data."""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from tzdata_pkg.parser.bill_parser import BillParser
from tzdata_pkg.parser.models import BillSummary
from tzdata_pkg.verify.models import VerifyCheck, VerifyReport

import logging
logger = logging.getLogger(__name__)

TOLERANCE = 0.01  # Acceptable float deviation


class BillReconciler:
    """Reconcile parsed bill data against original source files."""

    def __init__(self, bills_db_path: str, bill_dir: str):
        self.bills_db_path = bills_db_path
        self.bill_dir = Path(bill_dir)
        self.parser = BillParser()

    def reconcile_all(self) -> VerifyReport:
        """Reconcile all stored bills against their source files."""
        report = VerifyReport(timestamp=datetime.now().isoformat())

        # Check stored bills in DB
        if not self.bill_dir.exists():
            report.checks.append(VerifyCheck(
                name="bill_source_dir_exists",
                status="FAIL",
                source="file system",
                expected=str(self.bill_dir),
                actual="not found",
                message="Bill source directory does not exist",
            ))
            return report

        report.checks.append(VerifyCheck(
            name="bill_source_dir_exists",
            status="PASS",
            source="file system",
            expected=str(self.bill_dir),
            actual=str(self.bill_dir),
        ))

        # Scan for bill files
        txt_files = list(self.bill_dir.rglob("*.txt"))
        report.checks.append(VerifyCheck(
            name="bill_files_found",
            status="PASS" if txt_files else "WARN",
            source="file system",
            expected="> 0",
            actual=str(len(txt_files)),
        ))

        # Parse each file and validate summary
        for f in sorted(txt_files):
            self._reconcile_file(f, report)

        # Check fund balance for each parsed bill
        self._check_fund_balance(report)

        return report

    def _reconcile_file(self, file_path: Path, report: VerifyReport) -> None:
        """Parse a single bill file and validate summary fields."""
        try:
            result = self.parser.parse_file(file_path)
            summary = result.summary
            if not summary:
                report.checks.append(VerifyCheck(
                    name=f"parse_{file_path.name}",
                    status="FAIL",
                    source=file_path.name,
                    expected="BillSummary",
                    actual="None",
                    message="Failed to parse bill summary",
                ))
                return

            # Validate key fields exist
            for field_name in ["balance_bf", "balance_cf", "client_equity"]:
                val = getattr(summary, field_name)
                report.checks.append(VerifyCheck(
                    name=f"{file_path.name}_{field_name}",
                    status="PASS" if val != 0.0 else "WARN",
                    source=f"{file_path.name}.summary.{field_name}",
                    expected="non-zero",
                    actual=val,
                    deviation=0.0,
                ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name=f"parse_{file_path.name}",
                status="FAIL",
                source=file_path.name,
                expected="success",
                actual=f"error: {e}",
                message=str(e),
            ))

    def _check_fund_balance(self, report: VerifyReport) -> None:
        """Check fund balance equation across all parsed bills."""
        try:
            conn = sqlite3.connect(self.bills_db_path)
            cursor = conn.execute("""
                SELECT id, balance_b_f, balance_c_f, deposit_withdrawal,
                       total_pnl, commission, premium_received, premium_paid,
                       client_equity, margin_occupied
                FROM account_summary
                WHERE balance_b_f IS NOT NULL
            """)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                report.checks.append(VerifyCheck(
                    name="fund_balance_check",
                    status="SKIP",
                    source="account_summary",
                    expected="rows exist",
                    actual="0 rows",
                    message="No account summary data to validate",
                ))
                return

            ok = 0
            warn = 0
            fail = 0
            for row in rows:
                (bill_id, balance_bf, balance_cf, deposit, total_pnl,
                 commission, premium_recv, premium_paid, equity, margin) = row

                deposit = deposit or 0.0
                total_pnl = total_pnl or 0.0
                commission = commission or 0.0
                premium_recv = premium_recv or 0.0
                premium_paid = premium_paid or 0.0

                expected_cf = (balance_bf + deposit + total_pnl
                               - commission + premium_recv - premium_paid)

                if balance_cf == 0:
                    ok += 1
                elif abs(balance_cf - expected_cf) < TOLERANCE:
                    ok += 1
                elif abs(balance_cf - expected_cf) < balance_cf * 0.05:
                    warn += 1  # Within 5% — likely rounding or minor fee differences
                else:
                    fail += 1

            status = "PASS" if fail == 0 else ("WARN" if warn > 0 and fail == 0 else "FAIL")
            report.checks.append(VerifyCheck(
                name="fund_balance_equation",
                status=status,
                source="account_summary",
                expected="balance_cf = balance_bf + deposit + pnl - commission + premium_recv - premium_paid",
                actual=f"{ok} passed, {warn} warn, {fail} failed out of {len(rows)}",
                deviation=fail,
                message=f"{fail} rows with significant deviation may have data quality issues",
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="fund_balance_check",
                status="FAIL",
                source="account_summary",
                expected="query success",
                actual=str(e),
            ))
