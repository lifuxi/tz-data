"""P0-4: FIFO trade matching correctness tests.

Tests the TradeMatcher class with 8 scenarios:
1. Simple full close
2. Multiple opens then single close (partial FIFO)
3. Single open then multiple closes
4. Bidirectional positions (long + short)
5. Option PnL calculation (premium-based)
6. Contract multiplier correctness
7. Unclosed positions (open only)
8. Empty data
"""
import sqlite3
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tzdata_pkg.maintenance.statements.trade_matcher import TradeMatcher, CONTRACT_MULTIPLIERS


def _create_test_db():
    """Create in-memory DB with trades + matcher target tables."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            instrument TEXT NOT NULL,
            exchange TEXT,
            product TEXT,
            direction TEXT NOT NULL,
            offset_flag TEXT NOT NULL,
            volume INTEGER NOT NULL,
            price REAL NOT NULL,
            commission REAL DEFAULT 0,
            premium REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS matched_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument TEXT, exchange TEXT, product TEXT,
            is_option INTEGER DEFAULT 0,
            open_trade_id INTEGER, open_date TEXT, open_price REAL, open_volume INTEGER,
            open_premium REAL DEFAULT 0, open_direction TEXT,
            close_trade_id INTEGER, close_date TEXT, close_price REAL, close_volume INTEGER,
            close_premium REAL, holding_days INTEGER,
            price_pnl REAL, premium_pnl REAL DEFAULT 0, multiplier INTEGER DEFAULT 1,
            money_pnl REAL, commission REAL DEFAULT 0, net_pnl REAL,
            status TEXT DEFAULT 'closed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS trade_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matched_trade_id INTEGER, instrument TEXT, is_option INTEGER,
            open_date TEXT, close_date TEXT, open_volume INTEGER, open_direction TEXT,
            money_pnl REAL, premium_pnl REAL, commission REAL, net_pnl REAL, pnl_ratio REAL,
            holding_days INTEGER,
            underlying TEXT, expiry TEXT, option_type TEXT, strike REAL,
            delta REAL, gamma REAL, vega REAL, theta REAL,
            strategy_type TEXT, strategy_id TEXT,
            close_year INTEGER, close_month INTEGER, close_quarter INTEGER
        );
    """)
    return conn


def _insert_trades(conn, trades):
    """Insert trades into the test DB."""
    for t in trades:
        t.setdefault("premium", 0)
    conn.executemany("""
        INSERT INTO trades (trade_date, instrument, exchange, product,
                           direction, offset_flag, volume, price, commission, premium)
        VALUES (:trade_date, :instrument, :exchange, :product,
                :direction, :offset_flag, :volume, :price, :commission, :premium)
    """, trades)
    conn.commit()


class TestSimpleFullClose:
    """Scenario 1: 1 lot open + 1 lot close = 1 matched trade."""

    def test_single_lot_match(self):
        conn = _create_test_db()
        _insert_trades(conn, [
            {"trade_date": "20250102", "instrument": "rb2505", "exchange": "SHFE",
             "product": "rb", "direction": "buy", "offset_flag": "open",
             "volume": 1, "price": 3500, "commission": 5},
            {"trade_date": "20250103", "instrument": "rb2505", "exchange": "SHFE",
             "product": "rb", "direction": "sell", "offset_flag": "close",
             "volume": 1, "price": 3600, "commission": 5},
        ])
        conn.close()

        # Use the real DB path override
        # We need to monkey-patch since TradeMatcher reads from a fixed DB
        matcher = TradeMatcher()
        matcher.conn = sqlite3.connect(":memory:")
        matcher.conn.row_factory = sqlite3.Row
        # Copy data to matcher's connection
        src = _create_test_db()
        _insert_trades(src, [
            {"trade_date": "20250102", "instrument": "rb2505", "exchange": "SHFE",
             "product": "rb", "direction": "buy", "offset_flag": "open",
             "volume": 1, "price": 3500, "commission": 5},
            {"trade_date": "20250103", "instrument": "rb2505", "exchange": "SHFE",
             "product": "rb", "direction": "sell", "offset_flag": "close",
             "volume": 1, "price": 3600, "commission": 5},
        ])

        matcher.conn = src
        results = matcher.match_trades()

        assert len(results) == 1
        mt = results[0]
        assert mt.open_price == 3500
        assert mt.close_price == 3600
        assert mt.open_volume == 1
        assert mt.open_direction == "long"
        # rb multiplier = 10, long: (close - open) * volume * multiplier
        assert mt.price_pnl == pytest.approx(100)  # 3600 - 3500
        assert mt.money_pnl == pytest.approx(1000)  # 100 * 1 * 10

        src.close()
        matcher.close()


class TestMultipleOpensSingleClose:
    """Scenario 2: Multiple opens (1+2+3) then single close of 3 lots.
    FIFO should match: 1 from open1 + 2 from open2 = 2 matched trades."""

    def test_fifo_partial_close(self):
        src = _create_test_db()
        _insert_trades(src, [
            {"trade_date": "20250102", "instrument": "IF2503", "exchange": "CFFEX",
             "product": "if", "direction": "buy", "offset_flag": "open",
             "volume": 1, "price": 4000, "commission": 10},
            {"trade_date": "20250103", "instrument": "IF2503", "exchange": "CFFEX",
             "product": "if", "direction": "buy", "offset_flag": "open",
             "volume": 2, "price": 4050, "commission": 20},
            {"trade_date": "20250103", "instrument": "IF2503", "exchange": "CFFEX",
             "product": "if", "direction": "buy", "offset_flag": "open",
             "volume": 3, "price": 4100, "commission": 30},
            {"trade_date": "20250106", "instrument": "IF2503", "exchange": "CFFEX",
             "product": "if", "direction": "sell", "offset_flag": "close",
             "volume": 3, "price": 4150, "commission": 10},
        ])

        matcher = TradeMatcher()
        matcher.conn = src
        results = matcher.match_trades()

        # 3 lots close: FIFO matches 1 from first open + 2 from second open = 2 matched
        assert len(results) == 2

        # First match: open @ 4000 (1 lot) closed @ 4150
        assert results[0].open_price == 4000
        assert results[0].open_volume == 1
        assert results[0].close_volume == 1
        assert results[0].price_pnl == pytest.approx(150)  # 4150 - 4000

        # Second match: open @ 4050 (2 lots) partially closed @ 4150
        assert results[1].open_price == 4050
        assert results[1].open_volume == 2
        assert results[1].close_volume == 2
        assert results[1].price_pnl == pytest.approx(100)  # 4150 - 4050

        # Remaining 3-lot open @ 4100 should NOT be matched
        src.close()
        matcher.close()


class TestSingleOpenMultipleCloses:
    """Scenario 3: Open 5 lots, close 2 + close 3 = 2 matched trades."""

    def test_open_split_into_closes(self):
        src = _create_test_db()
        _insert_trades(src, [
            {"trade_date": "20250102", "instrument": "m2505", "exchange": "DCE",
             "product": "m", "direction": "buy", "offset_flag": "open",
             "volume": 5, "price": 3000, "commission": 10},
            {"trade_date": "20250103", "instrument": "m2505", "exchange": "DCE",
             "product": "m", "direction": "sell", "offset_flag": "close",
             "volume": 2, "price": 3100, "commission": 5},
            {"trade_date": "20250106", "instrument": "m2505", "exchange": "DCE",
             "product": "m", "direction": "sell", "offset_flag": "close",
             "volume": 3, "price": 3200, "commission": 5},
        ])

        matcher = TradeMatcher()
        matcher.conn = src
        results = matcher.match_trades()

        assert len(results) == 2
        assert results[0].open_volume == 2
        assert results[0].close_volume == 2
        assert results[0].price_pnl == pytest.approx(100)  # 3100 - 3000

        assert results[1].open_volume == 3
        assert results[1].close_volume == 3
        assert results[1].price_pnl == pytest.approx(200)  # 3200 - 3000

        src.close()
        matcher.close()


class TestBidirectionalPositions:
    """Scenario 4: Same instrument, both long and short opens, matched separately."""

    def test_long_and_short_matched_separately(self):
        src = _create_test_db()
        _insert_trades(src, [
            # Long open
            {"trade_date": "20250102", "instrument": "cu2503", "exchange": "SHFE",
             "product": "cu", "direction": "buy", "offset_flag": "open",
             "volume": 2, "price": 68000, "commission": 20},
            # Short open
            {"trade_date": "20250102", "instrument": "cu2503", "exchange": "SHFE",
             "product": "cu", "direction": "sell", "offset_flag": "open",
             "volume": 1, "price": 68500, "commission": 10},
            # Close long
            {"trade_date": "20250103", "instrument": "cu2503", "exchange": "SHFE",
             "product": "cu", "direction": "sell", "offset_flag": "close",
             "volume": 2, "price": 69000, "commission": 20},
            # Close short
            {"trade_date": "20250106", "instrument": "cu2503", "exchange": "SHFE",
             "product": "cu", "direction": "buy", "offset_flag": "close",
             "volume": 1, "price": 68200, "commission": 10},
        ])

        matcher = TradeMatcher()
        matcher.conn = src
        results = matcher.match_trades()

        assert len(results) == 2

        long_match = next(r for r in results if r.open_direction == "long")
        short_match = next(r for r in results if r.open_direction == "short")

        # Long: buy@68000, sell@69000 => pnl = (69000-68000) * 2 * 5 = 10000
        assert long_match.price_pnl == pytest.approx(1000)
        assert long_match.multiplier == 5  # cu multiplier

        # Short: sell@68500, buy@68200 => pnl = (68500-68200) * 1 * 5 = 1500
        assert short_match.price_pnl == pytest.approx(300)
        assert short_match.open_direction == "short"

        src.close()
        matcher.close()


class TestOptionPnLCalculation:
    """Scenario 5: Option trades use premium PnL, not price PnL."""

    def test_call_option_pnl_from_premium(self):
        src = _create_test_db()
        _insert_trades(src, [
            # Buy call open
            {"trade_date": "20250102", "instrument": "MO2503-C-6500", "exchange": "CFFEX",
             "product": "mo", "direction": "buy", "offset_flag": "open",
             "volume": 1, "price": 200, "commission": 10, "premium": 15000},
            # Sell call close
            {"trade_date": "20250103", "instrument": "MO2503-C-6500", "exchange": "CFFEX",
             "product": "mo", "direction": "sell", "offset_flag": "close",
             "volume": 1, "price": 200, "commission": 10, "premium": 18000},
        ])

        matcher = TradeMatcher()
        matcher.conn = src
        results = matcher.match_trades()

        assert len(results) == 1
        mt = results[0]
        assert mt.is_option == 1
        # For options: price_pnl = 0, premium_pnl drives money_pnl
        assert mt.price_pnl == 0
        # Long call: close_premium - open_premium (absolute values)
        # open_prem_abs = 15000, close_prem_abs = 18000
        # prem_pnl = 18000 - 15000 = 3000
        assert mt.premium_pnl == pytest.approx(3000)
        assert mt.money_pnl == pytest.approx(3000)

        src.close()
        matcher.close()

    def test_put_option_pnl_from_premium(self):
        src = _create_test_db()
        _insert_trades(src, [
            # Sell put open (short)
            {"trade_date": "20250102", "instrument": "MO2503-P-6000", "exchange": "CFFEX",
             "product": "mo", "direction": "sell", "offset_flag": "open",
             "volume": 1, "price": 100, "commission": 10, "premium": 8000},
            # Buy put close
            {"trade_date": "20250103", "instrument": "MO2503-P-6000", "exchange": "CFFEX",
             "product": "mo", "direction": "buy", "offset_flag": "close",
             "volume": 1, "price": 100, "commission": 10, "premium": 5000},
        ])

        matcher = TradeMatcher()
        matcher.conn = src
        results = matcher.match_trades()

        assert len(results) == 1
        mt = results[0]
        assert mt.is_option == 1
        assert mt.open_direction == "short"
        # Short put: open_prem_abs - close_prem_abs = 8000 - 5000 = 3000 (profit)
        assert mt.premium_pnl == pytest.approx(3000)

        src.close()
        matcher.close()


class TestContractMultipliers:
    """Scenario 6: Verify different multipliers produce correct money_pnl."""

    def test_if_multiplier_300(self):
        """IF: multiplier=300, pnl = (close-open) * volume * 300"""
        src = _create_test_db()
        _insert_trades(src, [
            {"trade_date": "20250102", "instrument": "IF2503", "exchange": "CFFEX",
             "product": "if", "direction": "buy", "offset_flag": "open",
             "volume": 1, "price": 4000, "commission": 10},
            {"trade_date": "20250103", "instrument": "IF2503", "exchange": "CFFEX",
             "product": "if", "direction": "sell", "offset_flag": "close",
             "volume": 1, "price": 4010, "commission": 10},
        ])
        matcher = TradeMatcher()
        matcher.conn = src
        results = matcher.match_trades()
        assert len(results) == 1
        assert results[0].multiplier == 300
        assert results[0].money_pnl == pytest.approx(3000)  # 10 * 1 * 300
        src.close()
        matcher.close()

    def test_rb_multiplier_10(self):
        """rb: multiplier=10"""
        src = _create_test_db()
        _insert_trades(src, [
            {"trade_date": "20250102", "instrument": "rb2505", "exchange": "SHFE",
             "product": "rb", "direction": "buy", "offset_flag": "open",
             "volume": 2, "price": 3500, "commission": 5},
            {"trade_date": "20250103", "instrument": "rb2505", "exchange": "SHFE",
             "product": "rb", "direction": "sell", "offset_flag": "close",
             "volume": 2, "price": 3550, "commission": 5},
        ])
        matcher = TradeMatcher()
        matcher.conn = src
        results = matcher.match_trades()
        assert len(results) == 1
        assert results[0].multiplier == 10
        assert results[0].money_pnl == pytest.approx(1000)  # 50 * 2 * 10
        src.close()
        matcher.close()

    def test_mo_multiplier_100(self):
        """MO: multiplier=100 (options use premium, but multiplier still set)"""
        assert CONTRACT_MULTIPLIERS.get("mo") == 100


class TestUnclosedPositions:
    """Scenario 7: Open-only trades produce no matched trades."""

    def test_open_only_no_matches(self):
        src = _create_test_db()
        _insert_trades(src, [
            {"trade_date": "20250102", "instrument": "ag2506", "exchange": "SHFE",
             "product": "ag", "direction": "buy", "offset_flag": "open",
             "volume": 3, "price": 7500, "commission": 10},
            {"trade_date": "20250102", "instrument": "ag2506", "exchange": "SHFE",
             "product": "ag", "direction": "sell", "offset_flag": "open",
             "volume": 1, "price": 7550, "commission": 10},
        ])
        matcher = TradeMatcher()
        matcher.conn = src
        results = matcher.match_trades()
        assert len(results) == 0
        src.close()
        matcher.close()


class TestEmptyData:
    """Scenario 8: Empty trades table returns 0."""

    def test_empty_trades(self):
        src = _create_test_db()
        matcher = TradeMatcher()
        matcher.conn = src
        results = matcher.match_trades()
        assert len(results) == 0
        src.close()
        matcher.close()


class TestSaveAndPerformance:
    """Verify save_results and populate_performance work end-to-end."""

    def test_full_pipeline(self):
        src = _create_test_db()
        _insert_trades(src, [
            {"trade_date": "20250102", "instrument": "rb2505", "exchange": "SHFE",
             "product": "rb", "direction": "buy", "offset_flag": "open",
             "volume": 2, "price": 3500, "commission": 10},
            {"trade_date": "20250103", "instrument": "rb2505", "exchange": "SHFE",
             "product": "rb", "direction": "sell", "offset_flag": "close",
             "volume": 2, "price": 3600, "commission": 10},
        ])

        matcher = TradeMatcher()
        matcher.conn = src
        matcher.ensure_tables()

        results = matcher.match_trades()
        saved = matcher.save_results(results)
        perf = matcher.populate_performance(results)

        assert saved == 1
        assert perf == 1

        # Verify matched_trades row
        row = src.execute("SELECT COUNT(*) FROM matched_trades").fetchone()
        assert row[0] == 1

        # Verify trade_performance row
        row = src.execute("SELECT COUNT(*) FROM trade_performance").fetchone()
        assert row[0] == 1

        # Verify net_pnl is reasonable
        row = src.execute("SELECT net_pnl FROM matched_trades LIMIT 1").fetchone()
        # price_pnl = 100 * 2 = 200, money_pnl = 200 * 10 = 2000, commission ~20
        assert row[0] > 0  # net_pnl should be positive

        src.close()
        matcher.close()
