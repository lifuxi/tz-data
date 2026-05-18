"""
SQLite → QuestDB historical data migration script.

Migrates existing market data from tzdata_market.db (SQLite) into QuestDB
time-series tables:
  - minute_quotes → future_minute (1min + resampled multi-frequency)
  - daily_quotes → daily_quotes

Usage:
    python migrations/sqlite_to_questdb.py dry-run    # Preview counts
    python migrations/sqlite_to_questdb.py run        # Execute migration
    python migrations/sqlite_to_questdb.py verify     # Verify consistency
"""
import sys
import os
import time

# Allow import from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from tzdata_pkg.storage.db_registry import DBRegistry

BATCH_SIZE = 10000


def extract_product(contract_code: str) -> str:
    """Extract product code from contract (e.g. IM2506 → IM, IF0 → IF)."""
    import re
    m = re.match(r"^([A-Z]+)", contract_code)
    return m.group(1) if m else contract_code


def build_timestamp(trade_date: str, trade_time: str = "00:00:00") -> str:
    """Build QuestDB UTC timestamp."""
    if len(trade_date) == 8 and trade_date.isdigit():
        trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
    if len(trade_time) == 5:
        trade_time += ":00"
    return f"{trade_date}T{trade_time}.000000Z"


def dry_run():
    """Preview data counts that would be migrated."""
    pool = DBRegistry().get_pool("market")
    with pool.connection() as conn:
        counts = {}
        for table in ["minute_quotes", "daily_quotes"]:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0] if row else 0

        # Breakdown by frequency
        freq_counts = conn.execute(
            "SELECT frequency, COUNT(*) FROM minute_quotes GROUP BY frequency"
        ).fetchall()

        # Breakdown by contract
        contract_counts = conn.execute(
            "SELECT contract_code, COUNT(*) FROM minute_quotes GROUP BY contract_code"
        ).fetchall()

    print("=== Migration Preview (dry-run) ===")
    print(f"minute_quotes: {counts['minute_quotes']} rows")
    print(f"daily_quotes:  {counts['daily_quotes']} rows")

    if freq_counts:
        print("\nMinute data by frequency:")
        for freq, cnt in freq_counts:
            print(f"  {freq}: {cnt:,}")

    if contract_counts:
        print("\nMinute data by contract:")
        for code, cnt in contract_counts:
            print(f"  {code}: {cnt:,}")

    # Check QuestDB connectivity
    try:
        qdb = DBRegistry().get_questdb_connection()
        cur = qdb.cursor()
        for table in ["future_minute", "daily_quotes"]:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row = cur.fetchone()
                print(f"\nQuestDB {table}: {row[0]} rows (existing)")
            except Exception:
                print(f"\nQuestDB {table}: table does not exist yet")
    except Exception as e:
        print(f"\nQuestDB connection: {e}")


def migrate_minute_quotes():
    """Migrate minute_quotes → future_minute."""
    pool = DBRegistry().get_pool("market")
    qdb = DBRegistry().get_questdb_connection()

    with pool.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM minute_quotes").fetchone()[0]

    if total == 0:
        print("No minute data to migrate.")
        return 0

    print(f"Migrating {total:,} minute quotes to QuestDB (batch_size={BATCH_SIZE})...")
    offset = 0
    inserted = 0
    skipped = 0
    start = time.time()

    with pool.connection() as conn:
        while offset < total:
            cursor = conn.execute(
                "SELECT exchange, contract_code, trade_date, trade_time, "
                "frequency, open, high, low, close, volume, turnover, "
                "open_interest, vwap, source "
                "FROM minute_quotes ORDER BY id LIMIT ? OFFSET ?",
                (BATCH_SIZE, offset),
            )
            rows = cursor.fetchall()
            if not rows:
                break

            cur = qdb.cursor()
            for row in rows:
                ts = build_timestamp(row[2], row[3])
                product = extract_product(row[1])
                try:
                    cur.execute("""
                        INSERT INTO future_minute
                            (ts, exchange, contract_code, product_code,
                             open, high, low, close,
                             volume, turnover, open_interest, source)
                        VALUES
                            (CAST(%s AS TIMESTAMP), %s, %s, %s,
                             %s, %s, %s, %s,
                             %s, %s, %s, %s)
                    """, (
                        ts, row[0], row[1], product,
                        row[5], row[6], row[7], row[8],
                        row[9], row[10], row[11], row[13],
                    ))
                    inserted += 1
                except Exception:
                    # Deduplicate: row may already exist
                    skipped += 1

            offset += len(rows)
            pct = min(100, offset / total * 100)
            print(f"  {offset:,}/{total:,} ({pct:.0f}%) — inserted: {inserted:,}, skipped: {skipped:,}")

    elapsed = time.time() - start
    print(f"Minute quotes migrated: {inserted:,} inserted, {skipped:,} skipped in {elapsed:.1f}s")
    return inserted


def migrate_daily_quotes():
    """Migrate daily_quotes → daily_quotes (QuestDB)."""
    pool = DBRegistry().get_pool("market")
    qdb = DBRegistry().get_questdb_connection()

    with pool.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM daily_quotes").fetchone()[0]

    if total == 0:
        print("No daily data to migrate.")
        return 0

    print(f"Migrating {total:,} daily quotes to QuestDB (batch_size={BATCH_SIZE})...")
    offset = 0
    inserted = 0
    skipped = 0
    start = time.time()

    with pool.connection() as conn:
        while offset < total:
            cursor = conn.execute(
                "SELECT exchange, contract_code, trade_date, "
                "open, high, low, close, settle, prev_settle, "
                "volume, turnover, open_interest, "
                "daily_change, daily_change_pct, amplitude, source "
                "FROM daily_quotes ORDER BY id LIMIT ? OFFSET ?",
                (BATCH_SIZE, offset),
            )
            rows = cursor.fetchall()
            if not rows:
                break

            cur = qdb.cursor()
            for row in rows:
                ts = build_timestamp(row[2])
                product = extract_product(row[1])
                try:
                    cur.execute("""
                        INSERT INTO daily_quotes
                            (ts, exchange, contract_code, product_code,
                             open, high, low, close, settle, prev_settle,
                             volume, turnover, open_interest,
                             daily_change, daily_change_pct, amplitude,
                             source)
                        VALUES
                            (CAST(%s AS TIMESTAMP), %s, %s, %s,
                             %s, %s, %s, %s, %s, %s,
                             %s, %s, %s,
                             %s, %s, %s, %s)
                    """, (
                        ts, row[0], row[1], product,
                        row[3], row[4], row[5], row[6],
                        row[7], row[8], row[9], row[10],
                        row[11], row[12], row[13], row[14],
                        row[15],
                    ))
                    inserted += 1
                except Exception:
                    skipped += 1

            offset += len(rows)
            pct = min(100, offset / total * 100)
            print(f"  {offset:,}/{total:,} ({pct:.0f}%) — inserted: {inserted:,}, skipped: {skipped:,}")

    elapsed = time.time() - start
    print(f"Daily quotes migrated: {inserted:,} inserted, {skipped:,} skipped in {elapsed:.1f}s")
    return inserted


def run_migration():
    """Execute full migration."""
    print("=== Starting SQLite → QuestDB Migration ===\n")

    # Initialize QuestDB schema
    print("Initializing QuestDB schema...")
    reg = DBRegistry()
    if reg.init_questdb_schema():
        print("  QuestDB schema initialized successfully.")
    else:
        print("  WARNING: QuestDB schema init failed (tables may not exist).")
        print("  Continuing anyway...")

    migrate_minute_quotes()
    print()
    migrate_daily_quotes()

    print("\n=== Migration Complete ===")


def verify():
    """Verify data consistency between SQLite and QuestDB."""
    pool = DBRegistry().get_pool("market")
    qdb = DBRegistry().get_questdb_connection()

    print("=== Data Verification ===\n")

    # Minute quotes
    with pool.connection() as conn:
        sqlite_count = conn.execute("SELECT COUNT(*) FROM minute_quotes").fetchone()[0]

    cur = qdb.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM future_minute")
        qdb_count = cur.fetchone()[0]
        status = "MATCH" if sqlite_count == qdb_count else "MISMATCH"
        print(f"minute_quotes:  SQLite={sqlite_count:,}  QuestDB={qdb_count:,}  [{status}]")
    except Exception as e:
        print(f"minute_quotes:  SQLite={sqlite_count:,}  QuestDB=ERROR({e})")

    # Daily quotes
    with pool.connection() as conn:
        sqlite_count = conn.execute("SELECT COUNT(*) FROM daily_quotes").fetchone()[0]

    try:
        cur.execute("SELECT COUNT(*) FROM daily_quotes")
        qdb_count = cur.fetchone()[0]
        status = "MATCH" if sqlite_count == qdb_count else "MISMATCH"
        print(f"daily_quotes:   SQLite={sqlite_count:,}  QuestDB={qdb_count:,}  [{status}]")
    except Exception as e:
        print(f"daily_quotes:   SQLite={sqlite_count:,}  QuestDB=ERROR({e})")

    # Sample spot check (last 5 rows)
    print("\nSpot check (last 5 minute quotes):")
    with pool.connection() as conn:
        sqlite_rows = conn.execute(
            "SELECT exchange, contract_code, trade_date, trade_time, close "
            "FROM minute_quotes ORDER BY id DESC LIMIT 5"
        ).fetchall()
        for row in sqlite_rows:
            print(f"  SQLite: {row[0]} {row[1]} {row[2]} {row[3]} close={row[4]}")

    try:
        cur.execute("""
            SELECT exchange, contract_code, date_part('day', ts),
                   date_part('hour', ts) || ':' || date_part('minute', ts) as t,
                   close
            FROM future_minute ORDER BY ts DESC LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  QDB:    {row[0]} {row[1]} {row[2]} {row[3]} close={row[4]}")
    except Exception as e:
        print(f"  QuestDB query failed: {e}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "dry-run":
        dry_run()
    elif cmd == "run":
        run_migration()
    elif cmd == "verify":
        verify()
    else:
        print("Usage: python migrations/sqlite_to_questdb.py {dry-run|run|verify}")
