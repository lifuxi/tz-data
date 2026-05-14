"""TDD tests for tzdata.download.cffex.csv_parser module"""

import tempfile
from pathlib import Path
import pytest


class TestCFFEXParseResult:
    """Tests for CFFEXParseResult dataclass"""

    def test_create_result(self):
        """Can create parse result"""
        import pandas as pd
        from tzdata_pkg.download.cffex.csv_parser import CFFEXParseResult
        df = pd.DataFrame({"col": [1, 2]})
        result = CFFEXParseResult(
            data=df,
            stats={"total_volume": 100},
            trade_date="2026-04-08",
            data_type="daily",
            record_count=2,
            columns=["col"],
        )
        assert result.record_count == 2
        assert result.data_type == "daily"


class TestCFFEXCSVParser:
    """Tests for CFFEXCSVParser"""

    def setup_method(self):
        from tzdata_pkg.download.cffex.csv_parser import CFFEXCSVParser
        self.parser = CFFEXCSVParser()

    def test_detect_encoding_gbk(self):
        """Detects GBK encoding for CFFEX CSV"""
        # Use a longer GBK-encoded string for reliable detection
        content = (
            "交易日,合约代码,开盘价,最高价,"
            "最低价,收盘价,成交量,持仓量,结算价\n"
            "MO2604,3500,3600,3400,3550,100,2000,3520\n"
        ).encode("gbk")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(content)
            f.flush()
            encoding = self.parser.detect_encoding(f.name)
            assert encoding == "gbk"

    def test_detect_encoding_utf8(self):
        """Detects UTF-8 encoding"""
        content = "合约代码,开盘价,最高价\nMO2604,3.5,4.0\n".encode("utf-8")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(content)
            f.flush()
            encoding = self.parser.detect_encoding(f.name)
            assert encoding == "utf-8"

    def test_read_csv_utf8(self):
        """Reads UTF-8 CSV correctly"""
        content = "合约代码,开盘价,最高价\nMO2604,3500,3600\nMO2605,3400,3500\n".encode("utf-8")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
            f.write(content)
            f.flush()
            df = self.parser.read_csv(f.name)
            assert len(df) == 2
            assert "合约代码" in df.columns

    def test_standardize_columns_by_position(self):
        """Standardizes columns by position when count matches"""
        import pandas as pd
        df = pd.DataFrame({
            "A": ["MO2604"],
            "B": [3500],
            "C": [3600],
            "D": [3400],
            "E": [1000],
            "F": [50000],
            "G": [20000],
            "H": [100],
            "I": [3450],
            "J": [3480],
            "K": [3420],
            "L": [30],
            "M": [0.8],
            "N": [0.5],
        })
        result = self.parser.standardize_columns(df, {})
        assert "instrument_id" in result.columns
        assert "open_price" in result.columns
        assert "close_price" in result.columns

    def test_standardize_columns_by_mapping(self):
        """Standardizes columns by name mapping"""
        import pandas as pd
        df = pd.DataFrame({
            "合约代码": ["MO2604"],
            "开盘价": [3500],
            "最高价": [3600],
        })
        result = self.parser.standardize_columns(df, self.parser.DAILY_COLUMN_MAPPING)
        assert "instrument_id" in result.columns
        assert "open_price" in result.columns

    def test_extract_stats(self):
        """Extracts statistics from DataFrame"""
        import pandas as pd
        df = pd.DataFrame({
            "volume": [100, 200, 300],
            "turnover": [10000, 20000, 30000],
            "instrument_id": ["MO2604", "MO2605", "MO2606"],
        })
        stats = self.parser.extract_stats(df)
        assert stats["total_volume"] == 600
        assert stats["max_volume"] == 300
        assert stats["contract_count"] == 3

    def test_parse_daily_csv(self):
        """Parses daily CSV file end-to-end"""
        content = (
            "合约代码,开盘价,最高价,最低价,收盘价,成交量,持仓量,结算价\n"
            "MO2604,3500,3600,3400,3550,100,2000,3520\n"
            "MO2605,3400,3500,3300,3450,200,3000,3420\n"
        ).encode("utf-8")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
            f.write(content)
            f.flush()
            result = self.parser.parse_daily_csv(f.name, "2026-04-08")
            assert result.record_count == 2
            assert result.data_type == "daily"
            assert result.trade_date == "2026-04-08"
            assert "instrument_id" in result.data.columns

    def test_parse_position_csv(self):
        """Parses position ranking CSV"""
        content = (
            "合约代码,期货公司会员简称,多头持仓量,空头持仓量,多头增减,空头增减\n"
            "MO2604,中信期货,1000,800,100,50\n"
            "MO2604,永安期货,900,1100,-50,200\n"
        ).encode("utf-8")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
            f.write(content)
            f.flush()
            result = self.parser.parse_position_csv(f.name, "MO")
            assert result.data_type == "position"
            assert result.record_count == 2
            assert "net_position" in result.data.columns

    def test_parse_csv_dispatch(self):
        """parse_csv dispatches to correct parser"""
        content = "合约代码,开盘价,最高价,最低价,收盘价,成交量,持仓量,结算价\nMO2604,3500,3600,3400,3550,100,2000,3520\n".encode("utf-8")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
            f.write(content)
            f.flush()

            result = self.parser.parse_csv(f.name, "daily")
            assert result.data_type == "daily"

            result = self.parser.parse_csv(f.name, "weekly")
            assert result.data_type == "daily"  # weekly uses daily parser

            result = self.parser.parse_csv(f.name, "monthly")
            assert result.data_type == "monthly"

    def test_parse_csv_invalid_type(self):
        """parse_csv raises ValueError for invalid type"""
        with pytest.raises(ValueError):
            self.parser.parse_csv("nonexistent.csv", "invalid_type")

    def test_parse_empty_file(self):
        """Handles empty CSV gracefully"""
        content = "合约代码,开盘价\n".encode("utf-8")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
            f.write(content)
            f.flush()
            result = self.parser.parse_daily_csv(f.name)
            assert result.record_count == 0

    def test_convenience_function(self):
        """parse_cffex_csv convenience function works"""
        from tzdata_pkg.download.cffex.csv_parser import parse_cffex_csv
        content = "合约代码,开盘价,最高价,最低价,收盘价,成交量,持仓量,结算价\nMO2604,3500,3600,3400,3550,100,2000,3520\n".encode("utf-8")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as f:
            f.write(content)
            f.flush()
            result = parse_cffex_csv(f.name, "daily")
            assert result.record_count == 1
