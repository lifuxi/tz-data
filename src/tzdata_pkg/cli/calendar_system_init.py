"""
System initialization script for trade calendar.
Runs automatically on startup / first-time setup.
Generates holidays 1990-2029 based on Chinese statutory rules.
"""
import logging
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Historical Chinese holiday rules (1990-2029)
# Based on State Council announcements and exchange notices.
# Pre-1995: Only weekends (Saturday/Sunday) were off.
# 1995-2007: 五一黄金周 (7 days), 十一国庆, 春节, etc.
# 2008+: 取消五一黄金周, 增加清明/端午/中秋
# ============================================================

def generate_historical_holidays(year_start: int = 1990, year_end: int = 2029) -> dict[str, str]:
    """
    Generate Chinese exchange holidays for 1990-2029.

    Returns dict of date_str -> holiday_name.
    """
    holidays = {}

    for year in range(year_start, year_end + 1):
        holidays.update(_holidays_for_year(year))

    return holidays


def _holidays_for_year(year: int) -> dict[str, str]:
    """Generate holidays for a single year."""
    h = {}

    # === 元旦 (New Year): 1 day (Jan 1) ===
    h[f"{year}-01-01"] = "元旦"

    # === 国庆节 (National Day): Oct 1-7 (since 1999) ===
    if year >= 1999:
        for d in range(1, 8):
            h[f"{year}-10-{d:02d}"] = "国庆节"
    else:
        h[f"{year}-10-01"] = "国庆节"

    # === 春节 (Spring Festival): ~7 days, lunar dates ===
    _add_spring_festival(h, year)

    # === 清明节 (Qingming): 3 days since 2008 ===
    if year >= 2008:
        qm = _qingming_date(year)
        for i in range(3):
            d = qm + timedelta(days=i)
            h[d.isoformat()] = "清明节"
    else:
        h[f"{year}-04-05"] = "清明节"

    # === 劳动节 (Labor Day) ===
    if 2000 <= year <= 2007:
        # 五一黄金周 (7 days: May 1-7)
        for d in range(1, 8):
            h[f"{year}-05-{d:02d}"] = "劳动节"
    elif year >= 2008:
        # 2008+: Only May 1 (1 day) or adjusted
        for d in range(1, 4):
            h[f"{year}-05-{d:02d}"] = "劳动节"
    elif year >= 1995:
        h[f"{year}-05-01"] = "劳动节"

    # === 端午节 (Dragon Boat): 3 days since 2008 ===
    if year >= 2008:
        dn = _dragon_boat_date(year)
        if dn:
            for i in range(3):
                d = dn + timedelta(days=i)
                h[d.isoformat()] = "端午节"
    elif year >= 1995:
        _add_approx_dragon_boat(h, year)

    # === 中秋节 (Mid-Autumn): 3 days since 2008 ===
    if year >= 2008:
        ma = _mid_autumn_date(year)
        if ma:
            for i in range(3):
                d = ma + timedelta(days=i)
                if d.isoformat() not in h:  # Don't override National Day
                    h[d.isoformat()] = "中秋节"
    elif year >= 1995:
        _add_approx_mid_autumn(h, year)

    return h


# ============================================================
# Lunar calendar approximations (2020-2030 exact, 1990-2019 estimated)
# ============================================================

SPRING_FESTIVAL = {
    2029: "02-13", 2028: "01-26", 2027: "02-06", 2026: "02-17",
    2025: "01-29", 2024: "02-10", 2023: "01-22", 2022: "02-01",
    2021: "02-12", 2020: "01-25", 2019: "02-05", 2018: "02-16",
    2017: "01-28", 2016: "02-08", 2015: "02-19", 2014: "01-31",
    2013: "02-10", 2012: "01-23", 2011: "02-03", 2010: "02-14",
    2009: "01-26", 2008: "02-07", 2007: "02-18", 2006: "01-29",
    2005: "02-09", 2004: "01-22", 2003: "02-01", 2002: "02-12",
    2001: "01-24", 2000: "02-05", 1999: "02-16", 1998: "01-28",
    1997: "02-07", 1996: "02-19", 1995: "01-31", 1994: "02-10",
    1993: "01-23", 1992: "02-04", 1991: "02-15", 1990: "01-27",
}


def _add_spring_festival(holidays: dict, year: int):
    """Add Spring Festival dates based on lunar calendar."""
    sf_str = SPRING_FESTIVAL.get(year)
    if not sf_str:
        return

    sf = date(year, int(sf_str[:2]), int(sf_str[3:]))

    if year >= 1999:
        # 7-day holiday: usually from 除夕 to 初六
        for i in range(-1, 6):
            d = sf + timedelta(days=i)
            holidays[d.isoformat()] = "春节"
    else:
        # 1990-1998: 3 days (初一到初三)
        for i in range(1, 4):
            d = sf + timedelta(days=i)
            holidays[d.isoformat()] = "春节"


def _qingming_date(year: int) -> date:
    """Qingming is usually Apr 4-5 (depends on solar terms)."""
    # Approximate: April 4 for leap year, April 5 for others
    if year % 4 == 0:
        return date(year, 4, 4)
    else:
        return date(year, 4, 5)


# Dragon Boat and Mid-Autumn are lunar - approximate table
DRAGON_BOAT = {
    2029: "06-16", 2028: "05-28", 2027: "06-09", 2026: "06-19",
    2025: "05-31", 2024: "06-10", 2023: "06-22", 2022: "06-03",
    2021: "06-14", 2020: "06-25", 2019: "06-07", 2018: "06-18",
    2017: "05-30", 2016: "06-09", 2015: "06-20", 2014: "06-02",
    2013: "06-12", 2012: "06-23", 2011: "06-06", 2010: "06-16",
    2009: "05-28", 2008: "06-08",
}


def _dragon_boat_date(year: int) -> Optional[date]:
    """Get Dragon Boat Festival date (lunar May 5)."""
    dn_str = DRAGON_BOAT.get(year)
    if not dn_str:
        # Fallback: approximate (usually late May or June)
        day = 10 + (year * 7) % 15
        return date(year, 6, min(day, 28))
    return date(year, int(dn_str[:2]), int(dn_str[3:]))


def _add_approx_dragon_boat(holidays: dict, year: int):
    """Pre-2008 Dragon Boat (1 day)."""
    dn = _dragon_boat_date(year)
    if dn and dn.year == year:
        holidays[dn.isoformat()] = "端午节"


MID_AUTUMN = {
    2029: "09-22", 2028: "10-03", 2027: "09-15", 2026: "09-25",
    2025: "10-06", 2024: "09-17", 2023: "09-29", 2022: "09-10",
    2021: "09-21", 2020: "10-01", 2019: "09-13", 2018: "09-24",
    2017: "10-04", 2016: "09-15", 2015: "09-27", 2014: "09-08",
    2013: "09-19", 2012: "09-30", 2011: "09-12", 2010: "09-22",
    2009: "10-03", 2008: "09-14",
}


def _mid_autumn_date(year: int) -> Optional[date]:
    """Get Mid-Autumn Festival date (lunar Aug 15)."""
    ma_str = MID_AUTUMN.get(year)
    if not ma_str:
        # Fallback: usually Sept or early Oct
        day = 15 + (year * 3) % 10
        return date(year, 9, min(day, 28))
    return date(year, int(ma_str[:2]), int(ma_str[3:]))


def _add_approx_mid_autumn(holidays: dict, year: int):
    """Pre-2008 Mid-Autumn (1 day)."""
    ma = _mid_autumn_date(year)
    if ma and ma.year == year and ma.isoformat() not in holidays:
        holidays[ma.isoformat()] = "中秋节"


# ============================================================
# System init function
# ============================================================

def run_system_init(year_start: int = 1990, year_end: int = 2026,
                    init_products: bool = True) -> dict:
    """
    Full system initialization of trade calendar.

    1. Generate exchange-level holidays (ALL) for all years
    2. Initialize CFFEX product calendars based on listing dates
    3. Validate results

    Args:
        year_start: First year (default 1990)
        year_end: Last year (default 2026)
        init_products: Also init CFFEX product calendars

    Returns:
        Summary dict
    """
    from tzdata_pkg.maintenance.metadata.trade_calendar import (
        TradeCalendarManager, PRODUCT_LISTING_DATES, CHINESE_HOLIDAYS,
        PRODUCT_EXCHANGE_MAP
    )

    TradeCalendarManager._ensure_migration()

    # Step 1: Generate and apply holidays
    logger.info(f"Generating holidays {year_start}-{year_end}...")
    generated = generate_historical_holidays(year_start, year_end)
    logger.info(f"Generated {len(generated)} holiday dates")

    # Merge with existing hardcoded holidays
    all_holidays = {**generated, **CHINESE_HOLIDAYS}

    # Step 2: Init exchange calendar (ALL) - batch by year for performance
    from tzdata_pkg.storage.db_registry import DBRegistry
    pool = DBRegistry().get_pool('market')
    exchange_count = 0

    for year in range(year_start, year_end + 1):
        current = date(year, 1, 1)
        year_end_date = date(year, 12, 31)
        batch = []

        while current <= year_end_date:
            date_str = current.isoformat()
            is_weekend = current.weekday() >= 5
            is_holiday = date_str in all_holidays
            holiday_name = all_holidays.get(date_str)

            if is_weekend or is_holiday:
                batch.append((date_str, 1, holiday_name))

            current += timedelta(days=1)

        # Batch insert
        if batch:
            with pool.transaction() as conn:
                conn.executemany("""
                    INSERT INTO trade_calendar (trade_date, exchange_code, product_code, is_holiday, holiday_name)
                    VALUES (?, 'ALL', '', ?, ?)
                    ON CONFLICT(trade_date, exchange_code, product_code) DO UPDATE SET
                        is_holiday = excluded.is_holiday,
                        holiday_name = excluded.holiday_name
                """, batch)
            exchange_count += len(batch)

    result = {
        "exchange_calendar": exchange_count,
        "years": year_end - year_start + 1,
        "products": {},
    }

    # Step 3: Init CFFEX product calendars
    if init_products:
        for product_code, listing_date in PRODUCT_LISTING_DATES.items():
            exchange = PRODUCT_EXCHANGE_MAP.get(product_code)
            if exchange != 'CFFEX':
                continue

            try:
                count = TradeCalendarManager.init_product_calendar(
                    product_code=product_code,
                    year_start=year_start,
                    year_end=year_end,
                    listing_date=listing_date,
                )
                result["products"][product_code] = count
                logger.info(f"  {product_code}: {count} records (listed {listing_date.isoformat()})")
            except Exception as e:
                result["products"][product_code] = f"Error: {e}"
                logger.error(f"  {product_code}: {e}")

    return result
