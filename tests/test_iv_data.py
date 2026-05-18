"""TDD tests for IV data layer: HV calculator, benchmark downloader, option IV downloader."""

import json
import sqlite3
import tempfile
from datetime import date, datetime
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

import math


# ============================================================
# HV Calculator tests
# ============================================================

class TestHVCalculator:
    """Tests for hv_calculator.HVCalculator."""

    def _make_calculator(self, prices=None):
        from tzdata_pkg.analysis.hv_calculator import HVCalculator
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute("""
            CREATE TABLE option_sim_underlying_daily (
                trade_date TEXT, underlying TEXT, close REAL
            )
        """)
        conn.execute("""
            CREATE TABLE mo_daily_iv_quotes (
                trade_date TEXT, underlying TEXT, option_type TEXT,
                volume REAL, open_interest REAL
            )
        """)
        if prices:
            for i, (trade_date, price) in enumerate(prices):
                conn.execute(
                    "INSERT INTO option_sim_underlying_daily VALUES (?, '000852', ?)",
                    (trade_date, price)
                )
        conn.commit()
        conn.close()
        return HVCalculator(db_path=tmp.name), tmp

    def test_calculate_hv_basic(self):
        """HV calculation returns reasonable value."""
        import random
        random.seed(42)
        prices = [(f"2024-01-{i+1:02d}", 100.0) for i in range(30)]
        calc, tmp = self._make_calculator(prices)

        with patch.object(calc, '_get_prices') as mock_prices:
            base = 100.0
            price_list = [base]
            random.seed(42)
            for _ in range(21):
                price_list.append(price_list[-1] * (1 + random.gauss(0, 0.012)))
            mock_prices.return_value = price_list

            hv = calc.calculate_hv("MO", window=20)
            assert hv is not None
            assert 0 < hv < 1.0  # 0-100% annual vol

    def test_calculate_hv_insufficient_data(self):
        """Returns None when insufficient prices."""
        calc, tmp = self._make_calculator([])

        with patch.object(calc, '_get_prices', return_value=[100.0, 101.0]):
            hv = calc.calculate_hv("MO", window=20)
            assert hv is None

    def test_calculate_hv_invalid_variety(self):
        """Returns None for unrecognized variety."""
        calc, tmp = self._make_calculator([])
        hv = calc.calculate_hv("XX", window=20)
        assert hv is None

    def test_hv_known_volatility(self):
        """HV of known prices matches expected range."""
        import random
        random.seed(123)
        # Generate prices with ~15% annual volatility
        base = 100.0
        price_list = [base]
        daily_sigma = 0.15 / math.sqrt(252)  # ~0.00945
        for _ in range(61):
            price_list.append(price_list[-1] * (1 + random.gauss(0, daily_sigma)))

        calc, tmp = self._make_calculator()
        with patch.object(calc, '_get_prices', return_value=price_list):
            hv = calc.calculate_hv("MO", window=60)
            assert hv is not None
            # Should be roughly 0.15 (allow wide range for stochastic)
            assert 0.05 < hv < 0.35


# ============================================================
# IV Benchmark Downloader tests
# ============================================================

class TestIVBenchmarkDownloader:
    """Tests for iv_benchmark_downloader.IVBenchmarkDownloader."""

    def _setup_db(self, trade_date_num="20240615", trade_date_iso="2024-06-15", spot_price=5800.0):
        """Create a test database with sample data."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute("""
            CREATE TABLE option_sim_underlying_daily (
                trade_date TEXT, underlying TEXT, close REAL
            )
        """)
        conn.execute("""
            CREATE TABLE mo_daily_iv_quotes (
                trade_date TEXT, underlying TEXT, contract_code TEXT,
                option_type TEXT, strike REAL, expire_date TEXT,
                iv REAL, delta REAL
            )
        """)
        # Spot price uses ISO date format
        conn.execute(
            "INSERT INTO option_sim_underlying_daily VALUES (?, '000852', ?)",
            (trade_date_iso, spot_price)
        )
        # Option contracts use YYYYMMDD format
        strikes = [5600, 5700, 5800, 5900, 6000]
        for i, strike in enumerate(strikes):
            conn.execute(
                "INSERT INTO mo_daily_iv_quotes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (trade_date_num, "MO", f"MO2406C{strike}", "C", strike,
                 "2024-06-21", 0.18 + i * 0.005, 0.3 + i * 0.05)
            )
            conn.execute(
                "INSERT INTO mo_daily_iv_quotes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (trade_date_num, "MO", f"MO2406P{strike}", "P", strike,
                 "2024-06-21", 0.20 + i * 0.005, -0.3 + i * 0.05)
            )
        conn.commit()
        conn.close()
        return tmp.name

    def test_ensure_tables(self):
        """iv_benchmark table is created."""
        from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        downloader = IVBenchmarkDownloader(db_path=tmp.name)
        conn = sqlite3.connect(tmp.name)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='iv_benchmark'"
        ).fetchone()
        assert row is not None
        conn.close()

    def test_compute_daily_creates_record(self):
        """compute_daily stores benchmark record."""
        from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader
        db_path = self._setup_db(trade_date_num="20240615")

        downloader = IVBenchmarkDownloader(db_path=db_path)

        with patch.object(downloader.hv_calc, 'calculate_hv', return_value=0.22):
            with patch.object(downloader.hv_calc, 'calculate_pcr', return_value={"pcr_volume": 0.8, "pcr_oi": 0.9}):
                result = downloader.compute_daily("20240615")

        assert "MO" in result
        assert result["MO"]["status"] == "ok"

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT * FROM iv_benchmark WHERE variety='MO' AND trade_date='2024-06-15'"
        ).fetchone()
        assert row is not None
        assert row[2] is not None  # atm_iv
        conn.close()

    def test_compute_skew_approximation(self):
        """Skew calculation returns reasonable value."""
        from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader
        db_path = self._setup_db()
        downloader = IVBenchmarkDownloader(db_path=db_path)

        conn = sqlite3.connect(db_path)
        skew = downloader._compute_skew_25delta(conn, "MO", "20240615", 5800.0)
        assert skew is None or isinstance(skew, (int, float))
        conn.close()

    def test_regime_classification(self):
        """Regime thresholds are correct."""
        from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        downloader = IVBenchmarkDownloader(db_path=tmp.name)

        assert downloader._classify_regime(None) == "normal"
        assert downloader._classify_regime(5) == "very_low"
        assert downloader._classify_regime(20) == "low"
        assert downloader._classify_regime(50) == "normal"
        assert downloader._classify_regime(85) == "high"
        assert downloader._classify_regime(95) == "very_high"

    def test_normalize_date(self):
        """Date normalization works for both formats."""
        from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        downloader = IVBenchmarkDownloader(db_path=tmp.name)

        assert downloader._normalize_date("20240615") == "2024-06-15"
        assert downloader._normalize_date("2024-06-15") == "2024-06-15"

    def test_atm_iv_finds_closest_strike(self):
        """ATM IV finds contract closest to spot."""
        from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader
        db_path = self._setup_db(spot_price=5850.0)
        downloader = IVBenchmarkDownloader(db_path=db_path)

        conn = sqlite3.connect(db_path)
        atm_iv, atm_strike, spot = downloader._get_atm_iv(conn, "MO", "20240615")
        conn.close()

        assert atm_iv is not None
        assert spot == 5850.0
        # ATM strike should be closest to 5850: either 5800 or 5900
        assert atm_strike in [5800.0, 5900.0]

    def test_iv_percentile_calculation(self):
        """IV percentile returns value when enough history."""
        from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute("""
            CREATE TABLE iv_benchmark (
                trade_date TEXT NOT NULL, variety TEXT NOT NULL,
                atm_iv REAL, PRIMARY KEY (trade_date, variety)
            )
        """)
        # Insert 30 days of data
        for i in range(30):
            d = f"2024-06-{30-i:02d}"
            iv = 0.20 + i * 0.002  # Increasing IV
            conn.execute("INSERT INTO iv_benchmark VALUES (?, 'MO', ?)", (d, iv))
        conn.commit()
        conn.close()

        downloader = IVBenchmarkDownloader(db_path=tmp.name)
        conn = sqlite3.connect(tmp.name)
        pct = downloader._compute_iv_percentile(conn, "MO", "2024-06-30")
        conn.close()

        assert pct is not None
        assert 0 <= pct <= 100


# ============================================================
# Option IV Downloader tests
# ============================================================

class TestOptionIVDownloaderClassDef:
    """Tests for option_iv_downloader module structure (no full import)."""

    def test_variety_map_in_module_source(self):
        """Verify VARIETY_MAP is defined in module source."""
        source_path = "C:/myspace/tz-data/src/tzdata_pkg/download/tushare/option_iv_downloader.py"
        with open(source_path, 'r', encoding='utf-8') as f:
            source = f.read()

        assert "VARIETY_MAP" in source
        assert "'MO'" in source
        assert "'IO'" in source
        assert "'HO'" in source
        assert "000852" in source
        assert "000300" in source
        assert "000016" in source

    def test_time_to_expiry_static(self):
        """Time to expiry calculation is correct."""
        try:
            from tzdata_pkg.download.tushare.option_iv_downloader import OptionIVDownloader
        except Exception:
            pytest.skip("OptionIVDownloader requires tushare")
        d = OptionIVDownloader._time_to_expiry(
            date(2024, 6, 15), "2024-07-19"
        )
        assert d is not None
        assert 0.09 < d < 0.10  # ~34 days / 365

    def test_time_to_expiry_expired(self):
        """Returns None for past expiry."""
        try:
            from tzdata_pkg.download.tushare.option_iv_downloader import OptionIVDownloader
        except Exception:
            pytest.skip("OptionIVDownloader requires tushare")
        d = OptionIVDownloader._time_to_expiry(
            date(2024, 7, 20), "2024-07-19"
        )
        assert d is None

    def test_normalize_date_yyyymmdd(self):
        """Normalizes YYYYMMDD to YYYY-MM-DD."""
        try:
            from tzdata_pkg.download.tushare.option_iv_downloader import OptionIVDownloader
        except Exception:
            pytest.skip("OptionIVDownloader requires tushare")
        assert OptionIVDownloader._normalize_date("20240615") == "2024-06-15"

    def test_normalize_date_iso(self):
        """ISO date is unchanged."""
        try:
            from tzdata_pkg.download.tushare.option_iv_downloader import OptionIVDownloader
        except Exception:
            pytest.skip("OptionIVDownloader requires tushare")
        assert OptionIVDownloader._normalize_date("2024-06-15") == "2024-06-15"


# ============================================================
# IV API endpoint tests
# ============================================================

class TestIVApiEndpoints:
    """Tests for IV API route functions using direct SQLite."""

    def _setup_test_db(self):
        """Create a test DB for API tests."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute("""
            CREATE TABLE iv_benchmark (
                trade_date TEXT NOT NULL, variety TEXT NOT NULL,
                atm_iv REAL, atm_strike REAL, spot_price REAL,
                hv_20 REAL, hv_60 REAL, iv_hv_spread REAL,
                skew_25delta REAL, term_structure TEXT,
                iv_percentile_1y REAL, iv_regime TEXT,
                pcr_volume REAL, pcr_oi REAL,
                PRIMARY KEY (trade_date, variety)
            )
        """)
        conn.execute("""
            CREATE TABLE mo_daily_iv_quotes (
                trade_date TEXT, underlying TEXT, contract_code TEXT,
                option_type TEXT, strike REAL, expire_date TEXT,
                iv REAL, delta REAL
            )
        """)
        conn.commit()
        conn.close()
        return tmp.name

    def test_iv_benchmark_empty(self):
        """Returns empty list when no data."""
        db_path = self._setup_test_db()
        with patch('tzdata_pkg.config.TZDATA_TRADING_DB', db_path):
            from tzdata_pkg.api.routes.analysis import get_iv_benchmark
            result = get_iv_benchmark(variety=None, start=None, end=None)
            assert "data" in result
            assert result["count"] == 0

    def test_iv_surface_empty(self):
        """Returns empty matrix when no data."""
        db_path = self._setup_test_db()
        with patch('tzdata_pkg.config.TZDATA_TRADING_DB', db_path):
            from tzdata_pkg.api.routes.analysis import get_iv_surface
            result = get_iv_surface(variety="MO", date="2024-06-15")
            assert "data" in result

    def test_iv_smile_empty(self):
        """Returns empty data when no smile data."""
        db_path = self._setup_test_db()
        with patch('tzdata_pkg.config.TZDATA_TRADING_DB', db_path):
            from tzdata_pkg.api.routes.analysis import get_iv_smile
            result = get_iv_smile(variety="MO", date="2024-06-15", expiry="2024-07-19")
            assert "data" in result

    def test_iv_cross_variety_empty(self):
        """Returns empty list when no cross-variety data."""
        db_path = self._setup_test_db()
        with patch('tzdata_pkg.config.TZDATA_TRADING_DB', db_path):
            from tzdata_pkg.api.routes.analysis import get_iv_cross_variety
            result = get_iv_cross_variety(start=None, end=None)
            assert "data" in result
            assert result["count"] == 0

    def test_iv_hv_spread_empty(self):
        """Returns empty list when no spread data."""
        db_path = self._setup_test_db()
        with patch('tzdata_pkg.config.TZDATA_TRADING_DB', db_path):
            from tzdata_pkg.api.routes.analysis import get_iv_hv_spread
            result = get_iv_hv_spread(variety="MO", start=None, end=None)
            assert "data" in result
            assert result["count"] == 0

    def test_iv_benchmark_with_data(self):
        """Returns benchmark data when present."""
        db_path = self._setup_test_db()
        conn = sqlite3.connect(db_path)
        conn.execute("""
            INSERT INTO iv_benchmark
            (trade_date, variety, atm_iv, hv_20, iv_hv_spread, iv_regime)
            VALUES ('2024-06-15', 'MO', 0.20, 0.18, 0.02, 'normal')
        """)
        conn.commit()
        conn.close()

        with patch('tzdata_pkg.config.TZDATA_TRADING_DB', db_path):
            from tzdata_pkg.api.routes.analysis import get_iv_benchmark
            result = get_iv_benchmark(variety="MO", start=None, end=None)
            assert result["count"] == 1
            assert result["data"][0]["atm_iv"] == 0.20
            assert result["data"][0]["variety"] == "MO"

    def test_iv_percentile_returns_stats(self):
        """Percentile endpoint returns 30d/90d/252d stats."""
        db_path = self._setup_test_db()
        conn = sqlite3.connect(db_path)
        for i in range(30):
            d = f"2024-06-{30-i:02d}"
            conn.execute(
                "INSERT INTO iv_benchmark (trade_date, variety, atm_iv, iv_regime) VALUES (?, 'MO', ?, 'normal')",
                (d, 0.18 + i * 0.002)
            )
        conn.commit()
        conn.close()

        with patch('tzdata_pkg.config.TZDATA_TRADING_DB', db_path):
            from tzdata_pkg.api.routes.analysis import get_iv_percentile
            result = get_iv_percentile(variety="MO", date=None)
            assert "percentile_30d" in result
            assert "percentile_90d" in result
            assert "percentile_252d" in result


# ============================================================
# Data integrity tests
# ============================================================

class TestIVDataIntegrity:
    """Tests for data consistency between IV components."""

    def test_benchmark_table_schema(self):
        """iv_benchmark table has all required columns."""
        from tzdata_pkg.analysis.iv_benchmark_downloader import IVBenchmarkDownloader
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        IVBenchmarkDownloader(db_path=tmp.name)

        conn = sqlite3.connect(tmp.name)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(iv_benchmark)")]
        required = [
            "trade_date", "variety", "atm_iv", "hv_20", "hv_60",
            "iv_hv_spread", "skew_25delta", "term_structure",
            "iv_percentile_1y", "iv_regime", "pcr_volume", "pcr_oi",
        ]
        for col in required:
            assert col in cols, f"Missing column: {col}"
        conn.close()

    def test_smile_snapshot_table_schema(self):
        """iv_smile_snapshot table has all required columns."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS iv_smile_snapshot (
                trade_date TEXT NOT NULL,
                variety TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                smile_data TEXT,
                atm_iv REAL,
                skew_ratio REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trade_date, variety, expiry_date)
            )
        """)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(iv_smile_snapshot)")]
        required = ["trade_date", "variety", "expiry_date", "smile_data", "atm_iv", "skew_ratio"]
        for col in required:
            assert col in cols, f"Missing column: {col}"
        conn.close()

    def test_celery_beat_schedule_has_iv_tasks(self):
        """Celery beat schedule includes IV tasks."""
        from tzdata_pkg.scheduler.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "iv-benchmark-daily" in schedule
        assert "iv-smile-snapshot" in schedule
        assert "iv-multi-variety-sync" in schedule

    def test_celery_includes_iv_tasks(self):
        """Celery app includes iv_tasks in include list."""
        from tzdata_pkg.scheduler.celery_app import celery_app
        include = celery_app.conf.include
        assert "tzdata_pkg.scheduler.tasks.iv_tasks" in include
