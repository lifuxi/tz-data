"""
TDD tests for MO signal data layer — ETF and futures downloaders.
"""
import pytest
from datetime import date
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── ETF Daily Downloader Tests ─────────────────────────────

class TestEtfDailyDownloader:
    """Tests for the ETF daily downloader."""

    def test_import(self):
        from tzdata_pkg.download.akshare.etf_daily import EtfDailyDownloader
        assert EtfDailyDownloader is not None

    def test_create_downloader(self):
        from tzdata_pkg.download.akshare.etf_daily import EtfDailyDownloader
        dl = EtfDailyDownloader(etf_code='512100')
        assert dl.etf_code == '512100'

    @patch('tzdata_pkg.download.akshare.etf_daily.EtfDailyDownloader._store_data')
    @patch('tzdata_pkg.download.akshare.etf_daily.AkshareClient')
    def test_download_success(self, mock_client_cls, mock_store):
        from tzdata_pkg.download.akshare.etf_daily import EtfDailyDownloader

        mock_client = MagicMock()
        mock_df = pd.DataFrame({
            '日期': ['2025-01-02', '2025-01-03'],
            '开盘': [3.0, 3.01],
            '最高': [3.02, 3.03],
            '最低': [2.99, 3.00],
            '收盘': [3.01, 3.02],
            '成交量': [1000000, 1100000],
            '成交额': [3e6, 3.3e6],
        })
        mock_client.fetch_etf_daily.return_value = mock_df
        mock_client_cls.return_value = mock_client
        mock_store.return_value = 2

        dl = EtfDailyDownloader(etf_code='512100')
        results = dl.download(date(2025, 1, 1), date(2025, 1, 31))

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].record_count == 2

    @patch('tzdata_pkg.download.akshare.etf_daily.sqlite3.connect')
    def test_store_data_writes_to_db(self, mock_connect):
        from tzdata_pkg.download.akshare.etf_daily import EtfDailyDownloader

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        df = pd.DataFrame({
            '日期': ['2025-01-02', '2025-01-03'],
            '开盘': [3.0, 3.01],
            '最高': [3.02, 3.03],
            '最低': [2.99, 3.00],
            '收盘': [3.01, 3.02],
            '成交量': [1000000, 1100000],
        })

        dl = EtfDailyDownloader(etf_code='512100')
        count = dl._store_data(df)

        assert count == 2
        assert mock_conn.execute.call_count == 2
        mock_conn.commit.assert_called_once()


# ── Futures Daily Downloader Tests ──────────────────────────

class TestFuturesDailyDownloader:
    """Tests for the IM futures daily downloader."""

    def test_import(self):
        from tzdata_pkg.download.akshare.futures_daily import FuturesDailyDownloader
        assert FuturesDailyDownloader is not None

    def test_create_downloader(self):
        from tzdata_pkg.download.akshare.futures_daily import FuturesDailyDownloader
        dl = FuturesDailyDownloader(product='IM')
        assert dl.product == 'IM'

    @patch('tzdata_pkg.download.akshare.futures_daily.FuturesDailyDownloader._store_data')
    @patch('tzdata_pkg.download.akshare.futures_daily.AkshareClient')
    def test_download_success(self, mock_client_cls, mock_store):
        from tzdata_pkg.download.akshare.futures_daily import FuturesDailyDownloader

        mock_client = MagicMock()
        mock_df = pd.DataFrame({
            'date': ['2025-01-02', '2025-01-03'],
            'open': [7000.0, 7010.0],
            'high': [7010.0, 7020.0],
            'low': [6995.0, 7005.0],
            'close': [7005.0, 7015.0],
            'volume': [50000, 55000],
            'hold': [100000, 101000],
            'settle': [7003.0, 7013.0],
        })
        mock_client.fetch_futures_daily.return_value = mock_df
        mock_client_cls.return_value = mock_client
        mock_store.return_value = 2

        dl = FuturesDailyDownloader(product='IM')
        results = dl.download(date(2025, 1, 1), date(2025, 1, 31))

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].record_count == 2

    @patch('tzdata_pkg.download.akshare.futures_daily.sqlite3.connect')
    def test_store_data_writes_to_db(self, mock_connect):
        from tzdata_pkg.download.akshare.futures_daily import FuturesDailyDownloader

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        df = pd.DataFrame({
            'date': ['2025-01-02', '2025-01-03'],
            'open': [7000.0, 7010.0],
            'high': [7010.0, 7020.0],
            'low': [6995.0, 7005.0],
            'close': [7005.0, 7015.0],
            'volume': [50000, 55000],
        })

        dl = FuturesDailyDownloader(product='IM')
        count = dl._store_data(df)

        assert count == 2
        assert mock_conn.execute.call_count == 2
        mock_conn.commit.assert_called_once()
