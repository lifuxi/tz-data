"""Position routes: position rankings and top holders."""

from typing import Optional
from fastapi import APIRouter, Query

from tzdata_pkg.query import TzDataClient

router = APIRouter()


@router.get("/{product}", summary="品种持仓排名", description="查询指定品种的机构持仓排名数据")
def get_positions(
    product: str,
    trade_date: Optional[str] = Query(None, description="Trade date YYYY-MM-DD"),
):
    """Query position ranking data for a product."""
    with TzDataClient() as client:
        results = client.positions(contract=product, trade_date=trade_date)
    return {"count": len(results), "product": product, "data": results}


@router.get("/{product}/top-holders", summary="主力持仓集中度", description="查询指定品种的主力会员持仓集中度")
def get_top_holders(
    product: str,
    trade_date: Optional[str] = Query(None, description="Trade date YYYY-MM-DD"),
):
    """Query top holder concentration for a product."""
    with TzDataClient() as client:
        results = client.top_holders(contract=product, trade_date=trade_date)
    return {"count": len(results), "product": product, "data": results}
