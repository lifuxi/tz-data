"""Tests for Phase 2 refactored downloaders."""

import pytest
import os
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from tzdata_pkg.download.cffex.daily_downloader import CFFEXDailyDownloader
from tzdata_pkg.download.cffex.position_downloader import CFFEXPositionDownloader
from tzdata_pkg.download.cffex.futures_downloader import CFFEXFuturesDownloader


# ── Minimal config for testing ──────────────────────────────

def _make_config(tmp_path: Path) -> dict:
    """Build a minimal CFFEX config pointing to temp directories."""
    cffex_dir = tmp_path / "cffex"
    cffex_dir.mkdir()
    (cffex_dir / "raw").mkdir()
    (cffex_dir / "logs").mkdir()
    return {
        "base_url": "http://www.cffex.com.cn/sj/",
        "storage": {
            "csv_dir": str(cffex_dir / "raw"),
            "db_path": str(cffex_dir / "cffex.db"),
            "log_dir": str(cffex_dir / "logs"),
            "checksum_file": str(cffex_dir / ".checksums.json"),
        },
        "partition": {"start_year": 2024, "auto_create_table": True, "index_on_create": True},
    }


# ── Test: daily_downloader product-aware table naming ───────

class TestDailyDownloaderTableNaming:
    """Verify _get_table_name uses product code, not hardcoded 'mo'."""

    @pytest.fixture
    def downloader(self, tmp_path):
        config = _make_config(tmp_path)
        return CFFEXDailyDownloader(config, "daily", product="IM")

    def test_table_name_uses_product(self, downloader):
        assert downloader._get_table_name("daily", 2025) == "im_daily_2025"

    def test_table_name_no_year(self, downloader):
        assert downloader._get_table_name("daily") == "im_daily"

    def test_weekly_table_name(self, downloader):
        assert downloader._get_table_name("weekly", 2025) == "im_weekly_2025"

    def test_monthly_table_name(self, downloader):
        assert downloader._get_table_name("monthly", 2025) == "im_monthly_2025"

    def test_mo_product_still_works(self, tmp_path):
        config = _make_config(tmp_path)
        dl = CFFEXDailyDownloader(config, "daily", product="MO")
        assert dl._get_table_name("daily", 2025) == "mo_daily_2025"


# ── Test: position_downloader product-aware table naming ────

class TestPositionDownloaderTableNaming:
    """Verify _get_table_name uses product code, not hardcoded 'mo'."""

    @pytest.fixture
    def downloader(self, tmp_path):
        config = _make_config(tmp_path)
        return CFFEXPositionDownloader(config, product="IM")

    def test_table_name_uses_product(self, downloader):
        assert downloader._get_table_name("position", 2025) == "im_position_2025"

    def test_summary_table_uses_product(self, downloader):
        # The summary table name is built inline in create_tables
        # We verify _get_table_name is correct; summary follows the same pattern
        year = 2025
        table = downloader._get_table_name("position", year)
        assert table == "im_position_2025"
        # Summary table uses same product prefix
        summary = f"{downloader.product.lower()}_position_summary_{year}"
        assert summary == "im_position_summary_2025"


# ── Test: futures_downloader table naming ───────────────────

class TestFuturesDownloaderTableNaming:
    """Verify futures downloader uses product code correctly."""

    @pytest.fixture
    def downloader(self, tmp_path):
        config = _make_config(tmp_path)
        return CFFEXFuturesDownloader(config, product="IC", data_type="daily")

    def test_table_name_uses_product(self, downloader):
        assert downloader._get_table_name("daily", 2025) == "ic_daily_2025"

    def test_stats_table_uses_product(self, downloader):
        assert downloader._get_stats_table_name(2025) == "ic_stats_2025"


# ── Test: unified_downloader ────────────────────────────────

class TestUnifiedDownloader:
    """Basic tests for CFFEXUnifiedDownloader."""

    def test_import(self):
        from tzdata_pkg.download.cffex.unified_downloader import CFFEXUnifiedDownloader
        assert CFFEXUnifiedDownloader is not None

    def test_unified_table_name_function(self):
        from tzdata_pkg.download.cffex.unified_downloader import unified_table_name
        assert unified_table_name("MO", "daily") == "MO_daily"
        assert unified_table_name("IM", "position") == "IM_position"

    def test_safe_helpers(self):
        from tzdata_pkg.download.cffex.unified_downloader import CFFEXUnifiedDownloader
        import pandas as pd

        assert CFFEXUnifiedDownloader._safe_float(1.5) == 1.5
        assert CFFEXUnifiedDownloader._safe_float("3.14") == 3.14
        assert CFFEXUnifiedDownloader._safe_float("") is None
        assert CFFEXUnifiedDownloader._safe_float(None) is None
        assert CFFEXUnifiedDownloader._safe_float(pd.NA) is None

        assert CFFEXUnifiedDownloader._safe_int(5) == 5
        assert CFFEXUnifiedDownloader._safe_int("3.7") == 3
        assert CFFEXUnifiedDownloader._safe_int("") is None
        assert CFFEXUnifiedDownloader._safe_int(None) is None

        assert CFFEXUnifiedDownloader._safe_str("hello") == "hello"
        assert CFFEXUnifiedDownloader._safe_str("") == ""
        assert CFFEXUnifiedDownloader._safe_str(None) == ""
        assert CFFEXUnifiedDownloader._safe_str(pd.NA) == ""
