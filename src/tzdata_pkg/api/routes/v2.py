"""Shared data API v2 — paginated, filtered access to trading data.

Provides standardized endpoints for tz2.0 and other consumers to query
bills, trades, positions, accounts, fund flows, and snapshots via HTTP
instead of direct SQLite file reads.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


def _trading_pool():
    from tzdata_pkg.storage.db_registry import DBRegistry
    return DBRegistry().get_pool("trading")


def _rows_to_dicts(cursor, rows):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in rows]


def _paginate(table: str, where_clauses: list[str], params: list,
              page: int, page_size: int, order_by: str = "id DESC"):
    """Execute paginated query with COUNT total."""
    where = " AND ".join(where_clauses) if where_clauses else "1=1"
    pool = _trading_pool()
    with pool.connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}", params
        ).fetchone()[0]
        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM {table} WHERE {where} ORDER BY {order_by} LIMIT {page_size} OFFSET {offset}",
            params,
        )
        rows = _rows_to_dicts(cursor, cursor.fetchall())
    return {"data": rows, "total": total, "page": page, "page_size": page_size}


# ── Bills ──────────────────────────────────────────────────────────


@router.get("/bills", summary="账单列表（分页）")
def list_bills(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    account_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    clauses, params = [], []
    if account_id:
        clauses.append("account_id = ?")
        params.append(account_id)
    if start_date:
        clauses.append("bill_date_start >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("bill_date_start <= ?")
        params.append(end_date)
    return _paginate("bills", clauses, params, page, page_size, "bill_date_start DESC")


@router.get("/bills/{bill_id}", summary="账单详情")
def get_bill(bill_id: int):
    pool = _trading_pool()
    with pool.connection() as conn:
        cursor = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,))
        rows = _rows_to_dicts(cursor, cursor.fetchall())
    if not rows:
        raise HTTPException(status_code=404, detail=f"Bill {bill_id} not found")
    return rows[0]


# ── Trades ─────────────────────────────────────────────────────────


@router.get("/trades", summary="交易记录（分页）")
def list_trades(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    account_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    instrument: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    offset_flag: Optional[str] = Query(None),
):
    clauses, params = [], []
    if account_id:
        clauses.append("account_id = ?")
        params.append(account_id)
    if start_date:
        clauses.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("trade_date <= ?")
        params.append(end_date)
    if instrument:
        clauses.append("instrument = ?")
        params.append(instrument)
    if direction:
        clauses.append("direction = ?")
        params.append(direction)
    if offset_flag:
        clauses.append("offset_flag = ?")
        params.append(offset_flag)
    return _paginate("trades", clauses, params, page, page_size, "trade_date DESC, id DESC")


# ── Positions ──────────────────────────────────────────────────────


@router.get("/positions", summary="持仓汇总（分页）")
def list_positions(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    instrument: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    clauses, params = [], []
    if instrument:
        clauses.append("instrument = ?")
        params.append(instrument)
    if start_date:
        clauses.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("trade_date <= ?")
        params.append(end_date)
    return _paginate("positions_summary", clauses, params, page, page_size, "trade_date DESC, instrument")


# ── Accounts ───────────────────────────────────────────────────────


@router.get("/accounts", summary="账户概览（分页）")
def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    account_id: Optional[str] = Query(None),
):
    clauses, params = [], []
    if account_id:
        clauses.append("account_id = ?")
        params.append(account_id)
    return _paginate("account_summary", clauses, params, page, page_size, "year DESC, month DESC")


# ── Fund Flows ─────────────────────────────────────────────────────


@router.get("/fund-flows/{bill_id}", summary="资金流水分类（分页）")
def list_fund_flows(
    bill_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    flow_type: Optional[str] = Query(None),
    flow_category: Optional[str] = Query(None),
):
    clauses, params = ["bill_id = ?"], [bill_id]
    if flow_type:
        clauses.append("flow_type = ?")
        params.append(flow_type)
    if flow_category:
        clauses.append("flow_category = ?")
        params.append(flow_category)
    return _paginate("capital_transactions_classified", clauses, params, page, page_size, "trade_date DESC")


# ── Snapshots ──────────────────────────────────────────────────────


@router.get("/snapshots", summary="日快照（分页）")
def list_snapshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    clauses, params = [], []
    if start_date:
        clauses.append("snapshot_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("snapshot_date <= ?")
        params.append(end_date)
    return _paginate("daily_account_snapshots", clauses, params, page, page_size, "snapshot_date DESC")


# ── Minute Quotes (Viewpoint 5) ──────────────────────────────────


def _market_pool():
    from tzdata_pkg.storage.db_registry import DBRegistry
    return DBRegistry().get_pool("market")


def _paginate_market(table: str, where_clauses: list[str], params: list,
                     page: int, page_size: int, order_by: str = "id DESC"):
    """Paginated query on market DB."""
    where = " AND ".join(where_clauses) if where_clauses else "1=1"
    pool = _market_pool()
    with pool.connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}", params
        ).fetchone()[0]
        offset = (page - 1) * page_size
        cursor = conn.execute(
            f"SELECT * FROM {table} WHERE {where} ORDER BY {order_by} LIMIT {page_size} OFFSET {offset}",
            params,
        )
        rows = _rows_to_dicts(cursor, cursor.fetchall())
    return {"data": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/minute-quotes", summary="分钟级行情（分页）")
def list_minute_quotes(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    contract_code: Optional[str] = Query(None),
    trade_date: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    frequency: Optional[str] = Query(None, description="1min, 5min, etc."),
):
    """Query minute-level price data.

    Supports QuestDB-backed and SQLite sources. Returns paginated
    OHLCV minute bars filtered by contract and date range.
    """
    clauses, params = [], []
    if contract_code:
        clauses.append("contract_code = ?")
        params.append(contract_code)
    if trade_date:
        clauses.append("trade_date = ?")
        params.append(trade_date)
    if start_date:
        clauses.append("trade_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("trade_date <= ?")
        params.append(end_date)
    if frequency:
        clauses.append("frequency = ?")
        params.append(frequency)

    return _paginate_market(
        "minute_quotes", clauses, params, page, page_size,
        "trade_date ASC, trade_time ASC",
    )


@router.get("/minute-quotes/summary", summary="分钟行情摘要")
def minute_quotes_summary(
    contract_code: str = Query(...),
    trade_date: Optional[str] = Query(None),
):
    """Get summary stats for a contract on a given date:
    bar count, OHLC range, volume total, gap count.
    """
    pool = _market_pool()
    date_clause = "AND trade_date = ?" if trade_date else ""
    params = [contract_code]
    if trade_date:
        params.append(trade_date)

    with pool.connection() as conn:
        row = conn.execute(f"""
            SELECT COUNT(*) as bar_count,
                   MIN(trade_time) as first_time,
                   MAX(trade_time) as last_time,
                   MIN(low) as low,
                   MAX(high) as high,
                   SUM(volume) as total_volume,
                   SUM(amount) as total_amount,
                   COUNT(DISTINCT trade_date) as day_count
            FROM minute_quotes
            WHERE contract_code = ? {date_clause}
        """, params).fetchone()

        if not row or row[0] == 0:
            return {"contract_code": contract_code, "bar_count": 0}

        cols = ["bar_count", "first_time", "last_time", "low", "high",
                "total_volume", "total_amount", "day_count"]
        return {"contract_code": contract_code, **dict(zip(cols, row))}


@router.get("/minute-quotes/contracts", summary="有分钟行情的合约列表")
def minute_contracts(trade_date: Optional[str] = Query(None)):
    """List all contracts that have minute data."""
    pool = _market_pool()
    date_clause = "WHERE trade_date = ?" if trade_date else ""
    params = [trade_date] if trade_date else []

    with pool.connection() as conn:
        cursor = conn.execute(f"""
            SELECT DISTINCT contract_code
            FROM minute_quotes
            {date_clause}
            ORDER BY contract_code
        """, params)
        return {"contracts": [row[0] for row in cursor.fetchall()]}


@router.get("/minute-quotes/frequencies/{contract_code}", summary="合约可用频率列表")
def list_frequencies(contract_code: str, trade_date: Optional[str] = Query(None)):
    """List frequencies available for a contract."""
    pool = _market_pool()
    date_clause = "AND trade_date = ?" if trade_date else ""
    params = [contract_code]
    if trade_date:
        params.append(trade_date)

    with pool.connection() as conn:
        cursor = conn.execute(f"""
            SELECT frequency, COUNT(*) as bar_count,
                   MIN(trade_date) as min_date, MAX(trade_date) as max_date
            FROM minute_quotes
            WHERE contract_code = ? {date_clause}
            GROUP BY frequency
            ORDER BY
                CASE frequency
                    WHEN '1min' THEN 1
                    WHEN '5min' THEN 2
                    WHEN '15min' THEN 3
                    WHEN '30min' THEN 4
                    WHEN '60min' THEN 5
                    ELSE 9
                END
        """, params)
        rows = cursor.fetchall()

    return {
        "contract_code": contract_code,
        "frequencies": [
            {"frequency": row[0], "bar_count": row[1],
             "min_date": row[2], "max_date": row[3]}
            for row in rows
        ],
    }
