"""
TDD tests for MO signal data layer — index daily downloader.
"""
import pytest
from datetime import date
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestIndexDailyDownloader:
    """Tests for the index daily downloader."""

    def test_import(self):
        from tzdata_pkg.download.akshare.index_daily import IndexDailyDownloader
        assert IndexDailyDownloader is not None

    def test_create_downloader_default(self):
        """Should be creatable with default config."""
        from tzdata_pkg.download.akshare.index_daily import IndexDailyDownloader
        dl = IndexDailyDownloader(index_code='000852')
        assert dl is not None
        assert dl.index_code == '000852'

    def test_create_downloader_csi500(self):
        from tzdata_pkg.download.akshare.index_daily import IndexDailyDownloader
        dl = IndexDailyDownloader(index_code='000905')
        assert dl.index_code == '000905'

    @patch('tzdata_pkg.download.akshare.index_daily.IndexDailyDownloader._store_data')
    @patch('tzdata_pkg.download.akshare.index_daily.AkshareClient')
    def test_download_success(self, mock_client_cls, mock_store):
        """Should download and return DownloadResult with correct record count."""
        from tzdata_pkg.download.akshare.index_daily import IndexDailyDownloader
        from tzdata_pkg.download.download_result import DownloadResult

        mock_client = MagicMock()
        mock_df = pd.DataFrame({
            'date': ['2025-01-02', '2025-01-03', '2025-01-06'],
            'open': [6000.0, 6010.0, 6020.0],
            'close': [6005.0, 6015.0, 6025.0],
            'high': [6010.0, 6020.0, 6030.0],
            'low': [5995.0, 6005.0, 6015.0],
            'volume': [1e8, 1.1e8, 1.2e8],
            'amount': [1e11, 1.1e11, 1.2e11],
        })
        mock_client.fetch_index_daily.return_value = mock_df
        mock_client_cls.return_value = mock_client
        mock_store.return_value = 3

        dl = IndexDailyDownloader(index_code='000852')
        results = dl.download(date(2025, 1, 1), date(2025, 1, 31))

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].record_count == 3

    def test_validate_results(self):
        """Should validate download results."""
        from tzdata_pkg.download.akshare.index_daily import IndexDailyDownloader
        from tzdata_pkg.download.download_result import DownloadResult

        results = [
            DownloadResult(success=True, url="", file_path=None, error=None,
                          data_type="index_daily", trade_date="2025-01", record_count=100),
        ]
        dl = IndexDailyDownloader(index_code='000852')
        validation = dl.validate(results)

        assert validation['success'] == 1
        assert validation['failed'] == 0
        assert validation['total_records'] == 100

    @patch('tzdata_pkg.download.akshare.index_daily.sqlite3.connect')
    def test_store_data_writes_to_db(self, mock_connect):
        """Should write data to option_sim_underlying_daily table."""
        from tzdata_pkg.download.akshare.index_daily import IndexDailyDownloader

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        df = pd.DataFrame({
            'date': ['2025-01-02', '2025-01-03'],
            'open': [6000.0, 6010.0],
            'high': [6010.0, 6020.0],
            'low': [5995.0, 6005.0],
            'close': [6005.0, 6015.0],
            'volume': [1e8, 1.1e8],
        })

        dl = IndexDailyDownloader(index_code='000852')
        count = dl._store_data(df)

        assert count == 2
        assert mock_conn.execute.call_count == 2
        mock_conn.commit.assert_called_once()

    def test_download_empty_data(self):
        """Should handle empty download gracefully."""
        from tzdata_pkg.download.akshare.index_daily import IndexDailyDownloader

        with patch('tzdata_pkg.download.akshare.index_daily.AkshareClient') as mock_cls:
            mock_client = MagicMock()
            mock_client.fetch_index_daily.return_value = pd.DataFrame()
            mock_cls.return_value = mock_client

            dl = IndexDailyDownloader(index_code='000852')
            results = dl.download(date(2025, 1, 1), date(2025, 1, 31))
            assert len(results) == 1
            assert results[0].record_count == 0
