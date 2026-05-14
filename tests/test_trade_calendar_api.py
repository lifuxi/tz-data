"""TDD tests for trade calendar DateQuery API endpoints"""

import pytest
from fastapi.testclient import TestClient

from tzdata_pkg.api.server import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


class TestDateQueryEndpoints:
    """Tests for the new date query API endpoints"""

    def test_next_trading_day_endpoint(self, client):
        """GET /trade-calendar/next-trading-day returns next trading day"""
        resp = client.get(
            "/api/maintenance/trade-calendar/next-trading-day",
            params={"date": "2026-01-05"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "next_trading_day" in data
        assert data["date"] == "2026-01-05"

    def test_next_trading_day_with_offset(self, client):
        """GET /trade-calendar/next-trading-day with n parameter"""
        resp = client.get(
            "/api/maintenance/trade-calendar/next-trading-day",
            params={"date": "2026-01-05", "n": 3}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["next_trading_day"] > "2026-01-05"

    def test_prev_trading_day_endpoint(self, client):
        """GET /trade-calendar/prev-trading-day returns prev trading day"""
        resp = client.get(
            "/api/maintenance/trade-calendar/prev-trading-day",
            params={"date": "2026-01-06"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "prev_trading_day" in data
        assert data["date"] == "2026-01-06"

    def test_trading_days_count_endpoint(self, client):
        """GET /trade-calendar/trading-days-count returns count"""
        resp = client.get(
            "/api/maintenance/trade-calendar/trading-days-count",
            params={"start_date": "2026-01-05", "end_date": "2026-01-09"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert data["count"] >= 1

    def test_is_trading_day_endpoint(self, client):
        """GET /trade-calendar/is-trading-day returns boolean"""
        resp = client.get(
            "/api/maintenance/trade-calendar/is-trading-day",
            params={"trade_date": "2026-01-05"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "is_trading_day" in data

    def test_date_query_invalid_date_format(self, client):
        """Invalid date format returns an error (404 from ValueError or 422/500)"""
        resp = client.get(
            "/api/maintenance/trade-calendar/next-trading-day",
            params={"date": "not-a-date"}
        )
        assert resp.status_code in (404, 422, 500)
