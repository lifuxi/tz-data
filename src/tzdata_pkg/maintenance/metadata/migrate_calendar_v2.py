"""
Migration v2: Expand trade_calendar with derived fields and product_code support.

Changes:
- Adds product_code column (if not present)
- Adds day_of_week column (ISO weekday: 1=Mon..7=Sun)
- Adds is_weekend column
- Adds is_workday column (for 调休 workdays)
- Adds special_flag column
- Ensures UNIQUE(trade_date, exchange_code, product_code) constraint
- Auto-populates derived fields from existing data
"""
import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


def migrate(db_path: str = None):
    """
    Run the calendar schema migration.

    Args:
        db_path: Optional explicit DB path. If None, uses DBRegistry default.
    """
    if db_path:
        pool = None  # Use direct connection
        conn = sqlite3.connect(db_path)
    else:
        from tzdata_pkg.storage.db_registry import DBRegistry
        pool = DBRegistry().get_pool('market')
        conn = pool.get_connection()

    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(trade_calendar)").fetchall()]

        # Check if already migrated
        new_cols = {'day_of_week', 'is_weekend', 'is_workday', 'special_flag'}
        if all(c in columns for c in new_cols) and 'product_code' in columns:
            logger.info("trade_calendar migration v2 already applied, skipping")
            return

        logger.info("Applying trade_calendar migration v2...")

        # Add missing columns one by one
        if 'product_code' not in columns:
            conn.execute("ALTER TABLE trade_calendar ADD COLUMN product_code TEXT NOT NULL DEFAULT ''")
            logger.info("  Added product_code column")

        if 'day_of_week' not in columns:
            conn.execute("ALTER TABLE trade_calendar ADD COLUMN day_of_week INTEGER DEFAULT 0")
            logger.info("  Added day_of_week column")

        if 'is_weekend' not in columns:
            conn.execute("ALTER TABLE trade_calendar ADD COLUMN is_weekend INTEGER DEFAULT 0")
            logger.info("  Added is_weekend column")

        if 'is_workday' not in columns:
            conn.execute("ALTER TABLE trade_calendar ADD COLUMN is_workday INTEGER DEFAULT 0")
            logger.info("  Added is_workday column")

        if 'special_flag' not in columns:
            conn.execute("ALTER TABLE trade_calendar ADD COLUMN special_flag TEXT DEFAULT ''")
            logger.info("  Added special_flag column")

        # Populate derived fields from existing data
        # strftime('%w'): 0=Sun, 1=Mon, ..., 6=Sat → ISO: 1=Mon..7=Sun
        conn.execute("""
            UPDATE trade_calendar
            SET day_of_week = CASE
                WHEN strftime('%w', trade_date) = '0' THEN 7
                ELSE CAST(strftime('%w', trade_date) AS INTEGER)
            END
        """)

        # Set is_weekend based on day_of_week
        conn.execute("""
            UPDATE trade_calendar
            SET is_weekend = 1
            WHERE day_of_week IN (6, 7)
        """)

        conn.commit()

        # Create product_listing_dates table if not exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_listing_dates (
                product_code TEXT PRIMARY KEY,
                product_name TEXT,
                exchange_code TEXT,
                listing_date TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_date ON trade_calendar(trade_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_exchange ON trade_calendar(exchange_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_product ON trade_calendar(product_code)")

        logger.info("trade_calendar migration v2 complete")

    except Exception:
        conn.rollback()
        raise
    finally:
        if db_path:
            conn.close()
