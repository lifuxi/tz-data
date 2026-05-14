"""TDD tests for Phase 3 API endpoint existence (smoke tests)."""

import pytest
import sqlite3
from fastapi.testclient import TestClient

from tzdata_pkg.api.server import app


@pytest.fixture
def client():
    """TestClient with test_if trading hours template seeded."""
    # Seed a minimal trading hours template so endpoints return data
    from tzdata_pkg.core.db import SQLitePool
    from tzdata_pkg.storage.db_registry import DBRegistry
    pool = DBRegistry().get_pool('market')
    try:
        with pool.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO trading_hours_template
                    (template_id, template_name, exchange_code, product_type,
                     normal_schedule, night_schedule, pre_open, pre_close, is_default)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "test_if", "Test IF Template", "CFFEX", "IF",
                '[{"start": "09:30", "end": "11:30"}, {"start": "13:00", "end": "15:00"}]',
                None, None, None, 0
            ))
    except Exception:
        pass  # Template may already exist from previous test run

    return TestClient(app)


class TestPhase3APISmoke:
    """Smoke tests verifying Phase 3 API endpoints exist and respond."""

    def test_main_contract_endpoint_exists(self, client):
        """GET /main-contract/{product_code} endpoint exists."""
        resp = client.get(
            "/api/maintenance/main-contract/IM",
            params={"date": "2026-01-15"}
        )
        # 200 (found) or 500 (DB error) both mean endpoint exists
        assert resp.status_code != 404

    def test_main_contract_series_endpoint_exists(self, client):
        """GET /main-contract/{product_code}/series endpoint exists."""
        resp = client.get(
            "/api/maintenance/main-contract/IM/series",
            params={"start_date": "2026-01-01", "end_date": "2026-12-31"}
        )
        assert resp.status_code != 404

    def test_main_contract_rollovers_endpoint_exists(self, client):
        """GET /main-contract/{product_code}/rollovers endpoint exists."""
        resp = client.get(
            "/api/maintenance/main-contract/IM/rollovers",
            params={"start_date": "2026-01-01", "end_date": "2026-12-31"}
        )
        assert resp.status_code != 404

    def test_trading_hours_endpoint_exists(self, client):
        """GET /trading-hours/{template_id} endpoint exists."""
        resp = client.get("/api/maintenance/trading-hours/test_if")
        assert resp.status_code != 404

    def test_trading_hours_sessions_endpoint_exists(self, client):
        """GET /trading-hours/{template_id}/sessions endpoint exists."""
        resp = client.get("/api/maintenance/trading-hours/test_if/sessions")
        assert resp.status_code != 404

    def test_check_trading_time_endpoint_exists(self, client):
        """GET /trading-hours/is-trading-time endpoint exists."""
        resp = client.get(
            "/api/maintenance/trading-hours/is-trading-time",
            params={"template_id": "test_if", "time_str": "10:00"}
        )
        assert resp.status_code != 404
