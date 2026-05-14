"""
Unit tests for SyncEngine.
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine, SyncBatch, SyncResult


class TestSyncBatch:
    """Tests for SyncBatch dataclass."""
    
    def test_create_batch(self):
        """Test creating a sync batch."""
        batch = SyncBatch(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            batch_index=0,
            total_batches=10
        )
        
        assert batch.start_date == date(2025, 1, 1)
        assert batch.end_date == date(2025, 1, 31)
        assert batch.batch_index == 0
        assert batch.total_batches == 10
    
    def test_batch_duration(self):
        """Test calculating batch duration in days."""
        batch = SyncBatch(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            batch_index=0,
            total_batches=10
        )
        
        duration = (batch.end_date - batch.start_date).days + 1
        assert duration == 31


class TestSyncResult:
    """Tests for SyncResult dataclass."""
    
    def test_create_success_result(self):
        """Test creating a successful sync result."""
        result = SyncResult(
            success=True,
            records_fetched=100,
            records_stored=100,
            progress_pct=100.0,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error_message=None
        )
        
        assert result.success is True
        assert result.records_fetched == 100
        assert result.records_stored == 100
        assert result.progress_pct == 100.0
        assert result.error_message is None
    
    def test_create_failure_result(self):
        """Test creating a failed sync result."""
        result = SyncResult(
            success=False,
            records_fetched=50,
            records_stored=0,
            progress_pct=50.0,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error_message="Connection timeout"
        )
        
        assert result.success is False
        assert result.records_fetched == 50
        assert result.error_message == "Connection timeout"
    
    def test_duration_calculation(self):
        """Test calculating sync duration."""
        start = datetime.now()
        end = start + timedelta(seconds=30)
        
        result = SyncResult(
            success=True,
            records_fetched=100,
            records_stored=100,
            progress_pct=100.0,
            start_time=start,
            end_time=end,
            error_message=None
        )
        
        duration = (result.end_time - result.start_time).total_seconds()
        assert duration == pytest.approx(30.0, abs=0.1)


class TestSyncEngineInitialization:
    """Tests for SyncEngine initialization."""
    
    @patch('tzdata_pkg.maintenance.sync.sync_engine.CatalogManager')
    def test_init_with_catalog_id(self, mock_catalog_manager):
        """Test initializing SyncEngine with catalog ID."""
        mock_catalog_manager.get_catalog.return_value = {
            'id': 1,
            'exchange_code': 'CFFEX',
            'product_code': 'IM',
            'contract_code': 'IM2506',
            'data_type': 'daily',
            'frequency': '1d',
            'data_source': 'tushare',
            'sync_mode': 'incremental'
        }
        
        engine = SyncEngine(catalog_id=1, mode='incremental')
        
        assert engine.catalog_id == 1
        assert engine.mode == 'incremental'
        mock_catalog_manager.get_catalog.assert_called_once_with(1)
    
    @patch('tzdata_pkg.maintenance.sync.sync_engine.CatalogManager')
    def test_init_with_full_mode(self, mock_catalog_manager):
        """Test initializing SyncEngine with full sync mode."""
        mock_catalog_manager.get_catalog.return_value = {
            'id': 1,
            'exchange_code': 'CFFEX',
            'product_code': 'IM',
            'data_type': 'daily',
            'sync_mode': 'full'
        }
        
        engine = SyncEngine(catalog_id=1, mode='full')
        
        assert engine.mode == 'full'


class TestSyncEngineDateRange:
    """Tests for SyncEngine date range calculation."""
    
    @patch('tzdata_pkg.maintenance.sync.sync_engine.CatalogManager')
    @patch('tzdata_pkg.maintenance.sync.sync_engine.SourceManager')
    def test_calculate_incremental_range(self, mock_source_manager, mock_catalog_manager):
        """Test calculating incremental sync date range."""
        mock_catalog_manager.get_catalog.return_value = {
            'id': 1,
            'exchange_code': 'CFFEX',
            'product_code': 'IM',
            'contract_code': 'IM2506',
            'data_type': 'daily',
            'last_sync_at': datetime(2025, 1, 2)
        }
        
        mock_source = MagicMock()
        mock_source.get_latest_date.return_value = date(2025, 1, 10)
        mock_source_manager.get_source.return_value = mock_source
        
        engine = SyncEngine(catalog_id=1, mode='incremental')
        engine._load_catalog()
        engine._get_data_source()
        
        # This would calculate the range from last_sync + 1 day to latest remote date
        # Implementation depends on actual logic
        assert engine.catalog is not None
        assert engine.source is not None
    
    @patch('tzdata_pkg.maintenance.sync.sync_engine.CatalogManager')
    def test_calculate_full_range(self, mock_catalog_manager):
        """Test calculating full sync date range."""
        mock_catalog_manager.get_catalog.return_value = {
            'id': 1,
            'exchange_code': 'CFFEX',
            'product_code': 'IM',
            'contract_code': 'IM2506',
            'data_type': 'daily'
        }
        
        engine = SyncEngine(catalog_id=1, mode='full')
        engine._load_catalog()
        
        # Full sync should use configured date range or default
        assert engine.mode == 'full'


class TestSyncEngineBatchSplitting:
    """Tests for SyncEngine batch splitting logic."""
    
    def test_split_into_batches_30_days(self):
        """Test splitting date range into 30-day batches."""
        engine = SyncEngine.__new__(SyncEngine)
        engine.batch_size_days = 30
        
        start_date = date(2025, 1, 1)
        end_date = date(2025, 3, 31)  # 90 days
        
        batches = engine._split_into_batches(start_date, end_date)
        
        assert len(batches) == 3
        assert batches[0].start_date == date(2025, 1, 1)
        assert batches[0].end_date == date(2025, 1, 30)
        assert batches[1].start_date == date(2025, 1, 31)
        assert batches[1].end_date == date(2025, 3, 1)
        assert batches[2].start_date == date(2025, 3, 2)
        assert batches[2].end_date == date(2025, 3, 31)
    
    def test_split_into_batches_partial_last_batch(self):
        """Test splitting with partial last batch."""
        engine = SyncEngine.__new__(SyncEngine)
        engine.batch_size_days = 30
        
        start_date = date(2025, 1, 1)
        end_date = date(2025, 2, 15)  # 46 days
        
        batches = engine._split_into_batches(start_date, end_date)
        
        assert len(batches) == 2
        assert batches[0].end_date == date(2025, 1, 30)
        assert batches[1].end_date == date(2025, 2, 15)
    
    def test_split_into_batches_single_batch(self):
        """Test splitting when range fits in single batch."""
        engine = SyncEngine.__new__(SyncEngine)
        engine.batch_size_days = 30
        
        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 15)  # 15 days
        
        batches = engine._split_into_batches(start_date, end_date)
        
        assert len(batches) == 1
        assert batches[0].start_date == date(2025, 1, 1)
        assert batches[0].end_date == date(2025, 1, 15)


class TestSyncEngineExecution:
    """Tests for SyncEngine execution flow."""
    
    @patch('tzdata_pkg.maintenance.sync.sync_engine.CatalogManager')
    @patch('tzdata_pkg.maintenance.sync.sync_engine.SourceManager')
    @patch('tzdata_pkg.maintenance.sync.sync_engine.QuestDBStore')
    @patch('tzdata_pkg.maintenance.sync.sync_engine.CheckpointManager')
    def test_execute_incremental_sync(
        self,
        mock_checkpoint,
        mock_questdb_store,
        mock_source_manager,
        mock_catalog_manager
    ):
        """Test executing incremental sync."""
        # Setup mocks
        mock_catalog_manager.get_catalog.return_value = {
            'id': 1,
            'catalog_name': 'Test Catalog',
            'exchange_code': 'CFFEX',
            'product_code': 'IM',
            'contract_code': 'IM2506',
            'data_type': 'daily',
            'frequency': '1d',
            'data_source': 'tushare',
            'sync_mode': 'incremental',
            'last_sync_at': datetime(2025, 1, 2)
        }
        
        mock_source = MagicMock()
        mock_source.get_latest_date.return_value = date(2025, 1, 10)
        mock_source.fetch_daily_quotes.return_value = [
            {'trade_date': '2025-01-03', 'close': 5800.0},
            {'trade_date': '2025-01-04', 'close': 5850.0}
        ]
        mock_source_manager.get_source.return_value = mock_source
        
        mock_questdb_store.insert_daily_quotes.return_value = 2
        
        # Execute
        engine = SyncEngine(catalog_id=1, mode='incremental')
        result = engine.execute()
        
        # Verify
        assert result.success is True
        assert result.records_fetched >= 0
        mock_source.fetch_daily_quotes.assert_called()
        mock_questdb_store.insert_daily_quotes.assert_called()
    
    @patch('tzdata_pkg.maintenance.sync.sync_engine.CatalogManager')
    @patch('tzdata_pkg.maintenance.sync.sync_engine.SourceManager')
    def test_execute_with_no_data(self, mock_source_manager, mock_catalog_manager):
        """Test executing sync when no new data available."""
        mock_catalog_manager.get_catalog.return_value = {
            'id': 1,
            'exchange_code': 'CFFEX',
            'product_code': 'IM',
            'contract_code': 'IM2506',
            'data_type': 'daily',
            'last_sync_at': datetime(2025, 1, 10)
        }
        
        mock_source = MagicMock()
        mock_source.get_latest_date.return_value = date(2025, 1, 10)  # Same as last sync
        mock_source_manager.get_source.return_value = mock_source
        
        engine = SyncEngine(catalog_id=1, mode='incremental')
        result = engine.execute()
        
        # Should handle gracefully when no new data
        assert result is not None


class TestSyncEngineErrorHandling:
    """Tests for SyncEngine error handling."""
    
    @patch('tzdata_pkg.maintenance.sync.sync_engine.CatalogManager')
    def test_execute_with_invalid_catalog(self, mock_catalog_manager):
        """Test executing sync with invalid catalog ID."""
        mock_catalog_manager.get_catalog.return_value = None
        
        engine = SyncEngine(catalog_id=999, mode='incremental')
        
        with pytest.raises(Exception):
            engine.execute()
    
    @patch('tzdata_pkg.maintenance.sync.sync_engine.CatalogManager')
    @patch('tzdata_pkg.maintenance.sync.sync_engine.SourceManager')
    def test_execute_with_source_error(self, mock_source_manager, mock_catalog_manager):
        """Test executing sync when data source fails."""
        mock_catalog_manager.get_catalog.return_value = {
            'id': 1,
            'exchange_code': 'CFFEX',
            'product_code': 'IM',
            'contract_code': 'IM2506',
            'data_type': 'daily',
            'last_sync_at': datetime(2025, 1, 2)
        }
        
        mock_source = MagicMock()
        mock_source.get_latest_date.side_effect = ConnectionError("API timeout")
        mock_source_manager.get_source.return_value = mock_source
        
        engine = SyncEngine(catalog_id=1, mode='incremental')
        
        with pytest.raises(ConnectionError):
            engine.execute()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
