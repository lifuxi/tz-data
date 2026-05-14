"""
Migration v3: Enhance product_config and contract_info with trading-relevant fields.

Changes:
- product_config: Add multiplier, price_tick, margin_rate, option_style
- contract_info: Add last_trade_date, delivery_date
"""
import logging

logger = logging.getLogger(__name__)


def migrate(db_path: str = None):
    """
    Run the product/contract schema migration v3.

    Args:
        db_path: Optional explicit DB path. If None, uses DBRegistry default.
    """
    if db_path:
        import sqlite3
        conn = sqlite3.connect(db_path)
        close_conn = True
    else:
        from tzdata_pkg.storage.db_registry import DBRegistry
        pool = DBRegistry().get_pool('market')
        conn = pool.get_connection()
        close_conn = False

    try:
        product_cols = [row[1] for row in conn.execute("PRAGMA table_info(product_config)").fetchall()]
        contract_cols = [row[1] for row in conn.execute("PRAGMA table_info(contract_info)").fetchall()]

        already_migrated = True

        # Product config new columns
        for col in ['multiplier', 'price_tick', 'margin_rate', 'option_style']:
            if col not in product_cols:
                conn.execute(f"ALTER TABLE product_config ADD COLUMN {col}")
                logger.info(f"  Added {col} to product_config")
                already_migrated = False

        # Contract info new columns
        for col in ['last_trade_date', 'delivery_date']:
            if col not in contract_cols:
                conn.execute(f"ALTER TABLE contract_info ADD COLUMN {col}")
                logger.info(f"  Added {col} to contract_info")
                already_migrated = False

        if already_migrated:
            logger.info("Migration v3 already applied, skipping")
        else:
            conn.commit()
            logger.info("Migration v3 complete")

    except Exception:
        conn.rollback()
        raise
    finally:
        if close_conn:
            conn.close()
