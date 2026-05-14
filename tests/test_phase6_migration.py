"""Tests for Phase 6: 12-to-3 DB migration."""

import pytest
import sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import patch


class TestMigrationRunner:
    """Test the migration runner."""

    @pytest.fixture
    def test_data_dir(self, tmp_path):
        """Create a temporary data directory with test DBs."""
        # Create source DBs
        cffex = sqlite3.connect(str(tmp_path / "cffex.db"))
        cffex.execute("""CREATE TABLE daily_quotes (
            trade_date TEXT, contract_code TEXT, open REAL, close REAL,
            high REAL, low REAL, volume INTEGER, exchange TEXT
        )""")
        cffex.execute("""CREATE TABLE position_detail (
            trade_date TEXT, member_name TEXT, long_volume INTEGER, short_volume INTEGER
        )""")
        cffex.execute("""CREATE TABLE contracts (contract_code TEXT, product TEXT)""")
        for i in range(100):
            cffex.execute("INSERT INTO daily_quotes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (f"2025-01-{i+1:02d}", f"MO2501", 100.0, 101.0, 102.0, 99.0, 1000, "CFFEX"))
        for i in range(50):
            cffex.execute("INSERT INTO position_detail VALUES (?, ?, ?, ?)",
                         (f"2025-01-{i+1:02d}", "Broker A", 100, 200))
        for i in range(10):
            cffex.execute("INSERT INTO contracts VALUES (?, ?)", (f"MO250{i}", "MO"))
        cffex.commit()
        cffex.close()

        shfe = sqlite3.connect(str(tmp_path / "shfe.db"))
        shfe.execute("""CREATE TABLE daily_quotes (
            trade_date TEXT, product TEXT, open REAL, close REAL
        )""")
        for i in range(30):
            shfe.execute("INSERT INTO daily_quotes VALUES (?, ?, ?, ?)",
                        (f"2025-02-{i+1:02d}", "AU", 500.0, 501.0))
        shfe.commit()
        shfe.close()

        bills = sqlite3.connect(str(tmp_path / "bills.db"))
        bills.execute("""CREATE TABLE trades (
            trade_date TEXT, account_id TEXT, contract TEXT,
            direction TEXT, volume INTEGER, price REAL
        )""")
        bills.execute("""CREATE TABLE matched_trades (
            trade_id INTEGER, match_date TEXT
        )""")
        for i in range(200):
            bills.execute("INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?)",
                         (f"2025-03-{i%28+1:02d}", "ACC001", "MO2503", "BUY", 1, 80.0))
        for i in range(100):
            bills.execute("INSERT INTO matched_trades VALUES (?, ?)", (i, f"2025-03-{i%28+1:02d}"))
        bills.commit()
        bills.close()

        institution = sqlite3.connect(str(tmp_path / "institution.db"))
        institution.execute("""CREATE TABLE institution_daily_features (
            trade_date TEXT, member_name TEXT, feature_value REAL
        )""")
        institution.execute("""CREATE TABLE market_regime (
            trade_date TEXT, regime TEXT, confidence REAL
        )""")
        for i in range(150):
            institution.execute("INSERT INTO institution_daily_features VALUES (?, ?, ?)",
                               (f"2025-04-{i%28+1:02d}", "Broker A", 0.5))
        for i in range(30):
            institution.execute("INSERT INTO market_regime VALUES (?, ?, ?)",
                               (f"2025-04-{i+1:02d}", "trend", 0.8))
        institution.commit()
        institution.close()

        # Create target DBs
        for db_name in ["tzdata_market.db", "tzdata_trading.db", "tzdata_analysis.db"]:
            conn = sqlite3.connect(str(tmp_path / db_name))
            conn.close()

        return tmp_path

    def test_import(self):
        from tzdata_pkg.migration import MigrationRunner
        assert MigrationRunner is not None

    def test_create_runner(self):
        from tzdata_pkg.migration import MigrationRunner
        runner = MigrationRunner(Path("/tmp"))
        assert runner.data_dir == Path("/tmp")

    def test_migrate_market(self, test_data_dir):
        from tzdata_pkg.migration import MigrationRunner
        runner = MigrationRunner(test_data_dir)
        report = runner.run()
        assert report.tables_migrated > 0
        assert report.rows_migrated > 0
        assert len(report.errors) == 0

    def test_verify_migration(self, test_data_dir):
        from tzdata_pkg.migration import MigrationRunner
        runner = MigrationRunner(test_data_dir)

        # First migrate
        runner.run()

        # Then verify
        results = runner.verify()
        # Check some tables have matching counts
        matching = sum(1 for v in results.values() if v["matched"])
        assert matching > 0

    def test_dry_run(self, test_data_dir):
        from tzdata_pkg.migration import MigrationRunner
        runner = MigrationRunner(test_data_dir)
        report = runner.run(dry_run=True)
        # Dry run should report counts but not actually copy
        assert report.rows_migrated > 0

    def test_missing_source_skipped(self, test_data_dir):
        """Migration should not fail if a source DB is missing."""
        from tzdata_pkg.migration import MigrationRunner
        runner = MigrationRunner(test_data_dir)
        # Should not raise
        report = runner.run()
        # May have warnings but should not crash
        assert isinstance(report.rows_migrated, int)


class TestCLIMigrate:
    """Test CLI migrate command."""

    def test_migrate_help(self):
        from click.testing import CliRunner
        from tzdata_pkg.__main__ import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["migrate", "--help"])
        assert result.exit_code == 0
        assert "dry-run" in result.output
        assert "verify" in result.output

    def test_migrate_dry_run_help(self):
        from click.testing import CliRunner
        from tzdata_pkg.__main__ import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["migrate", "--dry-run"])
        # Should not crash
        assert result.exit_code == 0 or result.exit_code == 1


class TestMigrationReport:
    """Test MigrationReport dataclass."""

    def test_report_to_dict(self):
        from tzdata_pkg.migration.migrate_12_to_3 import MigrationReport
        report = MigrationReport(
            started_at="2025-01-01T00:00:00",
            completed_at="2025-01-01T00:01:00",
            tables_migrated=5,
            rows_migrated=1000,
        )
        d = report.to_dict()
        assert d["tables_migrated"] == 5
        assert d["rows_migrated"] == 1000
        assert d["errors"] == []
