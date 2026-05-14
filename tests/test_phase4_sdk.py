"""Tests for Phase 4: Python SDK, Scheduler, and CLI."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date


# ── Python SDK tests ────────────────────────────────────────

class TestTzDataClient:
    """Test the main TzDataClient."""

    def test_import(self):
        from tzdata_pkg.query import TzDataClient
        assert TzDataClient is not None

    def test_create_client(self):
        from tzdata_pkg.query import TzDataClient
        client = TzDataClient()
        assert client is not None
        client.close()

    def test_client_has_market_accessors(self):
        from tzdata_pkg.query import TzDataClient
        client = TzDataClient()
        assert callable(client.quotes)
        assert callable(client.positions)
        assert callable(client.contracts)
        assert callable(client.top_holders)
        assert callable(client.quote_summary)
        client.close()

    def test_client_has_trading_accessors(self):
        from tzdata_pkg.query import TzDataClient
        client = TzDataClient()
        assert callable(client.bills)
        assert callable(client.trades)
        assert callable(client.matched_trades)
        assert callable(client.positions_summary)
        assert callable(client.account_summary)
        assert callable(client.pnl_summary)
        client.close()

    def test_client_has_analysis_accessors(self):
        from tzdata_pkg.query import TzDataClient
        client = TzDataClient()
        assert callable(client.institution_features)
        assert callable(client.signals)
        assert callable(client.market_regime)
        assert callable(client.tushare_daily)
        assert callable(client.option_features)
        assert callable(client.iv_snapshot)
        client.close()

    def test_client_context_manager(self):
        from tzdata_pkg.query import TzDataClient
        with TzDataClient() as client:
            assert client.quotes is not None

    def test_client_status(self):
        from tzdata_pkg.query import TzDataClient
        client = TzDataClient()
        status = client.status()
        assert "databases" in status
        assert "market" in status["databases"]
        assert "trading" in status["databases"]
        assert "analysis" in status["databases"]
        client.close()


class TestMarketQuery:
    """Test MarketQuery module."""

    def test_import(self):
        from tzdata_pkg.query.market import MarketQuery
        assert MarketQuery is not None

    def test_query_methods_exist(self):
        from tzdata_pkg.query import TzDataClient
        with TzDataClient() as client:
            # Should return empty list, not error
            quotes = client.quotes(exchange="CFFEX")
            assert isinstance(quotes, list)


class TestTradingQuery:
    """Test TradingQuery module."""

    def test_import(self):
        from tzdata_pkg.query.trading import TradingQuery
        assert TradingQuery is not None

    def test_pnl_summary_empty(self):
        from tzdata_pkg.query import TzDataClient
        with TzDataClient() as client:
            result = client.pnl_summary()
            assert isinstance(result, dict)
            assert "trade_count" in result


class TestAnalysisQuery:
    """Test AnalysisQuery module."""

    def test_import(self):
        from tzdata_pkg.query.analysis import AnalysisQuery
        assert AnalysisQuery is not None


# ── Scheduler tests ─────────────────────────────────────────

class TestTzDataScheduler:
    """Test the scheduler module."""

    def test_import(self):
        from tzdata_pkg.scheduler import TzDataScheduler
        assert TzDataScheduler is not None

    def test_create_scheduler(self):
        from tzdata_pkg.scheduler import TzDataScheduler
        scheduler = TzDataScheduler(mode="blocking")
        assert scheduler is not None
        try:
            scheduler.shutdown()
        except Exception:
            pass

    def test_default_jobs(self):
        from tzdata_pkg.scheduler import TzDataScheduler
        assert len(TzDataScheduler.DEFAULT_JOBS) == 5
        job_names = [j["name"] for j in TzDataScheduler.DEFAULT_JOBS]
        assert "cffex_daily" in job_names
        assert "cffex_position" in job_names
        assert "shfe_daily" in job_names
        assert "cfmmc_bills" in job_names
        assert "data_quality" in job_names

    def test_get_jobs(self):
        from tzdata_pkg.scheduler import TzDataScheduler
        scheduler = TzDataScheduler(mode="blocking")
        jobs = scheduler.get_jobs()
        assert len(jobs) == 5
        for job in jobs:
            assert "id" in job
            assert "name" in job
            assert "trigger" in job
        try:
            scheduler.shutdown()
        except Exception:
            pass

    def test_custom_jobs(self):
        from tzdata_pkg.scheduler import TzDataScheduler
        # Only schedule one job
        custom_jobs = [TzDataScheduler.DEFAULT_JOBS[0]]
        scheduler = TzDataScheduler(mode="blocking", jobs=custom_jobs)
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0]["name"] == "cffex_daily"
        try:
            scheduler.shutdown()
        except Exception:
            pass

    def test_run_unknown_job(self):
        from tzdata_pkg.scheduler import TzDataScheduler
        scheduler = TzDataScheduler(mode="blocking")
        with pytest.raises(ValueError, match="not found"):
            scheduler.run_now("nonexistent_job")
        try:
            scheduler.shutdown()
        except Exception:
            pass


# ── CLI tests ──────────────────────────────────────────────

class TestCLI:
    """Test CLI commands."""

    def test_cli_import(self):
        from tzdata_pkg.__main__ import cli
        assert cli is not None

    def test_cli_version(self):
        from click.testing import CliRunner
        from tzdata_pkg.__main__ import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "tzdata" in result.output

    def test_cli_status(self):
        from click.testing import CliRunner
        from tzdata_pkg.__main__ import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Market Data" in result.output or "Database not yet created" in result.output

    def test_cli_validate(self):
        from click.testing import CliRunner
        from tzdata_pkg.__main__ import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["validate"])
        assert result.exit_code == 0
        assert "data quality" in result.output.lower()

    def test_cli_download_help(self):
        from click.testing import CliRunner
        from tzdata_pkg.__main__ import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["download", "--help"])
        assert result.exit_code == 0
        assert "cffex" in result.output
        assert "shfe" in result.output
        assert "tushare" in result.output
        assert "cfmmc" in result.output

    def test_cli_query_help(self):
        from click.testing import CliRunner
        from tzdata_pkg.__main__ import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["query", "--help"])
        assert result.exit_code == 0
        assert "quotes" in result.output
        assert "positions" in result.output
        assert "bills" in result.output
        assert "pnl" in result.output

    def test_cli_schedule_help(self):
        from click.testing import CliRunner
        from tzdata_pkg.__main__ import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["schedule", "--help"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "run" in result.output
        assert "list" in result.output
