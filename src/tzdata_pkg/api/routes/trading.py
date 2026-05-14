"""Trading data routes: bills, trades, P&L."""

from typing import Optional
from fastapi import APIRouter, Query

from tzdata_pkg.query import TzDataClient

router = APIRouter()


@router.get("/bills")
def get_bills(
    account_id: Optional[str] = Query(None, description="Account ID"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
):
    """List bills."""
    with TzDataClient() as client:
        results = client.bills(account_id=account_id)
    return {"count": len(results), "data": results}


@router.get("/trades")
def get_trades(
    account_id: Optional[str] = Query(None, description="Account ID"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
):
    """List trade records."""
    with TzDataClient() as client:
        results = client.trades(account_id=account_id, start_date=start_date, end_date=end_date)
    return {"count": len(results), "data": results}


@router.get("/pnl")
def get_pnl(
    account_id: Optional[str] = Query(None, description="Account ID"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
):
    """P&L summary."""
    with TzDataClient() as client:
        summary = client.pnl_summary(
            account_id=account_id, start_date=start_date, end_date=end_date,
        )
    return summary


@router.get("/account-summary")
def get_account_summary(account_id: Optional[str] = Query(None)):
    """Account summary."""
    with TzDataClient() as client:
        summary = client.account_summary(account_id=account_id)
    return summary
