"""Admin routes: status, health check, and data verification."""
import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks

from tzdata_pkg.query import TzDataClient

router = APIRouter()

# In-memory cache for last verification result
_last_verify_report: dict = {}
_verify_in_progress = False


@router.get("/status", summary="系统状态", description="获取系统完整状态：数据库统计、表行数等")
def get_status():
    """Full system status: DB stats, table counts."""
    with TzDataClient() as client:
        status = client.status()
    return status


@router.get("/health", summary="健康检查", description="简单的健康检查接口")
def health_check():
    """Simple health check."""
    return {"status": "ok", "version": "0.3.0"}


@router.get("/verify/report", summary="校验报告", description="获取最后一次数据校验报告")
def get_verify_report():
    """Get the last verification report."""
    if not _last_verify_report:
        return {"status": "no_report", "message": "No verification has been run yet"}
    return _last_verify_report


@router.post("/verify/run", summary="触发数据校验", description="触发一次完整的数据校验流程（后台异步执行）")
async def run_verify(background_tasks: BackgroundTasks):
    """Trigger a full verification run."""
    global _verify_in_progress
    if _verify_in_progress:
        return {"status": "already_running", "message": "Verification is already in progress"}

    _verify_in_progress = True
    background_tasks.add_task(_run_verification)
    return {"status": "started", "message": "Verification started in background"}


def _run_verification():
    """Run all verification checks and cache the result."""
    global _verify_in_progress, _last_verify_report

    try:
        from tzdata_pkg.config import BILLS_DB, TZDATA_TRADING_DB, DATA_DIR
        from tzdata_pkg.verify import BillReconciler, CrossDBChecker, AnalysisVerifier

        reconciler = BillReconciler(bills_db_path=str(BILLS_DB), bill_dir=str(DATA_DIR / "bills" / "raw"))
        bill_report = reconciler.reconcile_all()

        checker = CrossDBChecker(bills_db_path=str(BILLS_DB), trading_db_path=str(TZDATA_TRADING_DB))
        cross_report = checker.check_all()

        verifier = AnalysisVerifier(bills_db_path=str(BILLS_DB))
        analysis_report = verifier.verify_all()

        # Combine into single report
        total_pass = bill_report.passed + cross_report.passed + analysis_report.passed
        total_fail = bill_report.failed + cross_report.failed + analysis_report.failed
        total_warn = bill_report.warnings + cross_report.warnings + analysis_report.warnings
        total_all = bill_report.total_checks + cross_report.total_checks + analysis_report.total_checks

        overall = "UNRELIABLE" if total_fail > 0 else ("QUESTIONABLE" if total_warn > 0 else "TRUSTWORTHY")

        _last_verify_report = {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall,
            "summary": {
                "total_checks": total_all,
                "passed": total_pass,
                "failed": total_fail,
                "warnings": total_warn,
            },
            "sections": {
                "bill_reconciliation": {
                    "total": bill_report.total_checks,
                    "passed": bill_report.passed,
                    "failed": bill_report.failed,
                    "warnings": bill_report.warnings,
                    "checks": [_check_to_dict(c) for c in bill_report.checks],
                },
                "cross_db": {
                    "total": cross_report.total_checks,
                    "passed": cross_report.passed,
                    "failed": cross_report.failed,
                    "warnings": cross_report.warnings,
                    "checks": [_check_to_dict(c) for c in cross_report.checks],
                },
                "analysis": {
                    "total": analysis_report.total_checks,
                    "passed": analysis_report.passed,
                    "failed": analysis_report.failed,
                    "warnings": analysis_report.warnings,
                    "checks": [_check_to_dict(c) for c in analysis_report.checks],
                },
            },
        }
    except Exception as e:
        _last_verify_report = {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }
    finally:
        _verify_in_progress = False


def _check_to_dict(check) -> dict:
    return {
        "name": check.name,
        "status": check.status,
        "source": check.source,
        "expected": check.expected,
        "actual": check.actual,
        "deviation": check.deviation,
        "message": check.message,
    }
