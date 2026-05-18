"""
CLI entry point for QuestDB migration.

Usage:
    python -m tzdata_pkg.cli.migrate_questdb dry-run    # Preview counts
    python -m tzdata_pkg.cli.migrate_questdb run        # Execute migration
    python -m tzdata_pkg.cli.migrate_questdb verify     # Verify consistency
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

if __name__ == "__main__":
    # Import from migrations module
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "migrations"))
    from sqlite_to_questdb import dry_run, run_migration, verify

    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "dry-run":
        dry_run()
    elif cmd == "run":
        run_migration()
    elif cmd == "verify":
        verify()
    else:
        print("Usage: python -m tzdata_pkg.cli.migrate_questdb {dry-run|run|verify}")
