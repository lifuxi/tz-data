"""
Trade calendar manager.
Manages Chinese futures exchange trading calendar.
"""
import logging
from datetime import date, timedelta
from typing import Optional

from tzdata_pkg.storage.db_registry import DBRegistry

logger = logging.getLogger(__name__)

# ============================================================
# Product listing dates (Chinese futures market)
# ============================================================

PRODUCT_LISTING_DATES = {
    # === CFFEX Futures ===
    "IF": date(2010, 4, 16),   # 沪深300期货
    "IH": date(2015, 4, 16),   # 上证50期货
    "IC": date(2015, 4, 16),   # 中证500期货
    "IM": date(2022, 7, 22),   # 中证1000期货
    # === CFFEX Options ===
    "IO": date(2019, 12, 23),  # 沪深300期权
    "HO": date(2022, 7, 22),   # 上证50期权 (CFFEX)
    "MO": date(2022, 7, 22),   # 中证1000期权
    # === SHFE Futures (partial) ===
    "AU": date(2008, 1, 9),    # 黄金
    "AG": date(2012, 5, 10),   # 白银
    "CU": date(1999, 10, 1),   # 铜
    "AL": date(1999, 10, 1),   # 铝
    "ZN": date(2007, 3, 26),   # 锌
    "SN": date(2007, 4, 10),   # 锡
}

PRODUCT_EXCHANGE_MAP = {
    "IF": "CFFEX", "IH": "CFFEX", "IC": "CFFEX", "IM": "CFFEX",
    "IO": "CFFEX", "HO": "CFFEX", "MO": "CFFEX",
    "AU": "SHFE", "AG": "SHFE", "CU": "SHFE", "AL": "SHFE", "ZN": "SHFE", "SN": "SHFE",
}

# Chinese futures exchange holidays 2025-2026
# (approximate, actual dates announced by exchanges each year)
CHINESE_HOLIDAYS = {
    # 2025
    '2025-01-01': '元旦',
    '2025-01-27': '春节',
    '2025-01-28': '春节',
    '2025-01-29': '春节',
    '2025-01-30': '春节',
    '2025-01-31': '春节',
    '2025-02-01': '春节',
    '2025-02-02': '春节',
    '2025-04-04': '清明节',
    '2025-04-05': '清明节',
    '2025-04-06': '清明节',
    '2025-05-01': '劳动节',
    '2025-05-02': '劳动节',
    '2025-05-03': '劳动节',
    '2025-05-04': '劳动节',
    '2025-05-05': '劳动节',
    '2025-05-31': '端午节',
    '2025-06-01': '端午节',
    '2025-06-02': '端午节',
    '2025-10-01': '国庆节',
    '2025-10-02': '国庆节',
    '2025-10-03': '国庆节',
    '2025-10-04': '国庆节',
    '2025-10-05': '国庆节',
    '2025-10-06': '国庆节',
    '2025-10-07': '国庆节',
    '2025-10-08': '国庆节',
    # 2026
    '2026-01-01': '元旦',
    '2026-01-02': '元旦',
    '2026-01-03': '元旦',
    '2026-02-14': '春节',
    '2026-02-15': '春节',
    '2026-02-16': '春节',
    '2026-02-17': '春节',
    '2026-02-18': '春节',
    '2026-02-19': '春节',
    '2026-02-20': '春节',
    '2026-02-21': '春节',
    '2026-04-05': '清明节',
    '2026-04-06': '清明节',
    '2026-04-07': '清明节',
    '2026-05-01': '劳动节',
    '2026-05-02': '劳动节',
    '2026-05-03': '劳动节',
    '2026-05-04': '劳动节',
    '2026-05-05': '劳动节',
    '2026-06-19': '端午节',
    '2026-06-20': '端午节',
    '2026-06-21': '端午节',
    '2026-10-01': '国庆节',
    '2026-10-02': '国庆节',
    '2026-10-03': '国庆节',
    '2026-10-04': '国庆节',
    '2026-10-05': '国庆节',
    '2026-10-06': '国庆节',
    '2026-10-07': '国庆节',
    '2026-10-08': '国庆节',
}


class TradeCalendarManager:
    @staticmethod
    def _ensure_migration():
        """Run product_code migration if needed."""
        from tzdata_pkg.maintenance.metadata.migrate_product_calendar import migrate
        migrate()

    @staticmethod
    def init_calendar(year_start: int = 2025, year_end: int = 2026) -> int:
        """
        Initialize trade calendar with holidays.

        Args:
            year_start: Start year
            year_end: End year (inclusive)

        Returns:
            Number of records inserted/updated
        """
        TradeCalendarManager._ensure_migration()
        pool = DBRegistry().get_pool('market')
        count = 0

        for year in range(year_start, year_end + 1):
            current = date(year, 1, 1)
            year_end_date = date(year, 12, 31)

            while current <= year_end_date:
                date_str = current.isoformat()
                is_weekend = current.weekday() >= 5
                is_holiday = date_str in CHINESE_HOLIDAYS
                holiday_name = CHINESE_HOLIDAYS.get(date_str)

                with pool.transaction() as conn:
                    conn.execute("""
                        INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday, holiday_name)
                        VALUES (?, 'ALL', '', ?, ?)
                        ON CONFLICT(trade_date, exchange_code, product_code) DO UPDATE SET
                            is_holiday = excluded.is_holiday,
                            holiday_name = excluded.holiday_name
                    """, (date_str, 1 if (is_weekend or is_holiday) else 0, holiday_name))
                    count += 1

                current += timedelta(days=1)

        logger.info(f"Initialized trade calendar: {count} dates from {year_start} to {year_end}")
        return count

    @staticmethod
    def get_trading_days(start_date: date, end_date: date,
                         exchange_code: str = 'ALL') -> list[date]:
        """
        Get trading days between two dates (excluding weekends and holidays).

        For 'ALL' scope: generates all dates in range, excludes weekends
        and dates stored as holidays in the DB.

        Args:
            start_date: Start date
            end_date: End date
            exchange_code: Exchange code (default 'ALL')

        Returns:
            List of trading dates
        """
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            # Get non-trading dates from DB
            rows = conn.execute("""
                SELECT trade_date FROM trade_calendar
                WHERE trade_date BETWEEN ? AND ?
                  AND exchange_code = ?
                  AND is_holiday = 1
                ORDER BY trade_date
            """, (start_date.isoformat(), end_date.isoformat(), exchange_code))
            non_trading = {row[0] for row in rows.fetchall()}

        # Generate all dates and exclude weekends + stored holidays
        trading = []
        current = start_date
        while current <= end_date:
            date_str = current.isoformat()
            is_weekend = current.weekday() >= 5
            if not is_weekend and date_str not in non_trading:
                trading.append(current)
            current += timedelta(days=1)

        return trading

    @staticmethod
    def is_trading_day(trade_date: date, exchange_code: str = 'ALL') -> bool:
        """Check if a date is a trading day."""
        if trade_date.weekday() >= 5:
            return False
        date_str = trade_date.isoformat()
        if date_str in CHINESE_HOLIDAYS:
            return False
        # Check DB for any exchange-specific holidays
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            row = conn.execute("""
                SELECT 1 FROM trade_calendar
                WHERE trade_date = ? AND exchange_code IN ('ALL', ?) AND is_holiday = 1
            """, (date_str, exchange_code)).fetchone()
            return row is None

    @staticmethod
    def get_latest_trading_day(before_date: date = None,
                               exchange_code: str = 'ALL') -> Optional[date]:
        """Get the most recent trading day before or on the given date."""
        if before_date is None:
            before_date = date.today()
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            row = conn.execute("""
                SELECT trade_date FROM trade_calendar
                WHERE trade_date <= ? AND exchange_code IN ('ALL', ?) AND is_holiday = 0
                ORDER BY trade_date DESC LIMIT 1
            """, (before_date.isoformat(), exchange_code)).fetchone()
            if row:
                return date.fromisoformat(row[0])
        return None

    @staticmethod
    def add_holiday(trade_date: date, holiday_name: str,
                    exchange_code: str = 'ALL') -> bool:
        """Mark a date as a holiday."""
        TradeCalendarManager._ensure_migration()
        pool = DBRegistry().get_pool('market')
        try:
            with pool.transaction() as conn:
                conn.execute("""
                    INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday, holiday_name)
                    VALUES (?, ?, '', 1, ?)
                    ON CONFLICT(trade_date, exchange_code, product_code) DO UPDATE SET
                        is_holiday = 1, holiday_name = excluded.holiday_name
                """, (trade_date.isoformat(), exchange_code, holiday_name))
            return True
        except Exception as e:
            logger.error(f"Failed to add holiday: {e}")
            return False

    @staticmethod
    def _ensure_product_column():
        """Ensure migration has been run (delegates to _ensure_migration)."""
        TradeCalendarManager._ensure_migration()

    @staticmethod
    def get_product_listing_date(product_code: str) -> Optional[date]:
        """Get listing date for a product."""
        # Check DB first
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT listing_date FROM product_listing_dates WHERE product_code = ?",
                (product_code,)
            ).fetchone()
            if row and row[0]:
                return date.fromisoformat(row[0])
        # Fallback to hardcoded dates
        return PRODUCT_LISTING_DATES.get(product_code)

    @staticmethod
    def _ensure_listing_table():
        """Create product_listing_dates table if not exists."""
        pool = DBRegistry().get_pool('market')
        with pool.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_listing_dates (
                    product_code TEXT PRIMARY KEY,
                    product_name TEXT,
                    exchange_code TEXT,
                    listing_date TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    @staticmethod
    def init_product_calendar(
        product_code: str,
        year_start: int = 2025,
        year_end: int = 2026,
        listing_date: Optional[date] = None,
    ) -> int:
        """
        Initialize product-level trade calendar.

        For each date from listing_date to year_end:
        - Inherit exchange-level holidays (from 'ALL' entries)
        - Mark dates before listing_date as holiday with name '未上市'
        - Weekend dates are marked as weekend
        - Trading days are set to is_holiday=0

        Args:
            product_code: Product code (e.g. IM, MO)
            year_start: Start year
            year_end: End year (inclusive)
            listing_date: Override listing date (default from PRODUCT_LISTING_DATES)

        Returns:
            Number of records inserted/updated
        """
        TradeCalendarManager._ensure_product_column()
        TradeCalendarManager._ensure_listing_table()

        if listing_date is None:
            listing_date = TradeCalendarManager.get_product_listing_date(product_code)
        if listing_date is None:
            raise ValueError(f"Unknown listing date for product {product_code}")

        # Save listing date to DB
        pool = DBRegistry().get_pool('market')
        exchange = PRODUCT_EXCHANGE_MAP.get(product_code, 'ALL')
        product_name = product_code  # Could be enhanced with product name lookup
        with pool.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO product_listing_dates
                (product_code, product_name, exchange_code, listing_date)
                VALUES (?, ?, ?, ?)
            """, (product_code, product_name, exchange, listing_date.isoformat()))

        # Build exchange holiday set and name map for the year range
        holiday_names = {}
        with pool.connection() as conn:
            rows = conn.execute("""
                SELECT trade_date, holiday_name FROM trade_calendar
                WHERE exchange_code = 'ALL' AND is_holiday = 1
                  AND trade_date BETWEEN ? AND ?
            """, (f"{year_start}-01-01", f"{year_end}-12-31"))
            for row in rows.fetchall():
                holiday_names[row[0]] = row[1] or ''
        exchange_holidays = set(holiday_names.keys())

        # Build all records by year, batch insert for performance
        count = 0
        for year in range(year_start, year_end + 1):
            current = date(year, 1, 1)
            year_end_date = date(year, 12, 31)
            batch_not_listed = []
            batch_holiday = []
            batch_trading = []

            while current <= year_end_date:
                date_str = current.isoformat()
                is_weekend = current.weekday() >= 5
                is_exchange_holiday = date_str in exchange_holidays
                is_before_listing = current < listing_date

                if is_before_listing:
                    batch_not_listed.append((date_str, exchange, product_code))
                elif is_weekend or is_exchange_holiday:
                    hn = holiday_names.get(date_str, '') if is_exchange_holiday else ''
                    batch_holiday.append((date_str, exchange, product_code, hn))
                else:
                    batch_trading.append((date_str, exchange, product_code))

                current += timedelta(days=1)

            # Batch insert all categories
            if batch_not_listed:
                with pool.transaction() as conn:
                    conn.executemany("""
                        INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday, holiday_name)
                        VALUES (?, ?, ?, 1, '未上市')
                        ON CONFLICT(trade_date, exchange_code, product_code) DO UPDATE SET
                            is_holiday = 1, holiday_name = '未上市'
                    """, batch_not_listed)
                count += len(batch_not_listed)

            if batch_holiday:
                with pool.transaction() as conn:
                    conn.executemany("""
                        INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday, holiday_name)
                        VALUES (?, ?, ?, 1, ?)
                        ON CONFLICT(trade_date, exchange_code, product_code) DO UPDATE SET
                            is_holiday = 1, holiday_name = excluded.holiday_name
                    """, batch_holiday)
                count += len(batch_holiday)

            if batch_trading:
                with pool.transaction() as conn:
                    conn.executemany("""
                        INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday, holiday_name)
                        VALUES (?, ?, ?, 0, '')
                        ON CONFLICT(trade_date, exchange_code, product_code) DO UPDATE SET
                            is_holiday = 0, holiday_name = ''
                    """, batch_trading)
                count += len(batch_trading)

                current += timedelta(days=1)

        logger.info(f"Initialized product calendar for {product_code}: {count} dates from {year_start} to {year_end}")
        return count

    @staticmethod
    def get_product_trading_days(
        product_code: str,
        start_date: date,
        end_date: date,
    ) -> list[date]:
        """Get trading days for a specific product."""
        TradeCalendarManager._ensure_product_column()
        exchange = PRODUCT_EXCHANGE_MAP.get(product_code, 'ALL')
        pool = DBRegistry().get_pool('market')
        with pool.connection() as conn:
            rows = conn.execute("""
                SELECT trade_date FROM trade_calendar
                WHERE trade_date BETWEEN ? AND ?
                  AND exchange_code = ?
                  AND product_code = ?
                  AND is_holiday = 0
                ORDER BY trade_date
            """, (start_date.isoformat(), end_date.isoformat(), exchange, product_code))
            return [date.fromisoformat(row[0]) for row in rows.fetchall()]
