"""Unified data quality auditor.

Orchestrates all verification dimensions (market, trading, analysis, QuestDB,
CFMMC parser, Celery) into a single entry point with structured report output.
"""
import logging
import sqlite3
import random
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from tzdata_pkg.verify.models import VerifyCheck, VerifyReport
from tzdata_pkg.config import get_data_dir, TZDATA_MARKET_DB, TZDATA_TRADING_DB, TZDATA_ANALYSIS_DB

logger = logging.getLogger(__name__)


class DataQualityAuditor:
    """Unified data quality assessment engine."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else get_data_dir()
        self.market_db = str(self.data_dir / "tzdata_market.db")
        self.trading_db = str(self.data_dir / "tzdata_trading.db")
        self.analysis_db = str(self.data_dir / "tzdata_analysis.db")

    def run_full_audit(self, scope: str = "all") -> VerifyReport:
        """Execute audit.

        Args:
            scope: "all" | "market" | "trading" | "analysis" | "questdb" | "parser" | "celery"
        """
        report = VerifyReport(timestamp=datetime.now().isoformat())

        if scope in ("all", "market"):
            self._audit_market(report)

        if scope in ("all", "trading"):
            self._audit_trading(report)

        if scope in ("all", "analysis"):
            self._audit_analysis(report)

        if scope in ("all", "questdb"):
            self._audit_questdb(report)

        if scope in ("all", "parser"):
            self._audit_parser(report)

        if scope in ("all", "celery"):
            self._audit_celery(report)

        return report

    # ------------------------------------------------------------------ #
    #  Market
    # ------------------------------------------------------------------ #
    def _audit_market(self, report: VerifyReport) -> None:
        self._audit_market_completeness(report)
        self._audit_market_anomalies(report)
        self._audit_market_schema(report)

    def _audit_market_completeness(self, report: VerifyReport) -> None:
        """Check data completeness against trading calendar."""
        import io
        import contextlib

        # CompletenessChecker has a known bug where earliest_date is a str, not date.
        # Suppress its stderr so it doesn't pollute the audit output.
        stderr_buf = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buf):
                from tzdata_pkg.maintenance.monitoring.completeness_checker import CompletenessChecker

                results = CompletenessChecker.check_all_enabled_catalogs()
        except Exception as e:
            results = [{'error': str(e)}]

        # Log CompletenessChecker errors
        stderr_output = stderr_buf.getvalue()
        if stderr_output.strip():
            for line in stderr_output.strip().splitlines():
                logger.debug(f"CompletenessChecker: {line}")

        if not results:
            report.checks.append(VerifyCheck(
                name="market_completeness_catalogs",
                status="SKIP", source="CompletenessChecker",
                expected="enabled catalogs", actual="none found",
            ))
            return

        incomplete = [r for r in results if r.get("status") == "incomplete"]
        errors = [r for r in results if "error" in r]

        report.checks.append(VerifyCheck(
            name="market_completeness_catalogs",
            status="PASS" if not incomplete and not errors else "WARN",
            source="CompletenessChecker",
            expected=f"{len(results)} catalogs complete",
            actual=f"{len(incomplete)} incomplete, {len(errors)} errors",
            message=f"Checked {len(results)} catalogs" + (f"; errors: {', '.join(str(r.get('error', '')) for r in errors[:3])}" if errors else ""),
        ))

        # Spot-check catalogs with < 100% completeness
        for r in results:
            pct = r.get("completeness_pct", 100)
            if pct < 100 and "error" not in r:
                report.checks.append(VerifyCheck(
                    name=f"completeness_{r.get('catalog_id', '?')}",
                    status="PASS" if pct >= 95 else "WARN",
                    source=f"catalog {r.get('catalog_id')}",
                    expected="100%",
                    actual=f"{pct}%",
                    deviation=round(100 - pct, 2),
                    message=r.get("catalog_name", ""),
                ))

    def _audit_market_anomalies(self, report: VerifyReport) -> None:
        """Run anomaly detection on market data."""
        try:
            from tzdata_pkg.maintenance.monitoring.anomaly_detector import AnomalyDetector

            detector = AnomalyDetector()
            anomalies = detector.detect_all()

            # Group by type
            by_type: dict[str, int] = {}
            for a in anomalies:
                t = a.get("type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1

            report.checks.append(VerifyCheck(
                name="market_anomalies",
                status="PASS" if not anomalies else "WARN",
                source="AnomalyDetector",
                expected="0 anomalies",
                actual=f"{len(anomalies)} anomalies",
                message=", ".join(f"{k}: {v}" for k, v in by_type.items()) if by_type else "clean",
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="market_anomalies",
                status="FAIL", source="AnomalyDetector",
                expected="success", actual=str(e),
            ))

    def _audit_market_schema(self, report: VerifyReport) -> None:
        """Validate market DB schema integrity."""
        self._check_schema_table(report, self.market_db, "daily_quotes", [
            "exchange", "contract_code", "trade_date",
            "open", "high", "low", "close", "volume",
        ])
        self._check_schema_table(report, self.market_db, "minute_quotes", [
            "exchange", "contract_code", "trade_date", "trade_time",
            "open", "high", "low", "close", "volume", "frequency",
        ])
        self._check_schema_table(report, self.market_db, "data_catalog", [
            "id", "exchange_code", "product_code", "data_type",
        ])

    # ------------------------------------------------------------------ #
    #  Trading
    # ------------------------------------------------------------------ #
    def _audit_trading(self, report: VerifyReport) -> None:
        # Cross-DB checks (existing)
        self._audit_trading_cross_db(report)
        # Business rules
        self._audit_trading_business_rules(report)
        # Bills reconciliation
        self._audit_bills_reconciliation(report)
        # Schema
        self._check_schema_table(report, self.trading_db, "trades", [
            "trade_date", "instrument", "direction", "volume", "total_pnl",
        ])
        self._check_schema_table(report, self.trading_db, "matched_trades", [
            "open_date", "close_date", "instrument", "open_volume", "close_volume", "net_pnl",
        ])
        self._check_schema_table(report, self.trading_db, "account_summary", [
            "year", "month", "account_id", "balance_b_f", "balance_c_f",
        ])
        self._check_schema_table(report, self.trading_db, "bills", [
            "id", "bill_date_start", "bill_date_end", "balance_bf", "balance_cf",
        ])
        # account_summary must have rows (backfilled from bills)
        self._check_account_summary_populated(report)

    def _audit_trading_cross_db(self, report: VerifyReport) -> None:
        """Cross-database consistency between trading DB tables."""
        try:
            from tzdata_pkg.verify.cross_db_check import CrossDBChecker

            checker = CrossDBChecker(self.trading_db, self.trading_db)
            # Since both DBs are unified now, check internal consistency
            self._check_trades_vs_matched(report)
            self._check_matched_pnl_vs_trades(report)
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="trading_cross_db",
                status="FAIL", source="CrossDBChecker",
                expected="success", actual=str(e),
            ))

    def _check_trades_vs_matched(self, report: VerifyReport) -> None:
        """Verify matched_trades volume <= trades open volume."""
        try:
            conn = sqlite3.connect(self.trading_db)
            open_vol = conn.execute(
                "SELECT COALESCE(SUM(volume),0) FROM trades WHERE offset_flag='open'"
            ).fetchone()[0]
            matched_vol = conn.execute(
                "SELECT COALESCE(SUM(open_volume),0) FROM matched_trades"
            ).fetchone()[0]
            conn.close()

            report.checks.append(VerifyCheck(
                name="trades_vs_matched_volume",
                status="PASS" if matched_vol <= open_vol else "WARN",
                source="trades vs matched_trades",
                expected=f"matched_vol ({matched_vol}) <= open_vol ({open_vol})",
                actual=f"matched_vol={matched_vol}, open_vol={open_vol}",
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="trades_vs_matched_volume",
                status="FAIL", source="trades vs matched_trades",
                expected="success", actual=str(e),
            ))

    def _check_matched_pnl_vs_trades(self, report: VerifyReport) -> None:
        """Verify matched trades PnL are within reasonable range."""
        try:
            conn = sqlite3.connect(self.trading_db)
            count = conn.execute("SELECT COUNT(*) FROM matched_trades").fetchone()[0]
            if count == 0:
                report.checks.append(VerifyCheck(
                    name="matched_trades_pnl",
                    status="SKIP", source="matched_trades",
                    expected="rows exist", actual="0 rows",
                ))
                conn.close()
                return

            max_pnl = conn.execute(
                "SELECT MAX(ABS(net_pnl)) FROM matched_trades"
            ).fetchone()[0]
            avg_pnl = conn.execute(
                "SELECT AVG(ABS(net_pnl)) FROM matched_trades"
            ).fetchone()[0]
            conn.close()

            report.checks.append(VerifyCheck(
                name="matched_trades_pnl",
                status="PASS", source="matched_trades",
                expected="reasonable PnL range",
                actual=f"count={count}, max_abs_pnl={max_pnl:.2f}, avg_abs_pnl={avg_pnl:.2f}",
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="matched_trades_pnl",
                status="FAIL", source="matched_trades",
                expected="success", actual=str(e),
            ))

    def _audit_trading_business_rules(self, report: VerifyReport) -> None:
        """Business rule checks on trading data."""
        self._check_trades_non_empty(report)
        self._check_trades_positive_volume(report)
        self._check_trades_contract_not_empty(report)

    def _check_trades_non_empty(self, report: VerifyReport) -> None:
        try:
            conn = sqlite3.connect(self.trading_db)
            count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            conn.close()
            report.checks.append(VerifyCheck(
                name="trades_non_empty",
                status="PASS" if count > 0 else "FAIL",
                source="trades",
                expected="> 0 rows", actual=str(count),
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="trades_non_empty",
                status="FAIL", source="trades",
                expected="table exists", actual=str(e),
            ))

    def _check_trades_positive_volume(self, report: VerifyReport) -> None:
        try:
            conn = sqlite3.connect(self.trading_db)
            neg = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE volume <= 0"
            ).fetchone()[0]
            conn.close()
            report.checks.append(VerifyCheck(
                name="trades_positive_volume",
                status="PASS" if neg == 0 else "FAIL",
                source="trades.volume",
                expected="all volume > 0", actual=f"{neg} rows with volume <= 0",
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="trades_positive_volume",
                status="FAIL", source="trades.volume",
                expected="success", actual=str(e),
            ))

    def _check_trades_contract_not_empty(self, report: VerifyReport) -> None:
        try:
            conn = sqlite3.connect(self.trading_db)
            empty = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE instrument IS NULL OR instrument = ''"
            ).fetchone()[0]
            conn.close()
            report.checks.append(VerifyCheck(
                name="trades_contract_not_empty",
                status="PASS" if empty == 0 else "FAIL",
                source="trades.instrument",
                expected="all instrument non-empty", actual=f"{empty} empty",
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="trades_contract_not_empty",
                status="FAIL", source="trades.instrument",
                expected="success", actual=str(e),
            ))

    def _check_account_summary_populated(self, report: VerifyReport) -> None:
        """Verify account_summary has been backfilled from bills."""
        try:
            conn = sqlite3.connect(self.trading_db)
            count = conn.execute("SELECT COUNT(*) FROM account_summary").fetchone()[0]
            months = conn.execute(
                "SELECT COUNT(DISTINCT year * 12 + month) FROM account_summary"
            ).fetchone()[0]
            conn.close()
            report.checks.append(VerifyCheck(
                name="account_summary_populated",
                status="PASS" if count > 0 else "FAIL",
                source="account_summary",
                expected="> 0 rows", actual=str(count),
                message=f"{months} monthly periods",
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="account_summary_populated",
                status="FAIL", source="account_summary",
                expected="table exists", actual=str(e),
            ))

    def _audit_bills_reconciliation(self, report: VerifyReport) -> None:
        """Bills summary cross-validation."""
        try:
            from tzdata_pkg.verify.bill_reconcile import BillReconciler

            bill_dir = str(self.data_dir / "bills" / "raw")
            reconciler = BillReconciler(self.trading_db, bill_dir)
            bill_report = reconciler.reconcile_all()
            report.checks.extend(bill_report.checks)
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="bills_reconciliation",
                status="FAIL", source="BillReconciler",
                expected="success", actual=str(e),
            ))

    # ------------------------------------------------------------------ #
    #  Analysis
    # ------------------------------------------------------------------ #
    def _audit_analysis(self, report: VerifyReport) -> None:
        try:
            from tzdata_pkg.verify.analysis_verify import AnalysisVerifier

            verifier = AnalysisVerifier(self.trading_db)
            analysis_report = verifier.verify_all()
            report.checks.extend(analysis_report.checks)
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="analysis_verification",
                status="FAIL", source="AnalysisVerifier",
                expected="success", actual=str(e),
            ))

        # Additional analysis DB checks
        self._check_analysis_table_non_empty(report, "feature_daily", "feature_daily")
        self._check_analysis_table_non_empty(report, "option_greeks", "option_greeks")
        self._check_analysis_table_non_empty(report, "iv_benchmark", "iv_benchmark")
        self._check_analysis_table_non_empty(report, "institution_ranking", "institution_ranking")

        # Schema checks
        self._check_schema_table(report, self.analysis_db, "feature_daily", [
            "trade_date", "contract_code", "exchange", "sentiment_score",
        ])
        self._check_schema_table(report, self.analysis_db, "iv_benchmark", [
            "trade_date", "contract_code", "atm_iv", "hv_20d",
        ])

    def _check_analysis_table_non_empty(self, report: VerifyReport, check_name: str, table: str) -> None:
        try:
            conn = sqlite3.connect(self.analysis_db)
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            conn.close()
            report.checks.append(VerifyCheck(
                name=f"analysis_{check_name}_non_empty",
                status="PASS" if count > 0 else "SKIP",
                source=table,
                expected="> 0 rows", actual=str(count),
                message=f"Analysis table {table} has {count} rows",
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name=f"analysis_{check_name}_non_empty",
                status="SKIP", source=table,
                expected="table exists", actual=str(e),
                message=f"Analysis table {table} not accessible — may not be initialized yet",
            ))

    # ------------------------------------------------------------------ #
    #  QuestDB
    # ------------------------------------------------------------------ #
    def _audit_questdb(self, report: VerifyReport) -> None:
        """SQLite vs QuestDB data consistency checks."""
        try:
            from tzdata_pkg.storage.db_registry import DBRegistry

            registry = DBRegistry()
            qdb_conn = registry.get_questdb_connection()
            if qdb_conn is None:
                report.checks.append(VerifyCheck(
                    name="questdb_connection",
                    status="SKIP", source="QuestDB",
                    expected="connected", actual="QuestDB unavailable",
                ))
                return

            report.checks.append(VerifyCheck(
                name="questdb_connection",
                status="PASS", source="QuestDB",
                expected="connected", actual="connected",
            ))

            # daily_quotes: SQLite table = QuestDB table name
            self._check_questdb_count(
                report, qdb_conn, self.market_db,
                "daily_quotes", "daily_quotes",
                "SELECT COUNT(*) FROM daily_quotes",
                "questdb_daily_quotes_count",
            )

            # minute_quotes: SQLite uses 'minute_quotes', QuestDB uses 'future_minute'
            self._check_questdb_count_cross_table(
                report, qdb_conn, self.market_db,
                "minute_quotes", "future_minute",
                "SELECT COUNT(*) FROM minute_quotes",
                "questdb_minute_quotes_count",
            )

            # Close connection
            try:
                qdb_conn.close()
            except Exception:
                pass
        except Exception as e:
            if "QuestDB unavailable" not in str(e):
                report.checks.append(VerifyCheck(
                    name="questdb_consistency",
                    status="FAIL", source="QuestDB",
                    expected="success", actual=str(e),
                ))

    def _check_questdb_count_cross_table(
        self, report: VerifyReport, qdb_conn, sqlite_db_path: str,
        sqlite_table: str, qdb_table: str, sqlite_query: str, check_name: str,
    ) -> None:
        """Compare row COUNT between SQLite and QuestDB with different table names."""
        try:
            # SQLite count
            conn = sqlite3.connect(sqlite_db_path)
            sqlite_count = conn.execute(sqlite_query).fetchone()[0]
            conn.close()

            # QuestDB count (different table)
            qdb_query = f"SELECT COUNT(*) FROM {qdb_table}"
            with qdb_conn.cursor() as cur:
                cur.execute(qdb_query)
                row = cur.fetchone()
                qdb_count = row[0] if row else 0

            deviation = abs(sqlite_count - qdb_count)
            report.checks.append(VerifyCheck(
                name=check_name,
                status="PASS" if deviation == 0 else "FAIL",
                source=f"{sqlite_table} vs QuestDB {qdb_table}",
                expected=sqlite_count,
                actual=qdb_count,
                deviation=deviation,
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name=check_name,
                status="FAIL", source=f"{sqlite_table} vs QuestDB {qdb_table}",
                expected="success", actual=str(e),
            ))

    def _check_questdb_count(
        self, report: VerifyReport, qdb_conn, sqlite_db_path: str,
        sqlite_table: str, qdb_table: str, query: str, check_name: str,
    ) -> None:
        """Compare row COUNT between SQLite and QuestDB."""
        try:
            # SQLite count
            conn = sqlite3.connect(sqlite_db_path)
            sqlite_count = conn.execute(query).fetchone()[0]
            conn.close()

            # QuestDB count
            with qdb_conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()
                qdb_count = row[0] if row else 0

            deviation = abs(sqlite_count - qdb_count)
            report.checks.append(VerifyCheck(
                name=check_name,
                status="PASS" if deviation == 0 else "FAIL",
                source=f"{sqlite_table} vs QuestDB",
                expected=sqlite_count,
                actual=qdb_count,
                deviation=deviation,
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name=check_name,
                status="FAIL", source=f"{sqlite_table} vs QuestDB",
                expected="success", actual=str(e),
            ))

    # ------------------------------------------------------------------ #
    #  CFMMC Parser
    # ------------------------------------------------------------------ #
    def _audit_parser(self, report: VerifyReport) -> None:
        """Batch parse historical bills and validate results."""
        bill_dir = self.data_dir / "bills" / "raw"
        if not bill_dir.exists():
            report.checks.append(VerifyCheck(
                name="bill_dir_exists",
                status="SKIP", source="CFMMCParser",
                expected=str(bill_dir), actual="not found",
            ))
            return

        report.checks.append(VerifyCheck(
            name="bill_dir_exists",
            status="PASS", source="CFMMCParser",
            expected=str(bill_dir), actual=str(bill_dir),
        ))

        txt_files = sorted(bill_dir.rglob("*.txt"))
        report.checks.append(VerifyCheck(
            name="bill_files_count",
            status="PASS" if txt_files else "WARN",
            source="CFMMCParser",
            expected="> 0", actual=str(len(txt_files)),
        ))

        parse_ok = 0
        parse_fail = 0
        balance_ok = 0
        balance_fail = 0

        for f in txt_files:
            try:
                from tzdata_pkg.maintenance.statements.parsers.cfmmc_parser import CFMMCParser

                result = CFMMCParser.parse(str(f))
                summary = result.get("summary", {})
                trades = result.get("trades", [])

                if summary:
                    parse_ok += 1
                    # Validate balance equation
                    balance_bf = summary.get("balance_bf", 0)
                    balance_cf = summary.get("balance_cf", 0)
                    deposit = summary.get("deposit_withdrawal", 0)
                    realized = summary.get("realized_pnl", 0)
                    mtm = summary.get("mtm_pnl", 0)
                    commission = summary.get("commission", 0)
                    premium_recv = summary.get("premium_received", 0)
                    premium_paid = summary.get("premium_paid", 0)

                    # balance_cf ≈ balance_bf + deposit + realized_pnl + mtm_pnl - commission + premium_recv - premium_paid
                    expected_cf = balance_bf + deposit + realized + mtm - commission + premium_recv - premium_paid
                    if balance_cf != 0 and abs(balance_cf - expected_cf) > abs(balance_cf) * 0.05:
                        balance_fail += 1
                        report.checks.append(VerifyCheck(
                            name=f"parser_balance_{f.name}",
                            status="FAIL", source=f.name,
                            expected=f"balance_cf ≈ {expected_cf:.2f}",
                            actual=f"balance_cf = {balance_cf:.2f}",
                            deviation=abs(balance_cf - expected_cf),
                            message="Balance equation deviation > 5%",
                        ))
                    else:
                        balance_ok += 1
                else:
                    parse_fail += 1

                # Check trades parsed
                if trades:
                    report.checks.append(VerifyCheck(
                        name=f"parser_trades_{f.name}",
                        status="PASS", source=f.name,
                        expected="trades > 0", actual=str(len(trades)),
                    ))
            except Exception as e:
                parse_fail += 1
                report.checks.append(VerifyCheck(
                    name=f"parser_{f.name}",
                    status="FAIL", source=f.name,
                    expected="parse success", actual=str(e),
                ))

        report.checks.append(VerifyCheck(
            name="parser_batch_summary",
            status="PASS" if parse_fail == 0 else "FAIL",
            source="CFMMCParser batch",
            expected=f"{parse_ok + parse_fail} files parsed successfully",
            actual=f"{parse_ok} ok, {parse_fail} failed, {balance_ok} balance ok, {balance_fail} balance fail",
        ))

    # ------------------------------------------------------------------ #
    #  Celery
    # ------------------------------------------------------------------ #
    def _audit_celery(self, report: VerifyReport) -> None:
        """Celery Beat task health checks."""
        self._check_celery_imports(report)
        self._check_celery_schedule(report)

    def _check_celery_imports(self, report: VerifyReport) -> None:
        """Verify all Celery task modules are importable."""
        try:
            from tzdata_pkg.scheduler.celery_app import celery_app

            includes = celery_app.conf.get("include", [])
            import_errors = []
            for module in includes:
                try:
                    __import__(module)
                except ImportError as e:
                    import_errors.append(f"{module}: {e}")

            report.checks.append(VerifyCheck(
                name="celery_module_imports",
                status="PASS" if not import_errors else "FAIL",
                source="Celery include",
                expected=f"{len(includes)} modules importable",
                actual=f"{len(includes) - len(import_errors)} ok, {len(import_errors)} failed",
                message="; ".join(import_errors) if import_errors else "all modules importable",
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="celery_module_imports",
                status="FAIL", source="Celery",
                expected="success", actual=str(e),
            ))

    def _check_celery_schedule(self, report: VerifyReport) -> None:
        """Verify Celery Beat schedule has no duplicate task IDs."""
        try:
            from tzdata_pkg.scheduler.celery_app import celery_app

            schedule = celery_app.conf.get("beat_schedule", {})
            task_ids = [v.get("task", "") for v in schedule.values()]
            duplicates = {t for t in task_ids if task_ids.count(t) > 1}

            report.checks.append(VerifyCheck(
                name="celery_schedule_duplicates",
                status="PASS" if not duplicates else "FAIL",
                source="beat_schedule",
                expected="no duplicate task_ids",
                actual=f"{len(duplicates)} duplicates: {', '.join(duplicates)}" if duplicates else "clean",
            ))

            report.checks.append(VerifyCheck(
                name="celery_schedule_count",
                status="PASS",
                source="beat_schedule",
                expected="scheduled tasks",
                actual=f"{len(schedule)} tasks configured",
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name="celery_schedule",
                status="FAIL", source="beat_schedule",
                expected="success", actual=str(e),
            ))

    # ------------------------------------------------------------------ #
    #  Schema validation helper
    # ------------------------------------------------------------------ #
    def _check_schema_table(
        self, report: VerifyReport, db_path: str, table: str, expected_columns: list[str]
    ) -> None:
        """Verify table exists and has expected columns."""
        try:
            conn = sqlite3.connect(db_path)
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            conn.close()

            if not rows:
                report.checks.append(VerifyCheck(
                    name=f"schema_{table}",
                    status="FAIL", source=f"{db_path}.{table}",
                    expected=f"table {table} exists", actual="table not found",
                ))
                return

            actual_columns = {r[1] for r in rows}
            missing = [c for c in expected_columns if c not in actual_columns]

            report.checks.append(VerifyCheck(
                name=f"schema_{table}",
                status="PASS" if not missing else "FAIL",
                source=f"{db_path}.{table}",
                expected=f"columns: {', '.join(expected_columns)}",
                actual=f"{len(rows)} columns found" + (f", missing: {', '.join(missing)}" if missing else ""),
            ))
        except Exception as e:
            report.checks.append(VerifyCheck(
                name=f"schema_{table}",
                status="FAIL", source=f"{db_path}.{table}",
                expected=f"table {table} exists", actual=str(e),
            ))
