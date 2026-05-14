"""TDD tests for tzdata.download.cffex.url_builder module"""

from datetime import date
import pytest


class TestCFFEXURLInfo:
    """Tests for CFFEXURLInfo dataclass"""

    def test_create_url_info(self):
        """Can create URL info with all fields"""
        from tzdata_pkg.download.cffex.url_builder import CFFEXURLInfo
        info = CFFEXURLInfo(
            url="http://example.com/data.csv",
            data_type="daily",
            trade_date="2026-04-08",
            product="MO",
            filename="daily_20260408.csv",
        )
        assert info.url == "http://example.com/data.csv"
        assert info.product == "MO"

    def test_optional_fields(self):
        """product and filename are optional"""
        from tzdata_pkg.download.cffex.url_builder import CFFEXURLInfo
        info = CFFEXURLInfo(url="http://x.com", data_type="daily", trade_date="2026-01-01")
        assert info.product is None
        assert info.filename is None


class TestCFFEXURLBuilder:
    """Tests for CFFEXURLBuilder"""

    def setup_method(self):
        from tzdata_pkg.download.cffex.url_builder import CFFEXURLBuilder
        self.builder = CFFEXURLBuilder()

    def test_build_daily_url(self):
        """Builds correct daily URL"""
        info = self.builder.build_daily_url(date(2026, 4, 8))
        assert info.data_type == "daily"
        assert info.trade_date == "20260408"
        assert info.filename == "daily_20260408.csv"
        assert "202604" in info.url
        assert "hqsj/rtj" in info.url

    def test_build_weekly_url(self):
        """Builds correct weekly URL"""
        info = self.builder.build_weekly_url(date(2026, 4, 6))
        assert info.data_type == "weekly"
        assert "hqsj/ztj" in info.url

    def test_build_monthly_url(self):
        """Builds correct monthly URL"""
        info = self.builder.build_monthly_url("202603")
        assert info.data_type == "monthly"
        assert info.trade_date == "202603"
        assert "hqsj/ytj" in info.url
        assert "monthly_202603" in info.filename

    def test_build_position_url(self):
        """Builds correct position ranking URL"""
        info = self.builder.build_position_url(date(2026, 4, 8), "MO")
        assert info.data_type == "position"
        assert info.product == "MO"
        assert "ccpm" in info.url
        assert "MO" in info.url

    def test_build_url_dispatch(self):
        """build_url dispatches to correct builder"""
        info = self.builder.build_url("daily", date(2026, 4, 8))
        assert info.data_type == "daily"

        info = self.builder.build_url("weekly", date(2026, 4, 8))
        assert info.data_type == "weekly"

        info = self.builder.build_url("monthly", date(2026, 4, 8))
        assert info.data_type == "monthly"

        info = self.builder.build_url("position", date(2026, 4, 8), "MO")
        assert info.data_type == "position"

    def test_build_url_position_requires_product(self):
        """build_url raises ValueError if position type without product"""
        with pytest.raises(ValueError):
            self.builder.build_url("position", date(2026, 4, 8))

    def test_build_url_invalid_type(self):
        """build_url raises ValueError for invalid data type"""
        with pytest.raises(ValueError):
            self.builder.build_url("invalid", date(2026, 4, 8))

    def test_build_batch_urls(self):
        """build_batch_urls generates URLs for date range"""
        urls = self.builder.build_batch_urls(
            "daily", date(2026, 4, 6), date(2026, 4, 10)
        )
        # Should include weekdays only (Mon-Fri)
        assert len(urls) >= 3  # at least 3 weekdays
        assert all(u.data_type == "daily" for u in urls)

    def test_build_url_with_custom_base(self):
        """Can use custom base URL"""
        from tzdata_pkg.download.cffex.url_builder import CFFEXURLBuilder
        builder = CFFEXURLBuilder(base_url="http://mirror.example.com/")
        info = builder.build_daily_url(date(2026, 4, 8))
        assert info.url.startswith("http://mirror.example.com/")

    def test_parse_date_from_url(self):
        """Can parse date from URL"""
        url = "http://www.cffex.com.cn/sj/hqsj/rtj/202604/08/20260408_1.csv"
        parsed = self.builder.parse_date_from_url(url)
        assert parsed == "20260408"

    def test_build_convenience_function(self):
        """build_cffex_url convenience function works"""
        from tzdata_pkg.download.cffex.url_builder import build_cffex_url
        url = build_cffex_url("daily", date(2026, 4, 8))
        assert isinstance(url, str)
        assert "20260408" in url
