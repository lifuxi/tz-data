"""
TDD tests for Phase 2 MO signal data — component stocks and A50 overnight.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Component Stock Data Downloader ────────────────────────

class TestComponentDownloader:
    """Tests for the component stock data downloader."""

    def test_import(self):
        from tzdata_pkg.download.akshare.component import ComponentDownloader
        assert ComponentDownloader is not None

    def test_create_downloader(self):
        from tzdata_pkg.download.akshare.component import ComponentDownloader
        dl = ComponentDownloader(index_code='000852')
        assert dl.index_code == '000852'

    @patch('tzdata_pkg.download.akshare.component.ComponentDownloader._store_components')
    @patch('tzdata_pkg.download.akshare.component.AkshareClient')
    def test_download_components(self, mock_client_cls, mock_store):
        """Should fetch and store component stock list."""
        from tzdata_pkg.download.akshare.component import ComponentDownloader

        mock_client = MagicMock()
        mock_df = pd.DataFrame({
            '成分代码': ['001382', '002827', '600226'],
            '成分名称': ['test1', 'test2', 'test3'],
            '纳入日期': ['2025-01-01', '2025-01-01', '2025-01-01'],
        })
        mock_client.fetch_component_stocks.return_value = mock_df
        mock_client_cls.return_value = mock_client
        mock_store.return_value = 3

        dl = ComponentDownloader(index_code='000852')
        results = dl.download(date(2025, 1, 1), date(2025, 1, 31))

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].record_count == 3


# ── A50 Overnight Data Downloader ──────────────────────────

class TestA50Downloader:
    """Tests for the A50 overnight futures downloader."""

    def test_import(self):
        from tzdata_pkg.download.akshare.a50_daily import A50DailyDownloader
        assert A50DailyDownloader is not None

    def test_create_downloader(self):
        from tzdata_pkg.download.akshare.a50_daily import A50DailyDownloader
        dl = A50DailyDownloader()
        assert dl.symbol == 'FEF'

    @patch('tzdata_pkg.download.akshare.a50_daily.A50DailyDownloader._store_data')
    @patch('tzdata_pkg.download.akshare.a50_daily.AkshareClient')
    def test_download_success(self, mock_client_cls, mock_store):
        from tzdata_pkg.download.akshare.a50_daily import A50DailyDownloader

        mock_client = MagicMock()
        mock_df = pd.DataFrame({
            'date': ['2025-01-02', '2025-01-03'],
            'open': [14500.0, 14520.0],
            'high': [14530.0, 14550.0],
            'low': [14480.0, 14500.0],
            'close': [14510.0, 14540.0],
            'volume': [50000, 55000],
            'position': [200000, 201000],
            's': [0.0, 0.0],
        })
        mock_client.fetch_a50_daily.return_value = mock_df
        mock_client_cls.return_value = mock_client
        mock_store.return_value = 2

        dl = A50DailyDownloader()
        results = dl.download(date(2025, 1, 1), date(2025, 1, 31))

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].record_count == 2

    @patch('tzdata_pkg.download.akshare.a50_daily.sqlite3.connect')
    def test_store_data_writes_to_db(self, mock_connect):
        from tzdata_pkg.download.akshare.a50_daily import A50DailyDownloader

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        df = pd.DataFrame({
            'date': ['2025-01-02', '2025-01-03'],
            'open': [14500.0, 14520.0],
            'high': [14530.0, 14550.0],
            'low': [14480.0, 14500.0],
            'close': [14510.0, 14540.0],
            'volume': [50000, 55000],
            'position': [200000, 201000],
            's': [0.0, 0.0],
        })

        dl = A50DailyDownloader()
        count = dl._store_data(df)

        assert count == 2
        assert mock_conn.execute.call_count == 2
        mock_conn.commit.assert_called_once()


# ── MO Signal Services: Component ─────────────────────────

class TestComponentSignalService:
    """Tests for component stock signal service."""

    @patch('tzdata_pkg.download.akshare.component.sqlite3.connect')
    def test_store_component_writes_to_db(self, mock_connect):
        from tzdata_pkg.download.akshare.component import ComponentDownloader

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        df = pd.DataFrame({
            '成分代码': ['001382', '002827'],
            '成分名称': ['test1', 'test2'],
            '纳入日期': ['2025-01-01', '2025-01-01'],
        })

        dl = ComponentDownloader(index_code='000852')
        count = dl._store_components(df)

        assert count == 2
        # execute is called for: CREATE TABLE, 2x CREATE INDEX, DELETE, 2x INSERT = 6 total
        assert mock_conn.execute.call_count >= 4
        mock_conn.commit.assert_called()
