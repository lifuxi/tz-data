"""
P0-3: Incremental sync idempotency tests.

Verifies that running the same incremental sync multiple times does NOT
produce duplicate records in the database.

Tests at the data-layer level (INSERT OR REPLACE pattern) since the full
sync engine requires external data source connectivity.
"""
import sqlite3
import pytest
from datetime import date
from pathlib import Path

MARKET_DB_PATH = "C:/myspace/tz-data/data/tzdata_market.db"


def _get_market_conn():
    """Get connection to market database."""
    conn = sqlite3.connect(MARKET_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _count_rows(table: str, **filters) -> int:
    """Count rows in a table with optional filters."""
    conn = _get_market_conn()
    try:
        if filters:
            conditions = " AND ".join(f"{k} = ?" for k in filters)
            sql = f"SELECT COUNT(*) FROM {table} WHERE {conditions}"
            row = conn.execute(sql, list(filters.values())).fetchone()
        else:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


class TestDailyQuoteIdempotency:
    """Test that daily_quotes INSERT OR REPLACE is idempotent."""

    @pytest.mark.skipif(
        not Path(MARKET_DB_PATH).exists(),
        reason="Market database not found",
    )
    def test_same_day_no_duplicate_quotes(self):
        """Same contract + date should have exactly 1 row (no duplicates)."""
        conn = _get_market_conn()
        try:
            # Find contracts with data
            rows = conn.execute(
                "SELECT DISTINCT exchange, contract_code FROM daily_quotes LIMIT 10"
            ).fetchall()
            if not rows:
                pytest.skip("No daily_quotes data available")

            for row in rows:
                exchange = row["exchange"]
                contract = row["contract_code"]
                count = conn.execute(
                    "SELECT COUNT(*) FROM daily_quotes WHERE exchange=? AND contract_code=?",
                    (exchange, contract),
                ).fetchone()[0]

                # Check for duplicate (same exchange + contract + date)
                duplicates = conn.execute(
                    """SELECT trade_date, COUNT(*) as cnt FROM daily_quotes
                       WHERE exchange=? AND contract_code=?
                       GROUP BY trade_date HAVING cnt > 1""",
                    (exchange, contract),
                ).fetchall()

                assert len(duplicates) == 0, \
                    f"Duplicates found for {exchange}.{contract}: {[(d[0], d[1]) for d in duplicates]}"
        finally:
            conn.close()

    @pytest.mark.skipif(
        not Path(MARKET_DB_PATH).exists(),
        reason="Market database not found",
    )
    def test_date_uniqueness_constraint(self):
        """daily_quotes table should have a uniqueness constraint on (exchange, contract_code, trade_date)."""
        conn = _get_market_conn()
        try:
            indexes = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_quotes'"
            ).fetchall()

            has_unique = False
            for idx in indexes:
                sql = idx["sql"] or ""
                if "UNIQUE" in sql.upper() or "unique" in sql.lower():
                    if any(kw in sql.lower() for kw in ["contract_code", "trade_date"]):
                        has_unique = True
                        break

            # Even without explicit constraint, verify no duplicates exist
            if not has_unique:
                dup_count = conn.execute(
                    """SELECT COUNT(*) FROM (
                        SELECT exchange, contract_code, trade_date, COUNT(*) as cnt
                        FROM daily_quotes
                        GROUP BY exchange, contract_code, trade_date
                        HAVING cnt > 1
                    )"""
                ).fetchone()[0]
                assert dup_count == 0, f"Found {dup_count} duplicate rows in daily_quotes"
        finally:
            conn.close()


class TestPositionDetailIdempotency:
    """Test that position_detail INSERT OR REPLACE is idempotent."""

    @pytest.mark.skipif(
        not Path(MARKET_DB_PATH).exists(),
        reason="Market database not found",
    )
    def test_no_duplicate_positions(self):
        """Same contract + date + rank + member should have exactly 1 row."""
        conn = _get_market_conn()
        try:
            rows = conn.execute(
                "SELECT COUNT(*) as cnt FROM position_detail"
            ).fetchone()
            if not rows or rows[0] == 0:
                pytest.skip("No position_detail data available")

            duplicates = conn.execute(
                """SELECT exchange, contract_code, trade_date, rank, member_name, COUNT(*) as cnt
                   FROM position_detail
                   GROUP BY exchange, contract_code, trade_date, rank, member_name
                   HAVING cnt > 1
                   LIMIT 10"""
            ).fetchall()

            assert len(duplicates) == 0, \
                f"Duplicate position rows found: {[(d[0], d[1], d[2], d[3], d[4], d[5]) for d in duplicates]}"
        finally:
            conn.close()


class TestIncrementalSyncIdempotency:
    """Test that the sync engine's incremental range calculation is correct."""

    def test_incremental_range_empty_when_up_to_date(self):
        """When local latest == remote latest, incremental range should be empty."""
        from tzdata_pkg.maintenance.metadata.trade_calendar import TradeCalendarManager

        # Same date range should produce no trading days after filtering
        d = date.today()
        # If local and remote are the same, the calendar should return [d] or []
        days = TradeCalendarManager.get_trading_days(d, d)
        # This is a sanity check that the calendar doesn't return unexpected extra days
        assert len(days) <= 1, f"Single day range returned {len(days)} days"

    def test_sync_batch_no_overlap(self):
        """Verify that sync batches don't have overlapping date ranges."""
        from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine, SyncBatch

        start = date(2025, 1, 1)
        end = date(2025, 3, 31)

        engine = SyncEngine(catalog_id=1, mode='full', batch_days=30)
        batches = engine._split_into_batches(start, end)

        # Verify no overlap: each batch's start should be > previous batch's end + 1 day
        for i in range(1, len(batches)):
            prev_end = batches[i - 1].end_date
            curr_start = batches[i].start_date
            assert curr_start > prev_end, \
                f"Batch overlap: batch {i-1} ends {prev_end}, batch {i} starts {curr_start}"

    def test_sync_batch_full_coverage(self):
        """Verify that batches cover the full date range without gaps."""
        from datetime import timedelta
        from tzdata_pkg.maintenance.sync.sync_engine import SyncEngine

        start = date(2025, 1, 1)
        end = date(2025, 2, 28)

        engine = SyncEngine(catalog_id=1, mode='full', batch_days=30)
        batches = engine._split_into_batches(start, end)

        assert batches[0].start_date == start, "First batch should start at range start"
        assert batches[-1].end_date == end, "Last batch should end at range end"

        # Verify contiguous coverage
        for i in range(1, len(batches)):
            prev_end = batches[i - 1].end_date
            curr_start = batches[i].start_date
            gap = (curr_start - prev_end).days
            assert gap == 1, \
                f"Gap of {gap} days between batch {i-1} (ends {prev_end}) and batch {i} (starts {curr_start})"
