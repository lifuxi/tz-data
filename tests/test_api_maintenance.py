"""
API boundary tests for tz-data maintenance endpoints.

Tests edge cases, error handling, and data consistency for:
- /api/maintenance/catalogs (field completeness, filters)
- /api/maintenance/catalogs/{id} (404, invalid ID)
- /api/maintenance/health/diff (empty snapshots)
- /api/maintenance/trade-calendar endpoints (boundary dates)
- Sync task failure scenarios
- Reconciliation & gap detection edge cases
"""
import pytest
from datetime import date, datetime
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ============================================================
# 1. /api/maintenance/catalogs — field completeness & filters
# ============================================================

class TestCatalogEndpoints:

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_list_catalogs_returns_required_fields(self, mock_cm):
        """All returned catalogs must contain core fields."""
        mock_cm.list_catalogs.return_value = [
            {
                'id': 1,
                'catalog_name': 'Test-IM-Daily',
                'exchange_code': 'CFFEX',
                'product_code': 'IM',
                'contract_code': 'IM2506',
                'data_type': 'daily',
                'frequency': '1d',
                'data_source': 'tushare',
                'is_enabled': True,
                'sync_mode': 'incremental',
            }
        ]
        from tzdata_pkg.api.routes.maintenance import list_catalogs

        resp = list_catalogs()

        assert resp['success'] is True
        catalogs = resp['data']
        assert len(catalogs) == 1
        cat = catalogs[0]
        required = ['id', 'catalog_name', 'exchange_code', 'product_code', 'data_type', 'is_enabled']
        for field in required:
            assert field in cat, f"Missing required field: {field}"

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_list_catalogs_empty_result(self, mock_cm):
        """Empty catalog list should return success with empty data."""
        mock_cm.list_catalogs.return_value = []
        from tzdata_pkg.api.routes.maintenance import list_catalogs

        resp = list_catalogs()

        assert resp['success'] is True
        assert resp['data'] == []

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_list_catalogs_filter_by_exchange(self, mock_cm):
        """Filter catalogs by exchange code."""
        mock_cm.list_catalogs.return_value = [{'id': 1, 'exchange_code': 'CFFEX'}]
        from tzdata_pkg.api.routes.maintenance import list_catalogs

        resp = list_catalogs(exchange='CFFEX')

        mock_cm.list_catalogs.assert_called_once_with(exchange_code='CFFEX', product_code=None)

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_list_catalogs_filter_by_product(self, mock_cm):
        """Filter catalogs by product code."""
        mock_cm.list_catalogs.return_value = [{'id': 1, 'product_code': 'IM'}]
        from tzdata_pkg.api.routes.maintenance import list_catalogs

        resp = list_catalogs(product='IM')

        mock_cm.list_catalogs.assert_called_once_with(exchange_code=None, product_code='IM')

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_list_catalogs_backend_error(self, mock_cm):
        """Backend error should return HTTP 500."""
        mock_cm.list_catalogs.side_effect = RuntimeError("DB connection failed")
        from tzdata_pkg.api.routes.maintenance import list_catalogs
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            list_catalogs()
        assert exc_info.value.status_code == 500
        assert "DB connection failed" in str(exc_info.value.detail)


# ============================================================
# 2. /api/maintenance/catalogs/{id} — 404 & invalid ID
# ============================================================

class TestCatalogDetailEndpoints:

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_get_catalog_not_found(self, mock_cm):
        """Non-existent catalog ID should return 404."""
        mock_cm.get_catalog.return_value = None
        from tzdata_pkg.api.routes.maintenance import get_catalog
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_catalog(999)
        assert exc_info.value.status_code == 404

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_get_catalog_success(self, mock_cm):
        """Valid catalog ID returns data."""
        mock_cm.get_catalog.return_value = {
            'id': 1, 'catalog_name': 'Test', 'data_type': 'daily'
        }
        from tzdata_pkg.api.routes.maintenance import get_catalog

        resp = get_catalog(1)

        assert resp['success'] is True
        assert resp['data']['id'] == 1

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_get_catalog_negative_id(self, mock_cm):
        """Negative catalog ID should not crash, returns 404."""
        mock_cm.get_catalog.return_value = None
        from tzdata_pkg.api.routes.maintenance import get_catalog
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_catalog(-1)
        assert exc_info.value.status_code == 404

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_get_catalog_zero_id(self, mock_cm):
        """Catalog ID 0 should return 404."""
        mock_cm.get_catalog.return_value = None
        from tzdata_pkg.api.routes.maintenance import get_catalog
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_catalog(0)
        assert exc_info.value.status_code == 404


# ============================================================
# 3. /api/maintenance/health/diff — empty & partial
# ============================================================

class TestHealthSnapshotEndpoints:

    @patch('tzdata_pkg.maintenance.monitoring.health_snapshot.HealthSnapshotGenerator')
    def test_health_diff_no_catalogs(self, mock_gen):
        """Empty catalog list returns empty data."""
        mock_gen.get_all_diffs.return_value = []
        from tzdata_pkg.api.routes.maintenance import get_diff_status

        resp = get_diff_status()

        assert isinstance(resp, dict)
        assert 'data' in resp
        assert resp['data'] == []

    @patch('tzdata_pkg.maintenance.monitoring.health_snapshot.HealthSnapshotGenerator')
    def test_health_diff_with_catalogs(self, mock_gen):
        """Health diff returns catalog-level diff data."""
        mock_gen.get_all_diffs.return_value = [
            {'catalog_id': 1, 'catalog_name': 'Test', 'missing_days': 0,
             'quality_score': 90.0, 'sync_status': 'completed'}
        ]
        from tzdata_pkg.api.routes.maintenance import get_diff_status

        resp = get_diff_status()

        assert len(resp['data']) == 1
        item = resp['data'][0]
        assert 'catalog_id' in item
        assert 'missing_days' in item
        assert 'quality_score' in item


# ============================================================
# 4. Trade calendar boundary tests
# ============================================================

class TestTradeCalendarEndpoints:

    def test_trading_days_same_date(self):
        """start_date == end_date should return valid response."""
        from tzdata_pkg.api.routes.maintenance import get_trading_days

        resp = get_trading_days('2025-01-02', '2025-01-02')

        assert resp['success'] is True
        assert isinstance(resp['data'], list)

    def test_trading_days_reverse_range(self):
        """start_date > end_date should return empty list."""
        from tzdata_pkg.api.routes.maintenance import get_trading_days

        resp = get_trading_days('2025-12-31', '2025-01-01')

        assert resp['success'] is True
        assert resp['count'] == 0

    def test_is_trading_day_valid_date(self):
        """Valid trading day check returns boolean."""
        from tzdata_pkg.api.routes.maintenance import is_trading_day

        resp = is_trading_day('2025-01-02')

        assert resp['success'] is True
        assert 'is_trading_day' in resp

    def test_is_trading_day_invalid_date_format(self):
        """Invalid date format should raise HTTPException."""
        from tzdata_pkg.api.routes.maintenance import is_trading_day
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            is_trading_day('not-a-date')


# ============================================================
# 5. Sync task failure scenarios
# ============================================================

class TestSyncTaskScenarios:

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_incremental_sync_no_enabled_catalogs(self, mock_cm):
        """Sync task with no enabled catalogs should complete gracefully."""
        mock_cm.get_enabled_catalogs.return_value = []
        from tzdata_pkg.scheduler.tasks.sync_tasks import daily_incremental_sync

        result = daily_incremental_sync()

        assert result['status'] == 'completed'


# ============================================================
# 6. Reconciliation task edge cases
# ============================================================

class TestReconciliationTask:

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_reconcile_no_catalogs(self, mock_cm):
        """No enabled catalogs should return empty check."""
        mock_cm.get_enabled_catalogs.return_value = []
        from tzdata_pkg.scheduler.tasks.check_tasks import reconcile_catalog_records

        result = reconcile_catalog_records()

        assert result['status'] == 'completed'
        assert result['catalogs_checked'] == 0
        assert result['corrected'] == 0


# ============================================================
# 7. Gap detection task edge cases
# ============================================================

class TestGapDetectionTask:

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_detect_gaps_no_catalogs(self, mock_cm):
        """No enabled catalogs should return empty."""
        mock_cm.get_enabled_catalogs.return_value = []
        from tzdata_pkg.scheduler.tasks.check_tasks import detect_data_gaps

        result = detect_data_gaps()

        assert result['status'] == 'completed'
        assert result['catalogs_checked'] == 0

    def test_normalize_date_formats(self):
        """_normalize_date handles YYYYMMDD, ISO, and date objects."""
        from tzdata_pkg.scheduler.tasks.check_tasks import _normalize_date

        assert _normalize_date('20250102') == '2025-01-02'
        assert _normalize_date('2025-01-02') == '2025-01-02'
        assert _normalize_date(date(2025, 1, 2)) == '2025-01-02'
        assert _normalize_date('') == ''
        assert _normalize_date(None) == ''

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_detect_gaps_catalog_no_date_range(self, mock_cm):
        """Catalog with no local data should skip gracefully."""
        mock_cm.get_enabled_catalogs.return_value = [
            {'id': 99, 'catalog_name': 'Empty', 'exchange_code': 'CFFEX',
             'product_code': 'TEST', 'contract_code': '', 'data_type': 'daily'}
        ]
        from tzdata_pkg.scheduler.tasks.check_tasks import detect_data_gaps
        from tzdata_pkg.storage.db_registry import DBRegistry

        # Mock pool to return no date range
        mock_pool = MagicMock()
        mock_pool.transaction.return_value.__enter__ = MagicMock(return_value=MagicMock(
            execute=MagicMock(return_value=MagicMock(fetchone=MagicMock(return_value=None)))
        ))
        mock_pool.transaction.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(DBRegistry, 'get_pool', return_value=mock_pool):
            result = detect_data_gaps()

            assert result['status'] == 'completed'
            assert result['catalogs_checked'] >= 1


# ============================================================
# 8. create_catalog endpoint boundary tests
# ============================================================

class TestCreateCatalog:

    def test_create_catalog_missing_fields(self):
        """Creating catalog without required fields should fail."""
        from tzdata_pkg.api.routes.maintenance import create_catalog
        from fastapi import HTTPException

        with pytest.raises(Exception):
            create_catalog({})

    @patch('tzdata_pkg.maintenance.metadata.catalog_manager.CatalogManager')
    def test_create_catalog_success(self, mock_cm):
        """Valid catalog creation returns ID."""
        mock_cm.create_catalog.return_value = 1
        from tzdata_pkg.api.routes.maintenance import create_catalog

        resp = create_catalog({
            'catalog_name': 'Test',
            'exchange_code': 'CFFEX',
            'product_code': 'TEST',
            'data_type': 'daily',
            'data_source': 'tushare'
        })

        assert resp['success'] is True
        assert resp['catalog_id'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
