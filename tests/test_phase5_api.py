"""Tests for Phase 5: FastAPI API service layer."""

import pytest
from fastapi.testclient import TestClient


class TestAPIServer:
    """Test the FastAPI application."""

    def test_import_app(self):
        from tzdata_pkg.api.server import app
        assert app is not None

    def test_app_title(self):
        from tzdata_pkg.api.server import app
        assert app.title == "tz-data API"


class TestAPIHealth:
    """Test health endpoints."""

    def test_health_check(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/admin/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "version" in data


class TestAPIMarket:
    """Test market data endpoints."""

    def test_quotes_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/market/quotes")
            assert resp.status_code == 200
            data = resp.json()
            assert "count" in data
            assert "data" in data

    def test_quotes_with_exchange(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/market/quotes", params={"exchange": "CFFEX"})
            assert resp.status_code == 200
            data = resp.json()
            assert "count" in data

    def test_contracts_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/market/contracts")
            assert resp.status_code == 200
            data = resp.json()
            assert "count" in data
            assert "data" in data


class TestAPIPositions:
    """Test position endpoints."""

    def test_positions_by_product(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/positions/MO")
            assert resp.status_code == 200
            data = resp.json()
            assert "count" in data
            assert "product" in data

    def test_top_holders(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/positions/MO/top-holders")
            assert resp.status_code == 200
            data = resp.json()
            assert "product" in data


class TestAPITrading:
    """Test trading endpoints."""

    def test_bills_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/bills")
            assert resp.status_code == 200
            data = resp.json()
            assert "count" in data
            assert "data" in data

    def test_trades_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/trades")
            assert resp.status_code == 200
            data = resp.json()
            assert "count" in data

    def test_pnl_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/pnl")
            assert resp.status_code == 200
            data = resp.json()
            assert "trade_count" in data


class TestAPIAnalysis:
    """Test analysis endpoints."""

    def test_signals_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/signals")
            assert resp.status_code == 200

    def test_regime_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/regime")
            assert resp.status_code == 200

    def test_institution_features_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/institution-features")
            assert resp.status_code == 200

    def test_option_features_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/option-features")
            assert resp.status_code == 200

    def test_iv_snapshot_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/iv-snapshot")
            assert resp.status_code == 200

    def test_tushare_daily_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/tushare-daily")
            assert resp.status_code == 200


class TestAPIAdmin:
    """Test admin endpoints."""

    def test_status_endpoint(self):
        from tzdata_pkg.api.server import app
        with TestClient(app) as client:
            resp = client.get("/api/v1/admin/status")
            assert resp.status_code == 200
            data = resp.json()
            assert "databases" in data


class TestCLIServe:
    """Test CLI serve command."""

    def test_serve_help(self):
        from click.testing import CliRunner
        from tzdata_pkg.__main__ import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "host" in result.output
        assert "port" in result.output
