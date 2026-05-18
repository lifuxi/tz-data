"""Analysis data routes: signals, regime, institution features, option data, IV analysis."""

import json
from typing import Optional
from fastapi import APIRouter, Query

from tzdata_pkg.cache.cache_service import cache_result
from tzdata_pkg.query import TzDataClient

router = APIRouter()


@router.get("/signals", summary="交易信号", description="查询系统生成的交易信号数据")
def get_signals(
    signal_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Query trading signals."""
    with TzDataClient() as client:
        results = client.signals(signal_type=signal_type, start_date=start_date, end_date=end_date)
    return {"count": len(results), "data": results}


@router.get("/regime", summary="市场状态", description="查询市场状态分类（趋势/震荡/突破等）")
@cache_result("market_regime", ttl=86400, tags=["regime"])
def get_market_regime(
    trade_date: Optional[str] = Query(None),
):
    """Query market regime classification."""
    with TzDataClient() as client:
        results = client.market_regime(trade_date=trade_date)
    return {"count": len(results), "data": results}


@router.get("/institution-features", summary="机构特征", description="查询机构会员的持仓特征数据")
def get_institution_features(
    member_name: Optional[str] = Query(None),
    trade_date: Optional[str] = Query(None),
):
    """Query institution feature data."""
    with TzDataClient() as client:
        results = client.institution_features(member_name=member_name, trade_date=trade_date)
    return {"count": len(results), "data": results}


@router.get("/option-features", summary="期权特征", description="查询期权特征数据（含 Greeks）")
@cache_result("option_greeks", ttl=86400, tags=["option", "greeks"])
def get_option_features(
    trade_date: Optional[str] = Query(None),
    contract: Optional[str] = Query(None),
):
    """Query option feature data with Greeks."""
    with TzDataClient() as client:
        results = client.option_features(trade_date=trade_date, contract=contract)
    return {"count": len(results), "data": results}


@router.get("/iv-snapshot", summary="IV 快照", description="查询隐含波动率快照数据")
def get_iv_snapshot(
    trade_date: Optional[str] = Query(None),
    underlying: Optional[str] = Query(None),
):
    """Query implied volatility snapshot."""
    with TzDataClient() as client:
        results = client.iv_snapshot(trade_date=trade_date, underlying=underlying)
    return {"count": len(results), "data": results}


@router.get("/tushare-daily", summary="Tushare 日线", description="查询 Tushare 日线数据")
def get_tushare_daily(
    ts_code: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Query Tushare daily data."""
    with TzDataClient() as client:
        results = client.tushare_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    return {"count": len(results), "data": results}


# ============================================================
# IV Analysis API endpoints
# ============================================================

@router.get("/iv/benchmark", summary="IV 基准指标", description="获取每日 IV 衍生指标")
@cache_result("iv_benchmark", ttl=86400, tags=["iv"])
def get_iv_benchmark(
    variety: Optional[str] = Query(None, description="品种: MO/IO/HO"),
    start: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """Query IV benchmark data."""
    import sqlite3
    from tzdata_pkg.config import TZDATA_TRADING_DB

    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        where = []
        params = []
        if variety:
            where.append("variety = ?")
            params.append(variety)
        if start:
            where.append("trade_date >= ?")
            params.append(start)
        if end:
            where.append("trade_date <= ?")
            params.append(end)

        where_sql = "WHERE " + " AND ".join(where) if where else ""

        rows = conn.execute(f"""
            SELECT trade_date, variety, atm_iv, atm_strike, spot_price,
                   hv_20, hv_60, iv_hv_spread, skew_25delta, term_structure,
                   iv_percentile_1y, iv_regime, pcr_volume, pcr_oi
            FROM iv_benchmark {where_sql}
            ORDER BY trade_date, variety
        """, params).fetchall()

        cols = ["trade_date", "variety", "atm_iv", "atm_strike", "spot_price",
                "hv_20", "hv_60", "iv_hv_spread", "skew_25delta", "term_structure",
                "iv_percentile_1y", "iv_regime", "pcr_volume", "pcr_oi"]

        results = []
        for row in rows:
            d = dict(zip(cols, row))
            if d.get("term_structure"):
                try:
                    d["term_structure"] = json.loads(d["term_structure"])
                except (json.JSONDecodeError, TypeError):
                    d["term_structure"] = None
            results.append(d)
        return {"count": len(results), "data": results}
    finally:
        conn.close()


@router.get("/iv/surface", summary="IV 曲面", description="获取波动率曲面数据")
@cache_result("iv_surface", ttl=86400, tags=["iv"])
def get_iv_surface(
    variety: Optional[str] = Query("MO"),
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
):
    """Query IV surface matrix."""
    import sqlite3
    from tzdata_pkg.config import TZDATA_TRADING_DB

    if not date:
        date = "2099-12-31"  # Will get latest available

    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        rows = conn.execute("""
            SELECT expire_date, strike, iv, option_type
            FROM mo_daily_iv_quotes
            WHERE trade_date <= ? AND underlying = ?
              AND iv IS NOT NULL AND strike IS NOT NULL
            ORDER BY expire_date, strike
        """, (date, variety)).fetchall()

        # Build matrix: {expiry_date: {strike: {"C": iv, "P": iv}}}
        matrix = {}
        for expiry, strike, iv, opt_type in rows:
            if expiry not in matrix:
                matrix[expiry] = {}
            if strike not in matrix[expiry]:
                matrix[expiry][strike] = {}
            matrix[expiry][strike][opt_type] = iv

        return {"count": len(rows), "data": matrix, "trade_date": date, "variety": variety}
    finally:
        conn.close()


@router.get("/iv/smile", summary="IV 微笑曲线", description="获取微笑曲线数据")
@cache_result("iv_smile", ttl=86400, tags=["iv"])
def get_iv_smile(
    variety: Optional[str] = Query("MO"),
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    expiry: Optional[str] = Query(None, description="到期日 YYYY-MM-DD"),
):
    """Query IV smile curve data."""
    import sqlite3
    from tzdata_pkg.config import TZDATA_TRADING_DB

    if not date:
        date = "2099-12-31"

    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        td_normalized = date.replace("-", "")[:8]
        where = "trade_date = ? AND underlying = ?"
        params = [td_normalized, variety]

        if expiry:
            where += " AND expire_date = ?"
            params.append(expiry)

        rows = conn.execute(f"""
            SELECT expire_date, strike, iv, option_type
            FROM mo_daily_iv_quotes
            WHERE {where} AND iv IS NOT NULL AND strike IS NOT NULL
            ORDER BY strike
        """, params).fetchall()

        # Build smile data
        expiries = {}
        for expiry_date, strike, iv, opt_type in rows:
            if expiry_date not in expiries:
                expiries[expiry_date] = {"strikes": [], "call_iv": [], "put_iv": [], "strike_iv": {}}
            if strike not in expiries[expiry_date]["strike_iv"]:
                expiries[expiry_date]["strikes"].append(strike)
                expiries[expiry_date]["strike_iv"][strike] = {}
            expiries[expiry_date]["strike_iv"][strike][opt_type] = iv

        return {
            "count": len(rows),
            "data": expiries,
            "trade_date": date,
            "variety": variety,
        }
    finally:
        conn.close()


@router.get("/iv/percentile", summary="IV 历史分位数", description="获取 IV 历史分位数")
@cache_result("iv_percentile", ttl=3600, tags=["iv"])
def get_iv_percentile(
    variety: Optional[str] = Query("MO"),
    date: Optional[str] = Query(None),
):
    """Query IV historical percentile."""
    import sqlite3
    from tzdata_pkg.config import TZDATA_TRADING_DB

    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        rows = conn.execute("""
            SELECT trade_date, atm_iv, iv_percentile_1y, iv_regime
            FROM iv_benchmark
            WHERE variety = ? AND atm_iv IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT 252
        """, (variety,)).fetchall()

        if not rows:
            return {"count": 0, "data": []}

        current_iv = rows[0][1]
        ivs = [r[1] for r in rows if r[1] is not None]
        percentiles_30d = 0
        percentiles_90d = 0
        percentiles_252d = 0

        if ivs:
            sorted_ivs = sorted(ivs)
            for window in [30, 90, 252]:
                subset = sorted_ivs[:min(window, len(sorted_ivs))]
                rank = sum(1 for v in subset if v < current_iv)
                pct = (rank / len(subset)) * 100 if subset else 0
                if window == 30:
                    percentiles_30d = pct
                elif window == 90:
                    percentiles_90d = pct
                else:
                    percentiles_252d = pct

        data = [
            {"trade_date": r[0], "atm_iv": r[1], "percentile_1y": r[2], "regime": r[3]}
            for r in rows
        ]

        return {
            "count": len(data),
            "current_iv": current_iv,
            "percentile_30d": round(percentiles_30d, 1),
            "percentile_90d": round(percentiles_90d, 1),
            "percentile_252d": round(percentiles_252d, 1),
            "data": data,
        }
    finally:
        conn.close()


@router.get("/iv/term-structure", summary="IV 期限结构", description="获取期限结构数据")
@cache_result("iv_term_structure", ttl=3600, tags=["iv"])
def get_iv_term_structure(
    variety: Optional[str] = Query("MO"),
    date: Optional[str] = Query(None),
):
    """Query IV term structure."""
    import sqlite3
    from tzdata_pkg.config import TZDATA_TRADING_DB

    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        if date:
            td = date.replace("-", "")[:8]
        else:
            td = conn.execute(
                "SELECT MAX(trade_date) FROM mo_daily_iv_quotes WHERE underlying = ?",
                (variety,)
            ).fetchone()[0]

        if not td:
            return {"count": 0, "data": []}

        # Get spot price
        code = {"MO": "000852", "IO": "000300", "HO": "000016"}.get(variety, "000852")
        spot_row = conn.execute("""
            SELECT close FROM option_sim_underlying_daily
            WHERE underlying = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 1
        """, (code, td)).fetchone()
        spot = float(spot_row[0]) if spot_row and spot_row[0] else None

        rows = conn.execute("""
            SELECT expire_date, strike, iv FROM mo_daily_iv_quotes
            WHERE trade_date = ? AND underlying = ?
              AND iv IS NOT NULL AND strike IS NOT NULL AND expire_date IS NOT NULL
        """, (td, variety)).fetchall()

        # Group by expiry, find ATM IV for each
        from collections import defaultdict
        expiry_groups = defaultdict(list)
        for exp, strike, iv in rows:
            expiry_groups[exp].append((float(strike), float(iv)))

        term_data = []
        for exp in sorted(expiry_groups):
            if spot:
                best = min(expiry_groups[exp], key=lambda c: abs(c[0] - spot))
            else:
                best = expiry_groups[exp][0]
            term_data.append({"expiry_date": exp, "atm_iv": round(best[1], 4),
                              "atm_strike": round(best[0], 1)})

        return {"count": len(term_data), "data": term_data, "spot": spot, "trade_date": td}
    finally:
        conn.close()


@router.get("/iv/cross-variety", summary="跨品种对比", description="获取 MO/IO/HO 对比数据")
@cache_result("iv_cross_variety", ttl=3600, tags=["iv"])
def get_iv_cross_variety(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    """Query cross-variety IV comparison."""
    import sqlite3
    from tzdata_pkg.config import TZDATA_TRADING_DB

    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        where = []
        params = []
        if start:
            where.append("trade_date >= ?")
            params.append(start)
        if end:
            where.append("trade_date <= ?")
            params.append(end)
        where_sql = "WHERE " + " AND ".join(where) if where else ""

        rows = conn.execute(f"""
            SELECT trade_date, variety, atm_iv, hv_20, hv_60, iv_hv_spread, iv_regime
            FROM iv_benchmark {where_sql}
            ORDER BY trade_date, variety
        """, params).fetchall()

        cols = ["trade_date", "variety", "atm_iv", "hv_20", "hv_60", "iv_hv_spread", "iv_regime"]
        data = [dict(zip(cols, row)) for row in rows]

        return {"count": len(data), "data": data}
    finally:
        conn.close()


@router.get("/iv/iv-hv-spread", summary="IV-HV 价差", description="获取 IV-HV 价差时序")
@cache_result("iv_hv_spread", ttl=3600, tags=["iv"])
def get_iv_hv_spread(
    variety: Optional[str] = Query("MO"),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    """Query IV-HV spread time series."""
    import sqlite3
    from tzdata_pkg.config import TZDATA_TRADING_DB

    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        where = ["variety = ?"]
        params = [variety]
        if start:
            where.append("trade_date >= ?")
            params.append(start)
        if end:
            where.append("trade_date <= ?")
            params.append(end)
        where_sql = "WHERE " + " AND ".join(where)

        rows = conn.execute(f"""
            SELECT trade_date, atm_iv, hv_20, hv_60, iv_hv_spread
            FROM iv_benchmark {where_sql}
            ORDER BY trade_date
        """, params).fetchall()

        data = [
            {
                "trade_date": r[0], "atm_iv": r[1],
                "hv_20": r[2], "hv_60": r[3], "iv_hv_spread": r[4],
            }
            for r in rows if r[4] is not None
        ]

        return {"count": len(data), "data": data}
    finally:
        conn.close()


@router.get("/iv/correlation", summary="IV-标的关联", description="获取 IV-标的滚动相关系数")
@cache_result("iv_correlation", ttl=3600, tags=["iv"])
def get_iv_correlation(
    variety: Optional[str] = Query("MO"),
    window: Optional[int] = Query(60, description="滚动窗口"),
):
    """Query IV-underlying correlation."""
    import sqlite3
    import math
    from tzdata_pkg.config import TZDATA_TRADING_DB

    conn = sqlite3.connect(str(TZDATA_TRADING_DB))
    try:
        # Get IV daily changes
        iv_rows = conn.execute("""
            SELECT trade_date, atm_iv FROM iv_benchmark
            WHERE variety = ? AND atm_iv IS NOT NULL
            ORDER BY trade_date
        """, (variety,)).fetchall()

        if len(iv_rows) < window:
            return {"count": 0, "data": [], "reason": "insufficient_data"}

        # Compute daily IV changes
        iv_changes = []
        for i in range(1, len(iv_rows)):
            prev_iv = iv_rows[i - 1][1]
            cur_iv = iv_rows[i][1]
            if prev_iv and cur_iv:
                iv_changes.append((iv_rows[i][0], (cur_iv - prev_iv) / prev_iv * 100))

        # Get underlying returns
        code = {"MO": "000852", "IO": "000300", "HO": "000016"}.get(variety, "000852")
        price_rows = conn.execute("""
            SELECT trade_date, close FROM option_sim_underlying_daily
            WHERE underlying = ?
            ORDER BY trade_date
        """, (code,)).fetchall()

        returns = []
        for i in range(1, len(price_rows)):
            prev = price_rows[i - 1][1]
            cur = price_rows[i][1]
            if prev and cur:
                returns.append((price_rows[i][0], math.log(cur / prev) * 100))

        # Align and compute rolling correlation
        iv_map = {r[0]: r[1] for r in iv_changes}
        ret_map = {r[0]: r[1] for r in returns}
        common_dates = sorted(set(iv_map.keys()) & set(ret_map.keys()))

        rolling_corr = []
        for i in range(window - 1, len(common_dates)):
            window_dates = common_dates[i - window + 1: i + 1]
            iv_vals = [iv_map[d] for d in window_dates]
            ret_vals = [ret_map[d] for d in window_dates]

            n = len(iv_vals)
            if n < 5:
                continue

            mean_iv = sum(iv_vals) / n
            mean_ret = sum(ret_vals) / n
            cov = sum((iv_vals[j] - mean_iv) * (ret_vals[j] - mean_ret) for j in range(n)) / (n - 1)
            std_iv = math.sqrt(sum((v - mean_iv) ** 2 for v in iv_vals) / (n - 1))
            std_ret = math.sqrt(sum((v - mean_ret) ** 2 for v in ret_vals) / (n - 1))

            if std_iv > 0 and std_ret > 0:
                corr = cov / (std_iv * std_ret)
                rolling_corr.append({
                    "trade_date": window_dates[-1],
                    "correlation": round(corr, 4),
                    "window": window,
                })

        return {"count": len(rolling_corr), "data": rolling_corr}
    finally:
        conn.close()
