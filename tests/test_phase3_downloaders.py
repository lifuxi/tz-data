"""Tests for Phase 3: Tushare, CFMMC, and BaseExchangeDownloader."""

import pytest
from datetime import date
from pathlib import Path


# ── BaseExchangeDownloader tests ────────────────────────────

class TestBaseExchangeDownloader:
    """Test the base exchange downloader abstraction."""

    def test_import(self):
        from tzdata_pkg.download.base import BaseExchangeDownloader
        assert BaseExchangeDownloader is not None

    def test_is_abstract(self):
        from tzdata_pkg.download.base import BaseExchangeDownloader
        # Should not be instantiable directly (abstract)
        with pytest.raises(TypeError):
            BaseExchangeDownloader({})

    def test_download_result(self):
        from tzdata_pkg.download.download_result import DownloadResult
        r = DownloadResult(
            success=True, url="http://test.com", file_path=None,
            error=None, data_type="daily", trade_date="2025-01-01",
            record_count=10,
        )
        assert r.success is True
        assert r.record_count == 10

    def test_base_apidownloader_import(self):
        from tzdata_pkg.download.base import BaseAPIDownloader
        assert BaseAPIDownloader is not None

    def test_download_module_exports(self):
        from tzdata_pkg.download import DownloadResult, BaseExchangeDownloader
        assert DownloadResult is not None
        assert BaseExchangeDownloader is not None


# ── Tushare downloader tests ────────────────────────────────

class TestTushareDownloaders:
    """Test Tushare downloader imports and structure."""

    def test_import_daily(self):
        from tzdata_pkg.download.tushare import TushareDailyDownloader
        assert TushareDailyDownloader is not None

    def test_import_minute(self):
        from tzdata_pkg.download.tushare import TushareMinuteDownloader
        assert TushareMinuteDownloader is not None

    def test_import_option(self):
        from tzdata_pkg.download.tushare import TushareOptionDownloader
        assert TushareOptionDownloader is not None

    def test_tushare_client_import(self):
        from tzdata_pkg.download.tushare.client import TushareClient
        assert TushareClient is not None

    def test_client_requires_token(self):
        from tzdata_pkg.download.tushare.client import TushareClient
        with pytest.raises(ValueError, match="token"):
            TushareClient(token="")

    def test_daily_requires_token(self):
        from tzdata_pkg.download.tushare import TushareDailyDownloader
        with pytest.raises(ValueError, match="TOKEN"):
            TushareDailyDownloader(config={"token": ""})

    def test_minute_requires_token(self):
        from tzdata_pkg.download.tushare import TushareMinuteDownloader
        with pytest.raises(ValueError, match="TOKEN"):
            TushareMinuteDownloader(config={"token": ""})

    def test_option_requires_token(self):
        from tzdata_pkg.download.tushare import TushareOptionDownloader
        with pytest.raises(ValueError, match="TOKEN"):
            TushareOptionDownloader(config={"token": ""})


# ── CFMMC downloader tests ──────────────────────────────────

class TestCFMMCDownloader:
    """Test CFMMC downloader imports and structure."""

    def test_import(self):
        from tzdata_pkg.download.cfmmc import CFMMCDownloader
        assert CFMMCDownloader is not None

    def test_inherits_base(self):
        from tzdata_pkg.download.cfmmc import CFMMCDownloader
        from tzdata_pkg.download.base import BaseExchangeDownloader
        assert issubclass(CFMMCDownloader, BaseExchangeDownloader)

    def test_source_name(self):
        from tzdata_pkg.download.cfmmc import CFMMCDownloader
        assert CFMMCDownloader.SOURCE_NAME == "cfmmc"


# ── TushareOptionDownloader parsing helpers ─────────────────

class TestOptionCodeParsing:
    """Test option contract code parsing."""

    def test_extract_contract_simple(self):
        from tzdata_pkg.download.tushare.option_downloader import TushareOptionDownloader
        assert TushareOptionDownloader._extract_contract("MO2505C8500.CFFEX") == "MO2505-C-8500"

    def test_extract_contract_put(self):
        from tzdata_pkg.download.tushare.option_downloader import TushareOptionDownloader
        assert TushareOptionDownloader._extract_contract("MO2505P9000.CFFEX") == "MO2505-P-9000"

    def test_extract_contract_no_dot(self):
        from tzdata_pkg.download.tushare.option_downloader import TushareOptionDownloader
        assert TushareOptionDownloader._extract_contract("MO2505C8500") == "MO2505-C-8500"

    def test_parse_option_details_call(self):
        from tzdata_pkg.download.tushare.option_downloader import TushareOptionDownloader
        strike, opt_type = TushareOptionDownloader._parse_option_details("MO2505C8500.CFFEX")
        assert opt_type == "C"
        assert strike == 85.0  # 8500 / 100

    def test_parse_option_details_put(self):
        from tzdata_pkg.download.tushare.option_downloader import TushareOptionDownloader
        strike, opt_type = TushareOptionDownloader._parse_option_details("MO2505P9000.CFFEX")
        assert opt_type == "P"
        assert strike == 90.0

    def test_parse_date_range(self):
        from tzdata_pkg.download.tushare.option_downloader import TushareOptionDownloader
        sd, ed = TushareOptionDownloader._parse_date_range("20250101-20250131")
        assert sd == "20250101"
        assert ed == "20250131"
