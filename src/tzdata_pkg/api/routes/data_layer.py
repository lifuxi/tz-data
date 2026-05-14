"""
Data layer API endpoints.

| Method | Path | 说明 |
|--------|------|------|
| GET | /api/v1/bills/{bill_id}/fund-flows | 获取账单资金流水 |
| GET | /api/v1/market/index/{code}/daily | 指数日线数据 |
| GET | /api/v1/options/greeks/{date} | 指定日期希腊字母 |
| GET | /api/v1/contracts/{symbol}/expiry | 合约到期信息 |
"""
import logging
import sqlite3
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data-layer"])

TZDATA_TRADING_DB = "C:/myspace/tz-data/data/tzdata_trading.db"


def get_db() -> sqlite3.Connection:
    """Get a SQLite connection to the trading database."""
    try:
        conn = sqlite3.connect(TZDATA_TRADING_DB)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")


@router.get("/bills/{bill_id}/fund-flows")
def get_bill_fund_flows(
    bill_id: int,
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    flow_type: Optional[str] = Query(None, description="Filter by flow type"),
):
    """获取账单资金流水。"""
    conn = get_db()
    try:
        sql = "SELECT * FROM bill_fund_flows WHERE bill_id = ?"
        params: list = [bill_id]

        if start_date:
            sql += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND trade_date <= ?"
            params.append(end_date)
        if flow_type:
            sql += " AND flow_type = ?"
            params.append(flow_type)

        sql += " ORDER BY trade_date, id"

        rows = conn.execute(sql, params).fetchall()
        flows = [dict(row) for row in rows]

        return {
            "bill_id": bill_id,
            "flows": flows,
            "count": len(flows),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching fund flows for bill {bill_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/market/index/{code}/daily")
def get_index_daily(
    code: str,
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
):
    """获取指数日线数据。

    Args:
        code: 指数代码，如 000852（中证1000）、000300（沪深300）
    """
    conn = get_db()
    try:
        sql = "SELECT * FROM daily_index_prices WHERE index_code = ?"
        params: list = [code]

        if start_date:
            sql += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND trade_date <= ?"
            params.append(end_date)

        sql += " ORDER BY trade_date"

        rows = conn.execute(sql, params).fetchall()
        data = [dict(row) for row in rows]

        return {
            "index_code": code,
            "data": data,
            "count": len(data),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching index daily for {code}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/options/greeks/{date}")
def get_option_greeks(
    date: str,
    symbol: Optional[str] = Query(None, description="Filter by option symbol"),
):
    """获取指定日期的期权希腊字母数据。"""
    conn = get_db()
    try:
        sql = "SELECT * FROM option_greeks_daily WHERE trade_date = ?"
        params: list = [date]

        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol)

        sql += " ORDER BY symbol"

        rows = conn.execute(sql, params).fetchall()
        data = [dict(row) for row in rows]

        return {
            "trade_date": date,
            "greeks": data,
            "count": len(data),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching option greeks for {date}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/contracts/{symbol}/expiry")
def get_contract_expiry(symbol: str):
    """获取合约到期信息。"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM contract_expiry WHERE symbol = ?",
            (symbol,)
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Contract not found: {symbol}"
            )

        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching contract expiry for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
