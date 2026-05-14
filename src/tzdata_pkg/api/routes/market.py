"""Market data routes: quotes and contracts."""

from typing import Optional
from fastapi import APIRouter, Query

from tzdata_pkg.query import TzDataClient

router = APIRouter()


@router.get("/quotes")
def get_quotes(
    exchange: Optional[str] = Query(None, description="Exchange code (CFFEX, SHFE)"),
    contract: Optional[str] = Query(None, description="Contract code"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=5000),
):
    """Query quote data."""
    with TzDataClient() as client:
        results = client.quotes(
            exchange=exchange, contract=contract,
            start_date=start_date, end_date=end_date,
        )
    return {"count": len(results), "data": results[:limit]}


@router.get("/contracts")
def list_contracts(
    exchange: Optional[str] = Query(None, description="Filter by exchange"),
):
    """List available contracts."""
    with TzDataClient() as client:
        results = client.contracts(exchange=exchange)
    return {"count": len(results), "data": results}
