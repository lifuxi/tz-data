"""CLI entry point for schema migration verification.

Usage:
    python -m tzdata_pkg.cli.verify_schema
"""
import sys
from pathlib import Path

# Add src to path for package imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(PROJECT_ROOT.parent / "data" / "tzdata_trading.db")

    from tzdata_pkg.migrations.verify_schema_alignment import verify_alignment, print_report

    report = verify_alignment(db_path)
    print_report(report)

    if report["tables_with_issues"] or report["tables_missing"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
