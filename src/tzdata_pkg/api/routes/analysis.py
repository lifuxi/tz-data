"""Analysis data routes: signals, regime, institution features, option data."""

from typing import Optional
from fastapi import APIRouter, Query

from tzdata_pkg.query import TzDataClient

router = APIRouter()


@router.get("/signals")
def get_signals(
    signal_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Query trading signals."""
    with TzDataClient() as client:
        results = client.signals(signal_type=signal_type, start_date=start_date, end_date=end_date)
    return {"count": len(results), "data": results}


@router.get("/regime")
def get_market_regime(
    trade_date: Optional[str] = Query(None),
):
    """Query market regime classification."""
    with TzDataClient() as client:
        results = client.market_regime(trade_date=trade_date)
    return {"count": len(results), "data": results}


@router.get("/institution-features")
def get_institution_features(
    member_name: Optional[str] = Query(None),
    trade_date: Optional[str] = Query(None),
):
    """Query institution feature data."""
    with TzDataClient() as client:
        results = client.institution_features(member_name=member_name, trade_date=trade_date)
    return {"count": len(results), "data": results}


@router.get("/option-features")
def get_option_features(
    trade_date: Optional[str] = Query(None),
    contract: Optional[str] = Query(None),
):
    """Query option feature data with Greeks."""
    with TzDataClient() as client:
        results = client.option_features(trade_date=trade_date, contract=contract)
    return {"count": len(results), "data": results}


@router.get("/iv-snapshot")
def get_iv_snapshot(
    trade_date: Optional[str] = Query(None),
    underlying: Optional[str] = Query(None),
):
    """Query implied volatility snapshot."""
    with TzDataClient() as client:
        results = client.iv_snapshot(trade_date=trade_date, underlying=underlying)
    return {"count": len(results), "data": results}


@router.get("/tushare-daily")
def get_tushare_daily(
    ts_code: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Query Tushare daily data."""
    with TzDataClient() as client:
        results = client.tushare_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    return {"count": len(results), "data": results}
