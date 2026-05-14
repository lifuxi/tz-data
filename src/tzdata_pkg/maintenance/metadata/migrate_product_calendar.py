"""
Migration: Add product_code support to trade_calendar.

Changes:
- Adds product_code column
- Removes UNIQUE(trade_date) in favor of UNIQUE(trade_date, exchange_code, product_code)
- Creates product_listing_dates table
"""
import logging

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)


def migrate():
    """Run the migration."""
    pool = DBRegistry().get_pool('market')

    with pool.connection() as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(trade_calendar)").fetchall()]

    # Already migrated?
    if 'product_code' in columns:
        logger.info("trade_calendar already has product_code column, skipping")
        return

    logger.info("Migrating trade_calendar to support product_code...")

    with pool.transaction() as conn:
        # Step 1: Create new table with correct schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_calendar_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                exchange_code TEXT NOT NULL DEFAULT 'ALL',
                product_code TEXT NOT NULL DEFAULT '',
                is_holiday INTEGER DEFAULT 0,
                holiday_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_date, exchange_code, product_code)
            )
        """)

        # Step 2: Copy data from old table (product_code = '')
        conn.execute("""
            INSERT INTO trade_calendar_new (trade_date, exchange_code, is_holiday, holiday_name, created_at)
            SELECT trade_date, exchange_code, is_holiday, holiday_name, created_at
            FROM trade_calendar
        """)

        # Step 3: Drop old table
        conn.execute("DROP TABLE trade_calendar")

        # Step 4: Rename new table
        conn.execute("ALTER TABLE trade_calendar_new RENAME TO trade_calendar")

        # Step 5: Recreate indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_date ON trade_calendar(trade_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_exchange ON trade_calendar(exchange_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_product ON trade_calendar(product_code)")

        # Step 6: Create product_listing_dates table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_listing_dates (
                product_code TEXT PRIMARY KEY,
                product_name TEXT,
                exchange_code TEXT,
                listing_date TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    logger.info("Migration complete: trade_calendar now supports product_code")
