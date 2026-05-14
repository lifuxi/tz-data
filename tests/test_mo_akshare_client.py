"""
TDD tests for MO signal data layer — akshare client.

Following TDD: these tests should FAIL initially, then pass after implementation.
"""
import pytest
from datetime import date
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestAkshareClient:
    """Tests for the akshare unified client."""

    def test_import_akshare_client(self):
        """Client module should be importable."""
        from tzdata_pkg.download.akshare.client import AkshareClient
        assert AkshareClient is not None

    def test_create_client(self):
        """Client should be instantiable without errors."""
        from tzdata_pkg.download.akshare.client import AkshareClient
        client = AkshareClient()
        assert client is not None

    @patch('akshare.stock_zh_index_daily')
    def test_fetch_index_daily(self, mock_ak_func):
        """Should fetch index daily data via stock_zh_index_daily_em."""
        from tzdata_pkg.download.akshare.client import AkshareClient

        # Mock akshare response
        mock_df = pd.DataFrame({
            'date': ['2025-01-02', '2025-01-03'],
            'open': [6000.0, 6010.0],
            'close': [6005.0, 6015.0],
            'high': [6010.0, 6020.0],
            'low': [5995.0, 6005.0],
            'volume': [100000000, 110000000],
            'amount': [1e11, 1.1e11],
        })
        mock_ak_func.return_value = mock_df

        client = AkshareClient()
        df = client.fetch_index_daily('sh000852')

        mock_ak_func.assert_called_once_with(symbol='sh000852')
        assert len(df) == 2
        assert 'date' in df.columns

    @patch('akshare.fund_etf_hist_em')
    def test_fetch_etf_daily(self, mock_ak_func):
        """Should fetch ETF daily data via fund_etf_hist_em."""
        from tzdata_pkg.download.akshare.client import AkshareClient

        mock_df = pd.DataFrame({
            '日期': ['2025-01-02', '2025-01-03'],
            '开盘': [3.0, 3.01],
            '收盘': [3.01, 3.02],
            '最高': [3.02, 3.03],
            '最低': [2.99, 3.00],
            '成交量': [1000000, 1100000],
            '成交额': [3e6, 3.3e6],
        })
        mock_ak_func.return_value = mock_df

        client = AkshareClient()
        df = client.fetch_etf_daily('512100', start_date='20250101', end_date='20250131')

        mock_ak_func.assert_called_once()
        assert len(df) == 2

    @patch('akshare.futures_zh_daily_sina')
    def test_fetch_futures_daily(self, mock_ak_func):
        """Should fetch futures daily data via futures_zh_daily_sina."""
        from tzdata_pkg.download.akshare.client import AkshareClient

        mock_df = pd.DataFrame({
            'date': ['2025-01-02', '2025-01-03'],
            'open': [7000.0, 7010.0],
            'close': [7005.0, 7015.0],
            'high': [7010.0, 7020.0],
            'low': [6995.0, 7005.0],
            'volume': [50000, 55000],
            'hold': [100000, 101000],
            'settle': [0.0, 0.0],
        })
        mock_ak_func.return_value = mock_df

        client = AkshareClient()
        df = client.fetch_futures_daily('IM0')

        mock_ak_func.assert_called_once_with(symbol='IM0')
        assert len(df) == 2

    @patch('akshare.index_stock_cons')
    def test_fetch_component_stocks(self, mock_ak_func):
        """Should fetch index component stocks via index_stock_cons."""
        from tzdata_pkg.download.akshare.client import AkshareClient

        mock_df = pd.DataFrame({
            '成分代码': ['001382', '002827'],
            '成分名称': ['test1', 'test2'],
            '纳入日期': ['2025-01-01', '2025-01-01'],
        })
        mock_ak_func.return_value = mock_df

        client = AkshareClient()
        df = client.fetch_component_stocks('000852')

        mock_ak_func.assert_called_once_with(symbol='000852')
        assert len(df) == 2

    @patch('akshare.stock_zh_index_daily')
    def test_fetch_index_daily_empty(self, mock_ak_func):
        """Should handle empty API response gracefully."""
        from tzdata_pkg.download.akshare.client import AkshareClient

        mock_ak_func.return_value = pd.DataFrame()

        client = AkshareClient()
        df = client.fetch_index_daily('sh000852')

        assert df is not None
        assert len(df) == 0

    @patch('akshare.stock_zh_index_daily')
    def test_fetch_index_daily_error(self, mock_ak_func):
        """Should raise or handle API error gracefully."""
        from tzdata_pkg.download.akshare.client import AkshareClient

        mock_ak_func.side_effect = Exception("Network error")

        client = AkshareClient()
        with pytest.raises(Exception):
            client.fetch_index_daily('sh000852')
