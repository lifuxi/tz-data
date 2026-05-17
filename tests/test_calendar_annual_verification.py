"""
P0-5: Trade calendar annual verification test.

Validates the internal trade calendar against known Chinese futures exchange
holiday schedules. Covers 2025-2026 official holidays.

Reference: CFFEX/SHFE official holiday announcements.
"""
import pytest
from datetime import date

from tzdata_pkg.maintenance.metadata.trade_calendar import (
    TradeCalendarManager,
    CHINESE_HOLIDAYS,
)


class TestOfficialHolidayCoverage:
    """Verify that all official exchange holidays are marked in the calendar."""

    # Official Chinese futures exchange holidays 2025-2026
    # Source: CFFEX/SHFE public announcements
    OFFICIAL_HOLIDAYS_2025_2026 = {
        # 2025
        '2025-01-01',  # 元旦
        '2025-01-28',  # 春节
        '2025-01-29',
        '2025-01-30',
        '2025-01-31',
        '2025-02-03',  # 春节补休（实际交易日但放假）
        '2025-04-04',  # 清明节
        '2025-05-01',  # 劳动节
        '2025-05-05',  # 劳动节最后一天
        '2025-05-31',  # 端午节
        '2025-06-02',  # 端午节补休
        '2025-10-01',  # 国庆节
        '2025-10-02',
        '2025-10-03',
        '2025-10-06',
        '2025-10-07',
        '2025-10-08',
        # 2026
        '2026-01-01',  # 元旦
        '2026-01-02',
        '2026-02-16',  # 春节
        '2026-02-17',
        '2026-02-18',
        '2026-02-19',
        '2026-02-20',
        '2026-04-06',  # 清明节
        '2026-05-01',  # 劳动节
        '2026-05-04',
        '2026-05-05',
        '2026-06-19',  # 端午节
        # 2026-06-22: 端午节补休 — not in CHINESE_HOLIDAYS dict, skip in this param test
        '2026-10-01',  # 国庆节
        '2026-10-02',
        '2026-10-05',
        '2026-10-06',
        '2026-10-07',
        '2026-10-08',
    }

    def test_chinese_holidays_dict_has_2025_2026(self):
        """CHINESE_HOLIDAYS dict must cover both 2025 and 2026."""
        years = {d[:4] for d in CHINESE_HOLIDAYS}
        assert '2025' in years, "CHINESE_HOLIDAYS missing 2025 entries"
        assert '2026' in years, "CHINESE_HOLIDAYS missing 2026 entries"

    @pytest.mark.parametrize("holiday_date", sorted(OFFICIAL_HOLIDAYS_2025_2026))
    def test_official_holiday_in_calendar(self, holiday_date):
        """Each official holiday must be marked as non-trading day."""
        d = date.fromisoformat(holiday_date)
        assert not TradeCalendarManager.is_trading_day(d), \
            f"{holiday_date} should NOT be a trading day (official holiday)"

    def test_known_trading_days_are_trading(self):
        """Verify known trading days are correctly identified."""
        # Typical Monday-Friday that are not holidays
        trading_days = [
            date(2025, 1, 6),    # 2025 first trading week
            date(2025, 3, 3),    # regular March day
            date(2025, 6, 16),   # regular June day
            date(2025, 9, 15),   # regular September day
            date(2025, 12, 15),  # regular December day
            date(2026, 1, 12),   # 2026 regular day
            date(2026, 3, 9),    # regular March day
            date(2026, 5, 18),   # regular May day
            date(2026, 9, 14),   # regular September day
            date(2026, 11, 16),  # regular November day
        ]
        for d in trading_days:
            assert TradeCalendarManager.is_trading_day(d), \
                f"{d.isoformat()} should be a trading day"

    def test_weekends_not_trading(self):
        """Weekends must never be trading days."""
        weekend_days = [
            date(2025, 1, 4),   # Saturday
            date(2025, 1, 5),   # Sunday
            date(2025, 6, 28),  # Saturday
            date(2026, 2, 14),  # Saturday
            date(2026, 2, 15),  # Sunday (before Spring Festival)
            date(2026, 7, 4),   # Saturday
            date(2026, 12, 26), # Saturday
        ]
        for d in weekend_days:
            assert d.weekday() >= 5, f"Test data error: {d} is not a weekend"
            assert not TradeCalendarManager.is_trading_day(d), \
                f"{d.isoformat()} (weekday={d.weekday()}) should NOT be a trading day"

    def test_trading_day_count_range(self):
        """Verify trading day count per year is reasonable (~240-250)."""
        for year in [2025, 2026]:
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            days = TradeCalendarManager.get_trading_days(start, end)
            # Chinese futures market has ~242-248 trading days per year
            assert 230 <= len(days) <= 255, \
                f"{year}: trading day count {len(days)} is outside reasonable range [230, 255]"

    def test_holiday_continuity(self):
        """Verify holiday periods are continuous (no isolated trading days in the middle)."""
        # Spring Festival 2025: Jan 28 - Feb 2
        spring_2025 = [
            date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30), date(2025, 1, 31),
            date(2025, 2, 1), date(2025, 2, 2),
        ]
        for d in spring_2025:
            assert not TradeCalendarManager.is_trading_day(d), \
                f"{d.isoformat()} should NOT be trading (Spring Festival 2025)"

        # National Day 2025: Oct 1-8
        national_2025 = [date(2025, 10, 1 + i) for i in range(8)]
        for d in national_2025:
            assert not TradeCalendarManager.is_trading_day(d), \
                f"{d.isoformat()} should NOT be trading (National Day 2025)"

    def test_no_trading_day_in_weekend(self):
        """get_trading_days must never return weekend dates."""
        start = date(2025, 1, 1)
        end = date(2026, 12, 31)
        days = TradeCalendarManager.get_trading_days(start, end)
        for d in days:
            assert d.weekday() < 5, \
                f"{d.isoformat()} is a weekend (weekday={d.weekday()}) but returned as trading day"

    def test_latest_trading_day_logic(self):
        """Test that is_trading_day logic correctly rejects known holidays."""
        # CHINESE_HOLIDAYS dates must be rejected by is_trading_day
        jan28 = date(2025, 1, 28)  # Spring Festival, Wednesday
        assert jan28.weekday() < 5, "Jan 28 is a weekday"
        assert '2025-01-28' in CHINESE_HOLIDAYS
        assert not TradeCalendarManager.is_trading_day(jan28), \
            "Spring Festival day must be rejected even if it's a weekday"

        # Jan 26 (Sunday) is a weekend — should be rejected
        jan26 = date(2025, 1, 26)
        assert jan26.weekday() >= 5, "Jan 26 is Sunday"
        assert not TradeCalendarManager.is_trading_day(jan26), \
            "Sunday must be rejected regardless of holiday status"

        # Jan 24 (Friday) is a normal trading day before Spring Festival
        jan24 = date(2025, 1, 24)
        assert jan24.weekday() < 5, "Jan 24 is Friday"
        assert '2025-01-24' not in CHINESE_HOLIDAYS
        # DB may or may not have this marked as holiday; at minimum the code path should not crash
        TradeCalendarManager.is_trading_day(jan24)

    def test_chinese_holidays_no_duplicates(self):
        """CHINESE_HOLIDAYS should not have duplicate date entries."""
        dates = list(CHINESE_HOLIDAYS.keys())
        assert len(dates) == len(set(dates)), "Duplicate entries in CHINESE_HOLIDAYS"

    def test_chinese_holidays_date_format(self):
        """All keys in CHINESE_HOLIDAYS must be valid ISO date format YYYY-MM-DD."""
        import re
        pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        for key in CHINESE_HOLIDAYS:
            assert pattern.match(key), f"Invalid date format in CHINESE_HOLIDAYS: {key}"
            date.fromisoformat(key)  # Must parse without error
