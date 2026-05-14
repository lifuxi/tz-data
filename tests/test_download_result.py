"""TDD tests for tzdata.download.download_result module"""

from tzdata_pkg.download.download_result import DownloadResult


class TestDownloadResult:
    """Tests for DownloadResult dataclass"""

    def test_create_success_result(self):
        """Can create a successful download result"""
        result = DownloadResult(
            success=True,
            url="http://example.com/data.csv",
            file_path="/tmp/data.csv",
            error=None,
            data_type="daily",
            trade_date="2026-04-08",
            record_count=50,
        )
        assert result.success is True
        assert result.record_count == 50

    def test_create_failure_result(self):
        """Can create a failed download result"""
        result = DownloadResult(
            success=False,
            url="http://example.com/data.csv",
            file_path=None,
            error="Connection timeout",
            data_type="daily",
            trade_date="2026-04-08",
        )
        assert result.success is False
        assert result.error is not None
        assert result.record_count == 0

    def test_default_values(self):
        """Default values are set correctly"""
        result = DownloadResult(
            success=True,
            url="http://x.com",
            file_path=None,
            error=None,
            data_type="daily",
            trade_date="2026-01-01",
        )
        assert result.record_count == 0
