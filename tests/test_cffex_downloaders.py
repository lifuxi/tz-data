"""Integration tests for CFFEX downloaders (daily, position, futures)."""

import tempfile
import shutil
from pathlib import Path
from datetime import date


def _make_config(tmpdir):
    db_path = Path(tmpdir) / "test.db"
    csv_dir = Path(tmpdir) / "raw"
    log_dir = Path(tmpdir) / "logs"
    checksum_file = Path(tmpdir) / ".checksums.json"
    return {
        "base_url": "http://www.cffex.com.cn/sj/",
        "storage": {
            "csv_dir": str(csv_dir),
            "db_path": str(db_path),
            "log_dir": str(log_dir),
            "checksum_file": str(checksum_file),
        },
        "download": {
            "timeout": 5, "max_retries": 1, "retry_delays": [0.01],
            "request_delay": 0.01, "user_agent": "TestAgent",
        },
        "batch": {"empty_file_threshold": 3},
        "partition": {"start_year": 2024, "index_on_create": True},
    }


class TestCFFEXDailyDownloader:
    def test_create_tables_and_save_data(self):
        from tzdata_pkg.download.cffex.daily_downloader import CFFEXDailyDownloader
        tmpdir = tempfile.mkdtemp()
        try:
            config = _make_config(tmpdir)
            downloader = CFFEXDailyDownloader(config, "daily", "MO")
            downloader.create_tables(2026)

            import pandas as pd
            from tzdata_pkg.download.cffex.csv_parser import CFFEXParseResult
            df = pd.DataFrame({
                "instrument_id": ["MO2604", "MO2605"],
                "open_price": [3500.0, 3400.0],
                "high_price": [3600.0, 3500.0],
                "low_price": [3400.0, 3300.0],
                "close_price": [3550.0, 3450.0],
                "settlement_price": [3520.0, 3420.0],
                "volume": [100, 200],
                "turnover": [10000.0, 20000.0],
                "open_interest": [2000, 3000],
                "oi_change": [100, 200],
                "strike_price": [None, None],
                "pre_settle": [3400.0, 3300.0],
                "change": [50.0, 100.0],
                "change_pct": [1.4, 2.9],
            })
            parse_result = CFFEXParseResult(
                data=df, stats={"total_volume": 300, "contract_count": 2},
                trade_date="2026-04-08", data_type="daily",
                record_count=2, columns=df.columns.tolist(),
            )
            count = downloader.save_to_database(parse_result)
            assert count == 2

            # Verify query
            dates = downloader.get_trade_dates(2026)
            assert "2026-04-08" in dates

            stats = downloader.get_statistics(year=2026)
            assert stats.get("contract_count") == 2
            downloader.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_invalid_data_type(self):
        tmpdir = tempfile.mkdtemp()
        try:
            config = _make_config(tmpdir)
            import pytest
            with pytest.raises(ValueError):
                from tzdata_pkg.download.cffex.daily_downloader import CFFEXDailyDownloader
                CFFEXDailyDownloader(config, "invalid")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestCFFEXFuturesDownloader:
    def test_create_tables_and_save_data(self):
        from tzdata_pkg.download.cffex.futures_downloader import CFFEXFuturesDownloader
        tmpdir = tempfile.mkdtemp()
        try:
            config = _make_config(tmpdir)
            downloader = CFFEXFuturesDownloader(config, "IM", "daily")
            downloader.create_tables(2026)

            import pandas as pd
            from tzdata_pkg.download.cffex.csv_parser import CFFEXParseResult
            df = pd.DataFrame({
                "instrument_id": ["IM2604", "IM2605", "MO2604"],  # MO should be filtered
                "open_price": [5500.0, 5400.0, 3500.0],
                "high_price": [5600.0, 5500.0, 3600.0],
                "low_price": [5400.0, 5300.0, 3400.0],
                "close_price": [5550.0, 5450.0, 3550.0],
                "settlement_price": [5520.0, 5420.0, 3520.0],
                "volume": [100, 200, 50],
                "turnover": [10000.0, 20000.0, 5000.0],
                "open_interest": [2000, 3000, 1000],
                "oi_change": [100, 200, 50],
            })
            parse_result = CFFEXParseResult(
                data=df, stats={"total_volume": 350, "contract_count": 3},
                trade_date="2026-04-08", data_type="daily",
                record_count=3, columns=df.columns.tolist(),
            )
            count = downloader.save_to_database(parse_result)
            assert count == 2  # Only IM contracts saved
            downloader.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_filter_futures_data(self):
        import pandas as pd
        from tzdata_pkg.download.cffex.futures_downloader import CFFEXFuturesDownloader
        tmpdir = tempfile.mkdtemp()
        try:
            config = _make_config(tmpdir)
            downloader = CFFEXFuturesDownloader(config, "IC", "daily")
            df = pd.DataFrame({
                "instrument_id": ["IC2604", "IM2604", "IC2605"],
                "volume": [100, 200, 300],
            })
            filtered = downloader.filter_futures_data(df)
            assert len(filtered) == 2
            assert all(id_.startswith("IC") for id_ in filtered["instrument_id"])
            downloader.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestCFFEXPositionDownloader:
    def test_create_tables_and_save_data(self):
        from tzdata_pkg.download.cffex.position_downloader import CFFEXPositionDownloader
        tmpdir = tempfile.mkdtemp()
        try:
            config = _make_config(tmpdir)
            downloader = CFFEXPositionDownloader(config, "MO")
            downloader.create_tables(2026)

            import pandas as pd
            from tzdata_pkg.download.cffex.csv_parser import CFFEXParseResult
            df = pd.DataFrame({
                "instrument_id": ["MO2604", "MO2604"],
                "member_name": ["中信期货", "永安期货"],
                "long_volume": [1000, 800],
                "short_volume": [900, 1100],
                "long_change": [100, -50],
                "short_change": [50, 200],
            })
            parse_result = CFFEXParseResult(
                data=df, stats={"total_long": 1800, "total_short": 2000},
                trade_date="2026-04-08", data_type="position",
                record_count=2, columns=df.columns.tolist(),
            )
            count = downloader.save_to_database(parse_result)
            assert count == 2

            positions = downloader.get_position_by_instrument("MO2604", "2026-04-08", 2026)
            assert len(positions) == 2

            top = downloader.get_top_members("2026-04-08", top_n=2, year=2026)
            assert "long" in top
            assert "short" in top
            downloader.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
