"""Tests for SHFE connection pool."""

import tempfile
import shutil
from pathlib import Path

from tzdata_pkg.download.shfe.connection_pool import SQLitePool, SHFEConnectionPool, get_shfe_pool


class TestSQLitePool:
    def test_acquire_and_release(self):
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = str(Path(tmpdir) / "test.db")
            pool = SQLitePool(db_path, pool_size=2)
            conn = pool.acquire()
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            pool.release(conn)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_context_manager(self):
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = str(Path(tmpdir) / "test.db")
            pool = SQLitePool(db_path, pool_size=2)
            with pool.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            # Verify table exists
            with pool.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
                assert cursor.fetchone() is not None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_stats(self):
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = str(Path(tmpdir) / "test.db")
            pool = SQLitePool(db_path, pool_size=3)
            stats = pool.get_stats()
            assert "db_path" in stats
            assert "pool_size" in stats
            assert stats["pool_size"] == 3
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSHFEConnectionPool:
    def test_singleton(self):
        instance1 = SHFEConnectionPool.get_instance()
        instance2 = SHFEConnectionPool.get_instance()
        assert instance1 is instance2

    def test_initialize_and_get_pool(self):
        tmpdir = tempfile.mkdtemp()
        try:
            pool_manager = SHFEConnectionPool()
            pool_manager._pools = {}  # Reset
            db_path = str(Path(tmpdir) / "test.db")
            pool_manager.initialize({"shfe": db_path})
            pool = pool_manager.get_pool("shfe")
            assert isinstance(pool, SQLitePool)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_shfe_pool_convenience(self):
        # Reset singleton for clean test
        SHFEConnectionPool._instance = None
        tmpdir = tempfile.mkdtemp()
        try:
            db_path = str(Path(tmpdir) / "test.db")
            pool_manager = SHFEConnectionPool.get_instance()
            pool_manager.initialize({"shfe": db_path})
            pool = get_shfe_pool()
            assert isinstance(pool, SQLitePool)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
            SHFEConnectionPool._instance = None
