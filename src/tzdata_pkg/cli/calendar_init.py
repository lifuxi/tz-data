"""
Trade calendar initialization script with internet/LLM-based holiday fetching
and validation mechanism.

Usage:
    python -m tzdata_pkg.cli.calendar_init --year 2026 --method llm
    python -m tzdata_pkg.cli.calendar_init --year 2027 --method builtin
    python -m tzdata_pkg.cli.calendar_init --year 2026 --method llm --validate-only
"""
import argparse
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# ============================================================
# 1. Built-in holiday rules (Chinese statutory holidays)
# ============================================================

STATUTORY_HOLIDAYS = {
    "元旦": (1, 1, 3),     # (month, day, duration_days)
    "春节": (1, 25, 7),    # Approximate - varies by lunar calendar
    "清明节": (4, 4, 3),   # Approximate
    "劳动节": (5, 1, 5),   # Approximate
    "端午节": (6, 2, 3),   # Approximate - varies by lunar calendar
    "中秋节": (9, 15, 3),  # Approximate - varies by lunar calendar
    "国庆节": (10, 1, 7),  # Fixed: Oct 1-7
}


def _builtin_holidays_for_year(year: int) -> dict[str, str]:
    """
    Generate approximate Chinese holidays for a given year.
    Uses lunar date calculation for Spring Festival etc. where possible.
    """
    holidays = {}

    # Fixed holidays
    holidays[f"{year}-01-01"] = "元旦"
    holidays[f"{year}-10-01"] = "国庆节"
    holidays[f"{year}-10-02"] = "国庆节"
    holidays[f"{year}-10-03"] = "国庆节"
    holidays[f"{year}-10-04"] = "国庆节"
    holidays[f"{year}-10-05"] = "国庆节"
    holidays[f"{year}-10-06"] = "国庆节"
    holidays[f"{year}-10-07"] = "国庆节"

    # Labor Day
    holidays[f"{year}-05-01"] = "劳动节"
    holidays[f"{year}-05-02"] = "劳动节"
    holidays[f"{year}-05-03"] = "劳动节"
    holidays[f"{year}-05-04"] = "劳动节"
    holidays[f"{year}-05-05"] = "劳动节"

    # Spring Festival (lunar calendar - approximate for 2025-2030)
    spring_festival_dates = {
        2025: "2025-01-29", 2026: "2026-02-17", 2027: "2027-02-06",
        2028: "2028-01-26", 2029: "2029-02-13", 2030: "2030-02-03",
    }
    if year in spring_festival_dates:
        sf = date.fromisoformat(spring_festival_dates[year])
        # Usually 7 days starting from New Year's Eve
        for i in range(-1, 6):
            d = sf + __import__('datetime').timedelta(days=i)
            holidays[d.isoformat()] = "春节"
        # Also include the days before (New Year's Eve)
        holidays[(sf - __import__('datetime').timedelta(days=1)).isoformat()] = "春节"

    # Qingming Festival (around Apr 4-5)
    qingming = date(year, 4, 4) if year % 4 == 0 else date(year, 4, 5)
    for i in range(3):
        d = qingming + __import__('datetime').timedelta(days=i)
        holidays[d.isoformat()] = "清明节"

    # Dragon Boat Festival (lunar May 5 - approximate)
    dnd_dates = {
        2025: "2025-05-31", 2026: "2026-06-19", 2027: "2027-06-09",
        2028: "2028-05-28", 2029: "2029-06-16", 2030: "2030-06-05",
    }
    if year in dnd_dates:
        dd = date.fromisoformat(dnd_dates[year])
        for i in range(3):
            d = dd + __import__('datetime').timedelta(days=i)
            holidays[d.isoformat()] = "端午节"

    # Mid-Autumn Festival (lunar Aug 15 - approximate)
    ma_dates = {
        2025: "2025-10-06", 2026: "2026-09-25", 2027: "2027-09-15",
        2028: "2028-10-03", 2029: "2029-09-22", 2030: "2030-09-12",
    }
    if year in ma_dates:
        md = date.fromisoformat(ma_dates[year])
        # Check if already covered by National Day
        if md.month == 10 and md.day <= 7:
            pass  # Already in 国庆节
        else:
            for i in range(3):
                d = md + __import__('datetime').timedelta(days=i)
                if d.isoformat() not in holidays:
                    holidays[d.isoformat()] = "中秋节"

    return holidays


# ============================================================
# 2. Internet-based holiday fetching (CFFEX / SHFE notices)
# ============================================================

def _fetch_cffex_holiday_notice(year: int) -> dict[str, str]:
    """
    Try to fetch CFFEX holiday arrangement notices.
    Returns dict of date -> holiday_name.
    """
    holidays = {}
    # CFFEX publishes holiday arrangement notices at:
    # http://www.cffex.com.cn/xwzx/tzgg/
    # We try to scrape the notice list and find holiday arrangement notices

    try:
        resp = requests.get(
            "http://www.cffex.com.cn/xwzx/tzgg/",
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        resp.encoding = resp.apparent_encoding

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for notices containing holiday arrangement keywords
        keywords = ["休市", "节假日", "交易安排", year]
        for link in soup.find_all("a"):
            text = link.get_text(strip=True)
            if any(str(k) in text for k in keywords):
                href = link.get("href", "")
                if href:
                    # Try to get the notice detail page
                    detail_url = href if href.startswith("http") else f"http://www.cffex.com.cn{href}"
                    try:
                        detail = requests.get(detail_url, timeout=10,
                                            headers={"User-Agent": "Mozilla/5.0"})
                        detail.encoding = detail.apparent_encoding
                        detail_soup = BeautifulSoup(detail.text, "html.parser")
                        content = detail_soup.get_text()
                        # Try to extract dates from content
                        extracted = _extract_dates_from_notice(content, year)
                        holidays.update(extracted)
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"Failed to fetch CFFEX notices: {e}")

    return holidays


def _extract_dates_from_notice(text: str, year: int) -> dict[str, str]:
    """Extract holiday dates from exchange notice text."""
    holidays = {}

    # Pattern 1: "X月X日至X月X日休市"
    pattern1 = re.compile(
        r"(\d{1,2})月(\d{1,2})日[至](\d{1,2})月(\d{1,2})日.*休",
        re.DOTALL
    )
    for m in pattern1.finditer(text):
        try:
            start_m, start_d = int(m.group(1)), int(m.group(2))
            end_m, end_d = int(m.group(3)), int(m.group(4))
            # Determine year from context or default
            notice_year = _extract_year_from_context(text, year)
            start = date(notice_year, start_m, start_d)
            end = date(notice_year, end_m, end_d)
            from datetime import timedelta
            current = start
            while current <= end:
                holidays[current.isoformat()] = "交易所休市"
                current += timedelta(days=1)
        except (ValueError, TypeError):
            continue

    # Pattern 2: "X月X日(周X)至X月X日(周X)"
    pattern2 = re.compile(
        r"(\d{1,2})月(\d{1,2})日.*?(\d{1,2})月(\d{1,2})日",
        re.DOTALL
    )

    return holidays


def _extract_year_from_context(text: str, default: int) -> int:
    """Extract year from notice context."""
    m = re.search(rf"({default-1}|{default}|{default+1})年", text)
    if m:
        return int(m.group(1))
    return default


# ============================================================
# 3. LLM-based holiday fetching
# ============================================================

def _llm_fetch_holidays(year: int, prompt_template: Optional[str] = None) -> dict[str, str]:
    """
    Use LLM to fetch Chinese futures exchange holidays for a given year.
    Falls back to API key from environment if available.
    """
    if prompt_template is None:
        prompt_template = (
            f"请列出中国期货市场{year}年所有交易所休市的节假日安排（包括周末以外的所有非交易日）。"
            f"请严格按照JSON格式返回，不要任何其他文字。\n"
            f"格式：{{\"2025-01-01\": \"元旦\", \"2025-01-28\": \"春节\", ...}}\n"
            f"注意：\n"
            f"1. 只包含非周末的休市日期（周六周日自动排除）\n"
            f"2. 包含调休补班日（如果是交易日）\n"
            f"3. 参考中国证监会和中国期货交易所的官方安排\n"
            f"4. 确保日期准确，这是用于期货交易系统的数据"
        )

    # Try to use Claude API if available
    api_key = __import__('os').environ.get("ANTHROPIC_API_KEY") or __import__('os').environ.get("OPENAI_API_KEY")

    if api_key and __import__('os').environ.get("ANTHROPIC_API_KEY"):
        return _llm_via_claude(year, prompt_template, api_key)
    elif api_key:
        return _llm_via_openai(year, prompt_template, api_key)
    else:
        logger.warning("No LLM API key found (ANTHROPIC_API_KEY or OPENAI_API_KEY). "
                       "Falling back to builtin holidays.")
        return _builtin_holidays_for_year(year)


def _llm_via_claude(year: int, prompt: str, api_key: str) -> dict[str, str]:
    """Call Claude API to get holiday data."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=2000,
            system="你是一个数据助手，提供准确的中国期货交易所节假日安排。只返回JSON，不要其他文字。",
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        return _parse_llm_response(text)
    except Exception as e:
        logger.warning(f"LLM call failed: {e}, falling back to builtin holidays")
        return _builtin_holidays_for_year(year)


def _llm_via_openai(year: int, prompt: str, api_key: str) -> dict[str, str]:
    """Call OpenAI API to get holiday data."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是一个数据助手，提供准确的中国期货交易所节假日安排。只返回JSON，不要其他文字。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
        )
        text = resp.choices[0].message.content.strip()
        return _parse_llm_response(text)
    except Exception as e:
        logger.warning(f"LLM call failed: {e}, falling back to builtin holidays")
        return _builtin_holidays_for_year(year)


def _parse_llm_response(text: str) -> dict[str, str]:
    """Parse LLM response into holiday dict."""
    # Extract JSON from response
    json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            # Validate format
            validated = {}
            for date_str, name in data.items():
                # Validate date format
                if re.match(r'\d{4}-\d{2}-\d{2}', str(date_str)):
                    try:
                        date.fromisoformat(str(date_str))
                        validated[str(date_str)] = str(name)
                    except ValueError:
                        logger.warning(f"Invalid date from LLM: {date_str}")
            return validated
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON: {e}")
    return {}


# ============================================================
# 4. Validation mechanism
# ============================================================

def validate_holidays(year: int, holidays: dict[str, str]) -> dict:
    """
    Validate holiday data against known rules and cross-reference.

    Returns a validation report with:
    - errors: list of validation errors
    - warnings: list of warnings
    - is_valid: overall validity
    """
    report = {"errors": [], "warnings": [], "is_valid": True}

    # Rule 1: National Day must be Oct 1-7
    national_days = [d for d, n in holidays.items() if n == "国庆节"]
    expected_national = {f"{year}-10-{d:02d}" for d in range(1, 8)}
    actual_national = set(national_days)
    missing = expected_national - actual_national
    if missing:
        report["errors"].append(f"国庆节缺少日期: {sorted(missing)}")
        report["is_valid"] = False

    # Rule 2: No holidays on weekends (Sat=5, Sun=6)
    for date_str in list(holidays.keys()):
        try:
            d = date.fromisoformat(date_str)
            if d.weekday() >= 5:
                report["warnings"].append(f"{date_str} ({holidays[date_str]}) 是周末")
        except ValueError:
            report["errors"].append(f"无效日期: {date_str}")
            report["is_valid"] = False

    # Rule 3: Check that all dates are within the year
    for date_str in holidays:
        if not date_str.startswith(str(year)):
            report["errors"].append(f"{date_str} 不在{year}年")
            report["is_valid"] = False

    # Rule 4: Spring Festival should be in Jan or Feb
    spring_fest = [d for d, n in holidays.items() if n == "春节"]
    for sf in spring_fest:
        m = int(sf.split("-")[1])
        if m not in (1, 2):
            report["warnings"].append(f"春节日期异常: {sf} (应在1-2月)")

    # Rule 5: Reasonable number of holidays (should be 20-35 for Chinese market)
    non_weekend_holidays = [
        d for d in holidays if date.fromisoformat(d).weekday() < 5
    ]
    if len(non_weekend_holidays) < 15:
        report["warnings"].append(f"节假日数量偏少 ({len(non_weekend_holidays)} 天)")
    elif len(non_weekend_holidays) > 40:
        report["warnings"].append(f"节假日数量偏多 ({len(non_weekend_holidays)} 天)")

    # Rule 6: Cross-reference with builtin holidays
    builtin = _builtin_holidays_for_year(year)
    builtin_dates = set(builtin.keys())
    provided_dates = set(holidays.keys())

    # Major holidays that should exist
    for bd, bn in builtin.items():
        if bn in ("国庆节", "元旦") and bd not in provided_dates:
            report["warnings"].append(f"缺少固定节假日: {bd} ({bn})")

    return report


def compare_with_builtin(year: int, holidays: dict[str, str]) -> dict:
    """Compare provided holidays with builtin data and show differences."""
    builtin = _builtin_holidays_for_year(year)
    builtin_set = set(builtin.keys())
    provided_set = set(holidays.keys())

    return {
        "only_in_builtin": sorted(builtin_set - provided_set),
        "only_in_provided": sorted(provided_set - builtin_set),
        "common": sorted(builtin_set & provided_set),
        "name_differences": {
            d: {"builtin": builtin[d], "provided": holidays[d]}
            for d in (builtin_set & provided_set)
            if builtin[d] != holidays[d]
        },
    }


# ============================================================
# 5. Main initialization function
# ============================================================

def init_calendar_year(
    year: int,
    method: str = "builtin",
    exchange_code: str = "ALL",
    validate: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Initialize trade calendar for a single year.

    Args:
        year: Year to initialize
        method: "builtin", "internet", or "llm"
        exchange_code: Exchange code (default "ALL")
        validate: Run validation after fetching
        dry_run: Don't write to DB, just show results

    Returns:
        Result dict with count, validation report, etc.
    """
    result = {"year": year, "method": method, "count": 0, "validation": None, "comparison": None}

    # Step 1: Fetch holidays
    logger.info(f"Fetching {year} holidays via {method}...")

    if method == "builtin":
        holidays = _builtin_holidays_for_year(year)
    elif method == "internet":
        holidays = _fetch_cffex_holiday_notice(year)
        if not holidays:
            logger.warning("Internet fetch returned no data, falling back to builtin")
            holidays = _builtin_holidays_for_year(year)
    elif method == "llm":
        holidays = _llm_fetch_holidays(year)
    else:
        raise ValueError(f"Unknown method: {method}")

    result["holidays"] = holidays

    # Step 2: Validate
    if validate:
        validation = validate_holidays(year, holidays)
        result["validation"] = validation
        if not validation["is_valid"]:
            logger.warning(f"Validation failed for {year}: {validation['errors']}")

    # Step 3: Compare with builtin
    comparison = compare_with_builtin(year, holidays)
    result["comparison"] = comparison

    if dry_run:
        result["count"] = len(holidays)
        return result

    # Step 4: Write to DB
    from tzdata_pkg.storage.db_registry import DBRegistry
    pool = DBRegistry().get_pool('market')
    count = 0

    # Get all dates in year
    from datetime import timedelta
    current = date(year, 1, 1)
    year_end = date(year, 12, 31)

    while current <= year_end:
        date_str = current.isoformat()
        is_weekend = current.weekday() >= 5
        is_holiday = date_str in holidays
        holiday_name = holidays.get(date_str)

        if is_holiday or is_weekend:
            with pool.transaction() as conn:
                conn.execute("""
                    INSERT INTO trade_calendar (trade_date, exchange_code, is_holiday, holiday_name)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(trade_date, exchange_code) DO UPDATE SET
                        is_holiday = excluded.is_holiday,
                        holiday_name = excluded.holiday_name
                """, (date_str, exchange_code, 1 if (is_weekend or is_holiday) else 0, holiday_name))
                count += 1

        current += timedelta(days=1)

    result["count"] = count
    logger.info(f"Initialized {year} calendar: {count} non-trading days")
    return result


# ============================================================
# 6. CLI entry point
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Initialize trade calendar")
    parser.add_argument("--year", type=int, required=True, help="Year to initialize")
    parser.add_argument("--method", choices=["builtin", "internet", "llm"], default="builtin",
                        help="Method to fetch holidays")
    parser.add_argument("--exchange", default="ALL", help="Exchange code")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't write to DB")
    parser.add_argument("--dry-run", action="store_true", help="Show results without writing")
    parser.add_argument("--compare", action="store_true", help="Compare with builtin holidays")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    result = init_calendar_year(
        year=args.year,
        method=args.method,
        exchange_code=args.exchange,
        validate=True,
        dry_run=args.dry_run or args.validate_only,
    )

    # Print results
    print(f"\n{'='*60}")
    print(f"交易日历初始化结果 - {args.year}年")
    print(f"{'='*60}")
    print(f"方法: {args.method}")
    print(f"节假日数量: {len(result.get('holidays', {}))}")
    print(f"写入数据库: {'否（dry-run）' if args.dry_run else str(result['count']) + ' 条'}")

    if result.get("validation"):
        v = result["validation"]
        print(f"\n校验报告:")
        print(f"  通过: {'是' if v['is_valid'] else '否'}")
        if v["errors"]:
            for e in v["errors"]:
                print(f"  [错误] {e}")
        if v["warnings"]:
            for w in v["warnings"]:
                print(f"  [警告] {w}")

    if args.compare or args.verbose:
        c = result.get("comparison")
        if c:
            print(f"\n与内置数据对比:")
            if c["only_in_builtin"]:
                print(f"  仅内置: {c['only_in_builtin']}")
            if c["only_in_provided"]:
                print(f"  仅提供: {c['only_in_provided']}")
            if c["name_differences"]:
                print(f"  名称差异: {c['name_differences']}")

    # Print all holidays
    print(f"\n{args.year}年节假日安排:")
    for d in sorted(result.get("holidays", {}).keys()):
        print(f"  {d}  {result['holidays'][d]}")


if __name__ == "__main__":
    main()
