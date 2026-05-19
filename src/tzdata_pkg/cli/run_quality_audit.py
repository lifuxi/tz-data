"""CLI entry point for data quality audit.

Usage:
    python -m tzdata_pkg.cli.run_quality_audit              # Full audit
    python -m tzdata_pkg.cli.run_quality_audit --scope market
    python -m tzdata_pkg.cli.run_quality_audit --scope trading
    python -m tzdata_pkg.cli.run_quality_audit --scope questdb
    python -m tzdata_pkg.cli.run_quality_audit --scope parser
    python -m tzdata_pkg.cli.run_quality_audit --scope celery
    python -m tzdata_pkg.cli.run_quality_audit --output report.json
"""
import sys
import json
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def print_report(report):
    """Print audit report in a formatted table."""
    # Summary counts by category
    categories = {
        "market": [],
        "trading": [],
        "analysis": [],
        "questdb": [],
        "parser": [],
        "celery": [],
    }

    for c in report.checks:
        name = c.name.lower()
        if "market" in name or "completeness" in name or "anomal" in name or "schema_daily" in name or "schema_minute" in name or "schema_data_catalog" in name:
            categories["market"].append(c)
        elif "trading" in name or "trades" in name or "matched" in name or "bills" in name or "schema_bills" in name or "schema_account" in name:
            categories["trading"].append(c)
        elif "analysis" in name or "feature" in name or "option_greeks" in name or "iv_benchmark" in name or "institution" in name:
            categories["analysis"].append(c)
        elif "questdb" in name:
            categories["questdb"].append(c)
        elif "parser" in name or "bill_" in name or "fund_balance" in name or "pnl" in name or "fee" in name or "pair" in name or "bill_dir" in name or "bill_file" in name:
            categories["parser"].append(c)
        elif "celery" in name:
            categories["celery"].append(c)
        else:
            # Assign to most relevant category based on source
            src = c.source.lower()
            if "questdb" in src:
                categories["questdb"].append(c)
            elif "celery" in src or "beat" in src:
                categories["celery"].append(c)
            elif "parser" in src or "cfmmc" in src or "bill" in src:
                categories["parser"].append(c)
            elif "analysis" in src or "feature" in src or "iv" in src:
                categories["analysis"].append(c)
            elif "trading" in src or "trades" in src or "bills.db" in src or "matched" in src:
                categories["trading"].append(c)
            else:
                categories["market"].append(c)

    label_map = {
        "market": "Market",
        "trading": "Trading",
        "analysis": "Analysis",
        "questdb": "QuestDB",
        "parser": "Parser",
        "celery": "Celery",
    }

    width = 80
    print("=" * width)
    print("       tz-data Data Quality Audit Report".center(width))
    print("=" * width)
    print(f" Timestamp : {report.timestamp}")
    print(f" Overall   : {report.overall_status}  (PASS={report.passed} FAIL={report.failed} WARN={report.warnings} SKIP={report.skipped})")
    print("-" * width)
    print(f" {'Category':<14} │ {'PASS':>5} {'FAIL':>5} {'WARN':>5} {'SKIP':>5}")
    print("-" * width)

    for cat_key, checks in categories.items():
        p = sum(1 for c in checks if c.status == "PASS")
        f = sum(1 for c in checks if c.status == "FAIL")
        w = sum(1 for c in checks if c.status == "WARN")
        s = sum(1 for c in checks if c.status == "SKIP")
        print(f" {label_map[cat_key]:<14} │ {p:>5} {f:>5} {w:>5} {s:>5}")

    print("=" * width)

    # Print FAIL and WARN details
    failures = [c for c in report.checks if c.status in ("FAIL", "WARN")]
    if failures:
        print(f"\n FAIL / WARN details ({len(failures)} items):")
        print("-" * width)
        for c in failures:
            marker = "!!" if c.status == "FAIL" else "??"
            msg = f" ({c.message})" if c.message else ""
            print(f"  [{marker}] {c.name}: {c.source} — expected={c.expected}, actual={c.actual}{msg}")
        print()
    else:
        print("\n All checks passed.")

    # Print skips
    skipped = [c for c in report.checks if c.status == "SKIP"]
    if skipped:
        print(f"\n Skipped ({len(skipped)} items):")
        for c in skipped:
            print(f"  [--] {c.name}: {c.message or c.actual}")


def main():
    parser = argparse.ArgumentParser(description="Run data quality audit")
    parser.add_argument("--scope", default="all",
                        choices=["all", "market", "trading", "analysis", "questdb", "parser", "celery"],
                        help="Audit scope (default: all)")
    parser.add_argument("--output", default=None,
                        help="Output JSON file path")
    parser.add_argument("--data-dir", default=None,
                        help="Data directory path")
    args = parser.parse_args()

    from tzdata_pkg.verify.data_quality_auditor import DataQualityAuditor

    auditor = DataQualityAuditor(data_dir=args.data_dir)
    report = auditor.run_full_audit(scope=args.scope)

    print_report(report)

    if args.output:
        output_path = Path(args.output)
        data = {
            "timestamp": report.timestamp,
            "overall_status": report.overall_status,
            "total_checks": report.total_checks,
            "passed": report.passed,
            "failed": report.failed,
            "warnings": report.warnings,
            "skipped": report.skipped,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "source": c.source,
                    "expected": c.expected,
                    "actual": c.actual,
                    "deviation": c.deviation,
                    "message": c.message,
                }
                for c in report.checks
            ],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON report saved to {output_path}")

    if report.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
