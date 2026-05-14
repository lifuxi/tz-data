"""
Migration v4: tz-data data layer schema.

Changes:
- trades: Add 5 new columns (trade_time, order_type, strategy_tag, vwap, slippage)
- Create 4 new tables: bill_fund_flows, option_greeks_daily, daily_index_prices, contract_expiry
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TRADE_COLUMNS = ['trade_time', 'order_type', 'strategy_tag', 'vwap', 'slippage']


def migrate(db_path: str = None):
    """
    Run the data layer schema migration.

    Args:
        db_path: Optional explicit DB path. If None, uses DBRegistry default.
    """
    if db_path:
        import sqlite3
        conn = sqlite3.connect(db_path)
        close_conn = True
    else:
        from tzdata_pkg.storage.db_registry import DBRegistry
        pool = DBRegistry().get_pool('trading')
        conn = pool.get_connection()
        close_conn = False

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        # Step 1: Add new columns to trades table (SQLite 3.37+ supports IF NOT EXISTS)
        existing_cols = [
            row[1] for row in conn.execute("PRAGMA table_info(trades)").fetchall()
        ]

        col_types = {
            'trade_time': 'TEXT',
            'order_type': 'TEXT',
            'strategy_tag': 'TEXT',
            'vwap': 'DECIMAL(20,4)',
            'slippage': 'DECIMAL(20,4)',
        }

        for col_name in TRADE_COLUMNS:
            if col_name not in existing_cols:
                conn.execute(
                    f"ALTER TABLE trades ADD COLUMN {col_name} {col_types[col_name]}"
                )
                logger.info(f"Added column {col_name} to trades")
            else:
                logger.debug(f"Column {col_name} already exists in trades")

        # Step 2: Execute new table definitions
        schema_path = Path(__file__).resolve().parent.parent.parent / "storage" / "schemas" / "trading_data_layer.sql"
        if schema_path.exists():
            sql_text = schema_path.read_text(encoding="utf-8")
            conn.executescript(sql_text)
            logger.info("Executed trading_data_layer.sql schema")
        else:
            logger.warning(f"Schema file not found: {schema_path}")

        conn.commit()
        logger.info("Data layer schema migration v4 completed successfully")

    except Exception as e:
        logger.warning(f"Data layer migration v4 failed: {e}")
        raise
    finally:
        if close_conn:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate()
