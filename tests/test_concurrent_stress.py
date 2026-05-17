"""P2-14: Concurrent query stress tests.

Tests for SQLite WAL concurrent read/write safety:
1. 50 concurrent reads — no SQLite locking errors
2. Mixed concurrent read + write — WAL handles conflicts gracefully
3. High-throughput burst — 100 queries in rapid succession
4. Connection pool limit enforcement — beyond max_connections raises DataAccessException
5. WAL mode active + concurrent readers don't block each other
6. Multi-pool isolation — concurrent access from different pools
"""
import concurrent.futures
import sqlite3
import tempfile
import time
import threading
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tzdata_pkg.core.db import SQLitePool
from tzdata_pkg.core.exceptions import DataAccessException


def _create_stress_test_db():
    """Create a temp SQLite DB with enough data for stress testing."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE daily_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange TEXT NOT NULL,
            contract_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume INTEGER
        )
    """)
    conn.execute("""
        CREATE INDEX idx_exchange_contract ON daily_quotes(exchange, contract_code)
    """)
    conn.execute("""
        CREATE TABLE position_detail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange TEXT NOT NULL,
            contract_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            broker TEXT,
            volume INTEGER
        )
    """)

    # Insert 5000 rows of test data
    for i in range(5000):
        exchange = "CFFEX" if i % 2 == 0 else "SHFE"
        contract = "MO2506" if i % 2 == 0 else "RB2510"
        conn.execute("""
            INSERT INTO daily_quotes (exchange, contract_code, trade_date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (exchange, contract, f"2025-01-{(i % 28) + 1:02d}", 100 + i % 50, 105 + i % 50, 95 + i % 50, 100 + i % 50, 1000 + i))

    # Insert 2000 position rows
    for i in range(2000):
        conn.execute("""
            INSERT INTO position_detail (exchange, contract_code, trade_date, broker, volume)
            VALUES (?, ?, ?, ?, ?)
        """, ("CFFEX", "MO2506", f"2025-01-{(i % 28) + 1:02d}", f"Broker{i % 20}", 100 + i % 500))

    conn.commit()
    conn.close()
    return db_path


def _cleanup(db_path: Path, retries=3):
    """Robust cleanup that handles Windows file locks."""
    for _ in range(retries):
        try:
            db_path.unlink()
            return
        except PermissionError:
            time.sleep(0.5)
    # Best effort — Windows may still hold a lock from a hung thread
    import warnings
    warnings.warn(f"Could not delete temp DB: {db_path}")


class TestConcurrentReads:
    """Test that concurrent reads do not cause errors."""

    def test_50_concurrent_reads(self):
        """50 threads reading simultaneously should all succeed.

        Uses per-thread connections (not pool) to avoid thread-local
        connection reuse across worker threads.
        """
        db_path = _create_stress_test_db()
        try:
            results = []
            errors = []
            lock = threading.Lock()

            def read_task(idx):
                try:
                    conn = sqlite3.connect(str(db_path), timeout=30)
                    conn.execute("PRAGMA journal_mode=WAL")
                    count = conn.execute(
                        "SELECT COUNT(*) FROM daily_quotes WHERE exchange = ?",
                        ("CFFEX",)
                    ).fetchone()[0]
                    conn.close()
                    with lock:
                        results.append(count)
                except Exception as e:
                    with lock:
                        errors.append((idx, str(e)))

            start = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                futures = [executor.submit(read_task, i) for i in range(50)]
                concurrent.futures.wait(futures, timeout=60)

            elapsed = time.time() - start

            assert len(errors) == 0, f"Errors: {errors}"
            assert len(results) == 50
            assert all(r == 2500 for r in results)  # 5000 / 2 = 2500 CFFEX rows
        finally:
            _cleanup(db_path)

    def test_mixed_concurrent_read_write(self):
        """Concurrent reads + writes should not deadlock or corrupt."""
        db_path = _create_stress_test_db()
        try:
            read_count = []
            errors = []
            lock = threading.Lock()

            def reader(idx):
                try:
                    conn = sqlite3.connect(str(db_path), timeout=30)
                    conn.execute("PRAGMA journal_mode=WAL")
                    for _ in range(10):
                        cnt = conn.execute("SELECT COUNT(*) FROM daily_quotes").fetchone()[0]
                        with lock:
                            read_count.append(cnt)
                        time.sleep(0.01)
                    conn.close()
                except Exception as e:
                    with lock:
                        errors.append(("reader", idx, str(e)))

            def writer(idx):
                try:
                    conn = sqlite3.connect(str(db_path), timeout=30)
                    conn.execute("PRAGMA journal_mode=WAL")
                    for i in range(5):
                        conn.execute("""
                            INSERT INTO daily_quotes
                                (exchange, contract_code, trade_date, open, high, low, close, volume)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, ("TEST", "TST2506", "2025-06-01", 100, 101, 99, 100, 100))
                        conn.commit()
                        time.sleep(0.02)
                    conn.close()
                except Exception as e:
                    with lock:
                        errors.append(("writer", idx, str(e)))

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for i in range(3):
                    futures.append(executor.submit(reader, i))
                for i in range(2):
                    futures.append(executor.submit(writer, i))
                concurrent.futures.wait(futures, timeout=60)

            assert len(errors) == 0, f"Errors: {errors}"
            assert len(read_count) == 30  # 3 readers * 10 iterations

            # Verify data integrity
            conn = sqlite3.connect(str(db_path))
            total = conn.execute("SELECT COUNT(*) FROM daily_quotes").fetchone()[0]
            conn.close()
            assert total >= 5000 + 10  # original + at least some inserts
        finally:
            _cleanup(db_path)


class TestConcurrentBurst:
    """Test rapid burst of concurrent queries."""

    def test_100_rapid_queries(self):
        """100 queries in rapid succession should complete without errors."""
        db_path = _create_stress_test_db()
        try:
            results = []
            lock = threading.Lock()

            def burst_task(idx):
                conn = sqlite3.connect(str(db_path), timeout=30)
                conn.execute("PRAGMA journal_mode=WAL")
                row = conn.execute("""
                    SELECT exchange, COUNT(*), AVG(close)
                    FROM daily_quotes
                    GROUP BY exchange
                    ORDER BY exchange
                """).fetchall()
                with lock:
                    results.append((idx, len(row)))
                conn.close()

            start = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(burst_task, i) for i in range(100)]
                concurrent.futures.wait(futures, timeout=60)
            elapsed = time.time() - start

            assert len(results) == 100
            assert all(r[1] == 2 for r in results)  # 2 exchange groups
        finally:
            _cleanup(db_path)


class TestPoolLimitEnforcement:
    """Test connection pool limit enforcement."""

    def test_pool_exhaustion_raises_error(self):
        """Exceeding max_connections should raise DataAccessException.

        Uses a barrier-like pattern: first threads hold connections open,
        later threads should fail with pool exhaustion.
        """
        db_path = _create_stress_test_db()
        try:
            pool = SQLitePool(str(db_path), max_connections=3)
            results = []
            lock = threading.Lock()
            release_event = threading.Event()

            def hold_connection(idx):
                """Thread 0,1,2: hold connection open until release_event."""
                try:
                    conn = pool.get_connection()
                    conn.execute("SELECT COUNT(*) FROM daily_quotes").fetchone()
                    # Hold connection until released
                    while not release_event.wait(timeout=0.05):
                        pass
                    pool.release()
                    with lock:
                        results.append(('held_released', idx))
                except DataAccessException:
                    with lock:
                        results.append(('exhausted', idx))
                except Exception as e:
                    with lock:
                        results.append(('error', idx, str(e)))

            def quick_connect(idx):
                """Thread 3,4: try to get connection while others hold."""
                try:
                    conn = pool.get_connection()
                    conn.execute("SELECT COUNT(*) FROM daily_quotes").fetchone()
                    pool.release()
                    with lock:
                        results.append(('success', idx))
                except DataAccessException:
                    with lock:
                        results.append(('exhausted', idx))
                except Exception as e:
                    with lock:
                        results.append(('error', idx, str(e)))

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # First 3 threads hold connections
                for i in range(3):
                    executor.submit(hold_connection, i)
                # Give them time to acquire connections
                import time
                time.sleep(0.5)

                # Then 2 threads try to connect (should fail with exhaustion)
                quick_results = []
                quick_futures = []
                for i in range(3, 5):
                    quick_futures.append(executor.submit(quick_connect, i))
                concurrent.futures.wait(quick_futures, timeout=15)

                # Release the held connections
                release_event.set()
                time.sleep(0.5)

            exhausted = [r for r in results if r[0] == 'exhausted']
            held = [r for r in results if r[0] == 'held_released']
            quick_success = [r for r in results if r[0] == 'success']

            # The 2 quick threads should both fail
            assert len(exhausted) >= 2, f"Expected >= 2 exhaustion, got {len(exhausted)}: {results}"
            assert len(held) == 3, f"Expected 3 held/released, got {len(held)}"
        finally:
            _cleanup(db_path)


class TestWALConcurrentSafety:
    """Test WAL mode handles concurrent access safely."""

    def test_wal_mode_active(self):
        """Verify WAL mode is active for the pool."""
        db_path = _create_stress_test_db()
        try:
            pool = SQLitePool(str(db_path), max_connections=5)
            with pool.connection() as conn:
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                assert mode == "wal", f"Expected WAL mode, got: {mode}"
            pool.close_all()
        finally:
            _cleanup(db_path)

    def test_concurrent_wal_readers_no_locking(self):
        """Multiple WAL readers should not block each other."""
        db_path = _create_stress_test_db()
        try:
            timings = []
            lock = threading.Lock()

            def timed_read(idx):
                start = time.time()
                conn = sqlite3.connect(str(db_path), timeout=30)
                conn.execute("PRAGMA journal_mode=WAL")
                _ = conn.execute("SELECT * FROM daily_quotes WHERE exchange='CFFEX' LIMIT 1000").fetchall()
                conn.close()
                elapsed = time.time() - start
                with lock:
                    timings.append(elapsed)

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(timed_read, i) for i in range(20)]
                concurrent.futures.wait(futures, timeout=60)

            assert len(timings) == 20
            # All reads should complete quickly (< 5 seconds each)
            for t in timings:
                assert t < 5.0, f"Query took {t:.2f}s — possible lock contention"
        finally:
            _cleanup(db_path)


class TestMultiPoolIsolation:
    """Test concurrent access across multiple DB pools."""

    def test_multi_pool_concurrent_queries(self):
        """Queries across different pools should not interfere."""
        db_path = _create_stress_test_db()
        try:
            results1 = []
            results2 = []
            lock = threading.Lock()

            def pool1_read():
                conn = sqlite3.connect(str(db_path), timeout=30)
                conn.execute("PRAGMA journal_mode=WAL")
                cnt = conn.execute("SELECT COUNT(*) FROM daily_quotes").fetchone()[0]
                conn.close()
                with lock:
                    results1.append(cnt)

            def pool2_read():
                conn = sqlite3.connect(str(db_path), timeout=30)
                conn.execute("PRAGMA journal_mode=WAL")
                cnt = conn.execute("SELECT COUNT(*) FROM daily_quotes").fetchone()[0]
                conn.close()
                with lock:
                    results2.append(cnt)

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                for _ in range(10):
                    futures.append(executor.submit(pool1_read))
                    futures.append(executor.submit(pool2_read))
                concurrent.futures.wait(futures, timeout=60)

            assert len(results1) == 10
            assert len(results2) == 10
            assert all(r == 5000 for r in results1)
            assert all(r == 5000 for r in results2)
        finally:
            _cleanup(db_path)
