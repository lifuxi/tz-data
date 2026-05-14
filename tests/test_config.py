"""TDD tests for tzdata.config module"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestGetDataDir:
    """Tests for get_data_dir()"""

    def test_default_data_dir(self):
        """When TZ_DATA_DIR is not set, return default path (Windows: C:\\myspace\\tz-data\\data)"""
        from tzdata_pkg.config import get_data_dir

        # Clear env var if set
        original = os.environ.pop("TZ_DATA_DIR", None)
        try:
            data_dir = get_data_dir()
            assert isinstance(data_dir, Path)
            assert str(data_dir) == r"C:\myspace\tz-data\data"
        finally:
            if original:
                os.environ["TZ_DATA_DIR"] = original

    def test_env_var_override(self):
        """When TZ_DATA_DIR is set, use that path"""
        # Must patch before import
        with patch.dict(os.environ, {"TZ_DATA_DIR": "D:/my-custom/data"}):
            # Force re-import by clearing cached module
            import sys
            if "tzdata.config" in sys.modules:
                del sys.modules["tzdata.config"]
            from tzdata_pkg.config import get_data_dir
            data_dir = get_data_dir()
            assert Path(str(data_dir)) == Path("D:/my-custom/data")


class TestGetCffexConfig:
    """Tests for get_cffex_config()"""

    def test_returns_dict(self):
        """get_cffex_config returns a dict with expected keys"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"TZ_DATA_DIR": tmpdir}):
                import sys
                if "tzdata_pkg.config" in sys.modules:
                    del sys.modules["tzdata_pkg.config"]
                from tzdata_pkg.config import get_cffex_config
                config = get_cffex_config()
                assert isinstance(config, dict)
                assert "base_url" in config
                assert "storage" in config
                assert "download" in config
                assert "products" in config
                assert "data_types" in config

    def test_storage_paths_use_data_dir(self):
        """Storage paths are derived from TZ_DATA_DIR"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"TZ_DATA_DIR": tmpdir}):
                import sys
                if "tzdata_pkg.config" in sys.modules:
                    del sys.modules["tzdata_pkg.config"]
                from tzdata_pkg.config import get_cffex_config
                config = get_cffex_config()
                storage = config["storage"]
                assert tmpdir in storage["csv_dir"]
                assert tmpdir in storage["db_path"]
                assert tmpdir in storage["log_dir"]


class TestGetShfeConfig:
    """Tests for get_shfe_config()"""

    def test_returns_dict(self):
        """get_shfe_config returns a dict with expected keys"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"TZ_DATA_DIR": tmpdir}):
                import sys
                if "tzdata_pkg.config" in sys.modules:
                    del sys.modules["tzdata_pkg.config"]
                from tzdata_pkg.config import get_shfe_config
                config = get_shfe_config()
                assert isinstance(config, dict)
                assert "storage" in config
                assert "products" in config


class TestDatabasePaths:
    """Tests for database path resolution"""

    def test_cffex_db_path(self):
        """CFFEX_DB path is derived from data dir"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"TZ_DATA_DIR": tmpdir}):
                import sys
                if "tzdata_pkg.config" in sys.modules:
                    del sys.modules["tzdata_pkg.config"]
                from tzdata_pkg.config import CFFEX_DB
                assert str(CFFEX_DB).startswith(tmpdir)
                assert "cffex.db" in str(CFFEX_DB)

    def test_shfe_db_path(self):
        """SHFE_DB path is derived from data dir"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"TZ_DATA_DIR": tmpdir}):
                import sys
                if "tzdata_pkg.config" in sys.modules:
                    del sys.modules["tzdata_pkg.config"]
                from tzdata_pkg.config import SHFE_DB
                assert str(SHFE_DB).startswith(tmpdir)
                assert "shfe.db" in str(SHFE_DB)
