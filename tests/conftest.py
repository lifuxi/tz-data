"""
Test configuration and fixtures for pytest.
"""
import pytest
from datetime import date, datetime
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def mock_pg_connection():
    """Mock PostgreSQL connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
    return mock_conn


@pytest.fixture
def mock_questdb_connection():
    """Mock QuestDB connection."""
    mock_conn = MagicMock()
    return mock_conn


@pytest.fixture
def sample_catalog():
    """Sample data catalog for testing."""
    return {
        'id': 1,
        'catalog_name': '中金所-IM-日线',
        'exchange_code': 'CFFEX',
        'product_code': 'IM',
        'contract_code': 'IM2506',
        'data_type': 'daily',
        'frequency': '1d',
        'data_source': 'tushare',
        'is_enabled': True,
        'sync_mode': 'incremental',
        'last_sync_at': datetime.now(),
        'created_at': datetime.now()
    }


@pytest.fixture
def sample_daily_quotes():
    """Sample daily quotes data."""
    return [
        {
            'trade_date': '2025-01-02',
            'open': 5800.0,
            'high': 5850.0,
            'low': 5780.0,
            'close': 5830.0,
            'volume': 100000,
            'turnover': 580000000.0,
            'open_interest': 50000
        },
        {
            'trade_date': '2025-01-03',
            'open': 5830.0,
            'high': 5880.0,
            'low': 5810.0,
            'close': 5860.0,
            'volume': 120000,
            'turnover': 703200000.0,
            'open_interest': 52000
        }
    ]


@pytest.fixture
def sample_minute_quotes():
    """Sample minute quotes data."""
    return [
        {
            'trade_time': '2025-01-02 09:30:00',
            'open': 5800.0,
            'high': 5805.0,
            'low': 5798.0,
            'close': 5802.0,
            'volume': 1000,
            'turnover': 5802000.0
        },
        {
            'trade_time': '2025-01-02 09:31:00',
            'open': 5802.0,
            'high': 5808.0,
            'low': 5800.0,
            'close': 5806.0,
            'volume': 1200,
            'turnover': 6967200.0
        }
    ]


@pytest.fixture
def sample_holdings():
    """Sample top 20 holdings data."""
    return [
        {
            'trade_date': '2025-01-02',
            'member_name': '中信期货',
            'long_volume': 5000,
            'long_change': 100,
            'short_volume': 4800,
            'short_change': -50
        },
        {
            'trade_date': '2025-01-02',
            'member_name': '国泰君安',
            'long_volume': 4500,
            'long_change': -200,
            'short_volume': 4600,
            'short_change': 150
        }
    ]


@pytest.fixture
def mock_tushare_source():
    """Mock Tushare data source."""
    mock_source = MagicMock()
    mock_source.name = 'tushare'
    mock_source.fetch_daily_quotes.return_value = []
    mock_source.fetch_minute_quotes.return_value = []
    mock_source.fetch_top20_holdings.return_value = []
    mock_source.get_latest_date.return_value = date(2025, 1, 2)
    return mock_source


@pytest.fixture
def sync_result_success():
    """Sample successful sync result."""
    from tzdata_pkg.maintenance.sync.sync_engine import SyncResult
    
    return SyncResult(
        success=True,
        records_fetched=100,
        records_stored=100,
        progress_pct=100.0,
        start_time=datetime.now(),
        end_time=datetime.now(),
        error_message=None
    )


@pytest.fixture
def sync_result_failure():
    """Sample failed sync result."""
    from tzdata_pkg.maintenance.sync.sync_engine import SyncResult
    
    return SyncResult(
        success=False,
        records_fetched=50,
        records_stored=0,
        progress_pct=50.0,
        start_time=datetime.now(),
        end_time=datetime.now(),
        error_message="Connection timeout"
    )
