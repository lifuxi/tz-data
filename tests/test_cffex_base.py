"""TDD tests for tzdata.download.cffex.base module"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import date

import pytest


class TestCFFEXDownloaderBase:
    """Tests for CFFEXDownloader base class"""

    def _make_downloader(self, config=None):
        from tzdata_pkg.download.cffex.base import CFFEXDownloader

        class TestDownloader(CFFEXDownloader):
            def save_to_database(self, parse_result):
                return parse_result.record_count

            def create_tables(self, year):
                cursor = self.conn.cursor()
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS test_daily_{year} (
                        trade_date TEXT, instrument_id TEXT,
                        open_price REAL, high_price REAL,
                        low_price REAL, close_price REAL,
                        volume INTEGER
                    )
                """)
                self.conn.commit()

            def _get_table_name(self, data_type, year=None):
                y = year or date.today().year
                return f"test_daily_{y}"

        tmpdir = tempfile.mkdtemp()
        db_path = Path(tmpdir) / "test.db"
        csv_dir = Path(tmpdir) / "raw"
        log_dir = Path(tmpdir) / "logs"
        checksum_file = Path(tmpdir) / ".checksums.json"

        test_config = {
            "base_url": "http://www.cffex.com.cn/sj/",
            "storage": {
                "csv_dir": str(csv_dir),
                "db_path": str(db_path),
                "log_dir": str(log_dir),
                "checksum_file": str(checksum_file),
            },
            "download": {
                "timeout": 5,
                "max_retries": 2,
                "retry_delays": [0.01, 0.01],
                "request_delay": 0.01,
                "user_agent": "TestAgent",
            },
            "batch": {"empty_file_threshold": 3},
            "partition": {"start_year": 2024},
        }
        if config:
            test_config.update(config)

        downloader = TestDownloader(test_config)
        return downloader, tmpdir

    def _cleanup(self, downloader, tmpdir):
        import shutil
        downloader.close()
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    def test_init_creates_directories(self):
        downloader, tmpdir = self._make_downloader()
        db_path = Path(downloader.config["storage"]["db_path"])
        assert db_path.parent.exists()
        self._cleanup(downloader, tmpdir)

    def test_init_creates_database(self):
        downloader, tmpdir = self._make_downloader()
        db_path = Path(downloader.config["storage"]["db_path"])
        assert db_path.exists()
        self._cleanup(downloader, tmpdir)

    def test_calculate_checksum(self):
        downloader, tmpdir = self._make_downloader()
        checksum = downloader.calculate_checksum(b"hello world")
        assert len(checksum) == 32
        assert checksum == downloader.calculate_checksum(b"hello world")
        assert checksum != downloader.calculate_checksum(b"hello")
        self._cleanup(downloader, tmpdir)

    def test_checksum_persistence(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = Path(tmpdir) / "test.db"
            csv_dir = Path(tmpdir) / "raw"
            log_dir = Path(tmpdir) / "logs"
            checksum_file = Path(tmpdir) / ".checksums.json"

            test_config = {
                "base_url": "http://www.cffex.com.cn/sj/",
                "storage": {
                    "csv_dir": str(csv_dir),
                    "db_path": str(db_path),
                    "log_dir": str(log_dir),
                    "checksum_file": str(checksum_file),
                },
                "download": {
                    "timeout": 5, "max_retries": 2,
                    "retry_delays": [0.01, 0.01],
                    "request_delay": 0.01,
                    "user_agent": "TestAgent",
                },
                "batch": {"empty_file_threshold": 3},
                "partition": {"start_year": 2024},
            }

            from tzdata_pkg.download.cffex.base import CFFEXDownloader
            class TestDownloader(CFFEXDownloader):
                def save_to_database(self, parse_result):
                    return parse_result.record_count
                def create_tables(self, year):
                    cursor = self.conn.cursor()
                    cursor.execute(f"CREATE TABLE IF NOT EXISTS test_daily_{year} (trade_date TEXT)")
                    self.conn.commit()
                def _get_table_name(self, data_type, year=None):
                    return f"test_daily_{year or date.today().year}"

            downloader = TestDownloader(test_config)
            downloader.checksums["test_key"] = "abc123"
            downloader._save_checksums()
            downloader.close()

            # Re-create with same directory
            downloader2 = TestDownloader(test_config)
            assert downloader2.checksums["test_key"] == "abc123"
            downloader2.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch("requests.Session.get")
    def test_download_csv_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"instrument_id,open,close\nMO2604,3500,3600\n"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        downloader, tmpdir = self._make_downloader()
        from tzdata_pkg.download.cffex.url_builder import CFFEXURLInfo
        url_info = CFFEXURLInfo(
            url="http://example.com/test.csv",
            data_type="daily",
            trade_date="2026-04-08",
            filename="daily_20260408.csv",
        )
        result = downloader.download_csv(url_info, save_file=False)
        assert result.success is True
        assert result.data_type == "daily"
        self._cleanup(downloader, tmpdir)

    @patch("requests.Session.get")
    def test_download_csv_404_returns_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        downloader, tmpdir = self._make_downloader()
        from tzdata_pkg.download.cffex.url_builder import CFFEXURLInfo
        url_info = CFFEXURLInfo(
            url="http://example.com/test.csv",
            data_type="daily",
            trade_date="2026-04-08",
        )
        result = downloader.download_csv(url_info, save_file=False)
        assert result.success is True
        assert result.file_path is None
        assert result.record_count == 0
        self._cleanup(downloader, tmpdir)

    @patch("requests.Session.get")
    def test_download_csv_timeout_retries(self, mock_get):
        from requests.exceptions import Timeout
        mock_get.side_effect = Timeout()

        downloader, tmpdir = self._make_downloader()
        from tzdata_pkg.download.cffex.url_builder import CFFEXURLInfo
        url_info = CFFEXURLInfo(
            url="http://example.com/test.csv",
            data_type="daily",
            trade_date="2026-04-08",
        )
        result = downloader.download_csv(url_info, save_file=False)
        assert result.success is False
        assert result.error is not None
        assert mock_get.call_count == 2
        self._cleanup(downloader, tmpdir)

    def test_download_batch(self):
        downloader, tmpdir = self._make_downloader()

        with patch.object(downloader, "download_csv") as mock_dl:
            mock_dl.return_value = MagicMock(
                success=True, file_path=None, record_count=0
            )
            results = downloader.download_batch(
                "daily", date(2026, 4, 6), date(2026, 4, 7), save_csv=False
            )
            assert len(results) >= 1
            assert all(isinstance(r.success, bool) for r in results)

        self._cleanup(downloader, tmpdir)

    def test_context_manager(self):
        downloader, tmpdir = self._make_downloader()
        with downloader:
            assert downloader.conn is not None
        # After exit, session should be closed
        self._cleanup(downloader, tmpdir)

    def test_get_latest_date_empty_table(self):
        downloader, tmpdir = self._make_downloader()
        downloader.create_tables(2026)
        result = downloader.get_latest_date("daily", 2026)
        assert result is None
        self._cleanup(downloader, tmpdir)
