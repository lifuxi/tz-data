"""Realtime market data API routes — 12 new endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()


def _get_market_pool():
    from tzdata_pkg.storage.db_registry import DBRegistry
    return DBRegistry().get_pool("market")


def _get_adapter():
    """Get the MarketDataAdapter singleton from app state."""
    from tzdata_pkg.api.server import app
    return getattr(app.state, "market_adapter", None)


# ========== Catalog CRUD ==========

@router.get("/catalog", summary="数据目录列表")
def get_catalog(
    is_active: Optional[int] = Query(None, description="1=enabled, 0=disabled"),
    exchange: Optional[str] = Query(None),
    asset_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """Query market data catalog with filters."""
    pool = _get_market_pool()
    conditions = []
    params = []
    if is_active is not None:
        conditions.append("is_active = ?")
        params.append(is_active)
    if exchange:
        conditions.append("exchange = ?")
        params.append(exchange)
    if asset_type:
        conditions.append("asset_type = ?")
        params.append(asset_type)

    where = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * page_size

    try:
        with pool.connection() as conn:
            cur = conn.execute(f"SELECT COUNT(*) FROM market_data_catalog WHERE {where}", params)
            total = cur.fetchone()[0]
            cur = conn.execute(
                f"SELECT * FROM market_data_catalog WHERE {where} ORDER BY symbol LIMIT ? OFFSET ?",
                params + [page_size, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]
            return {"total": total, "page": page, "page_size": page_size, "items": rows}
    except Exception as e:
        return {"total": 0, "page": page, "page_size": page_size, "items": [], "error": str(e)}


@router.post("/catalog", summary="新增数据目录条目")
def create_catalog_item(
    symbol: str,
    product_id: Optional[str] = None,
    exchange: Optional[str] = None,
    asset_type: str = "FUTURE",
    real_time_source: Optional[str] = None,
    backup_source: Optional[str] = None,
    historical_source: Optional[str] = None,
    subscribe_from: Optional[str] = None,
    subscribe_until: Optional[str] = None,
):
    """Add a new symbol to the catalog."""
    pool = _get_market_pool()
    try:
        with pool.transaction() as conn:
            conn.execute(
                """INSERT INTO market_data_catalog
                   (symbol, product_id, exchange, asset_type, is_active,
                    real_time_source, backup_source, historical_source,
                    subscribe_from, subscribe_until)
                   VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                   ON CONFLICT(symbol) DO UPDATE SET
                       product_id=excluded.product_id,
                       exchange=excluded.exchange,
                       asset_type=excluded.asset_type,
                       real_time_source=excluded.real_time_source,
                       backup_source=excluded.backup_source,
                       historical_source=excluded.historical_source,
                       subscribe_from=excluded.subscribe_from,
                       subscribe_until=excluded.subscribe_until""",
                (symbol, product_id, exchange, asset_type,
                 real_time_source, backup_source, historical_source,
                 subscribe_from, subscribe_until),
            )
        return {"status": "ok", "symbol": symbol}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.put("/catalog/{symbol}", summary="更新数据目录条目")
def update_catalog_item(
    symbol: str,
    is_active: Optional[int] = None,
    real_time_source: Optional[str] = None,
    backup_source: Optional[str] = None,
    subscribe_until: Optional[str] = None,
):
    """Update catalog entry: toggle active, switch source, change expiry."""
    pool = _get_market_pool()
    updates = []
    params = []
    if is_active is not None:
        updates.append("is_active = ?")
        params.append(is_active)
    if real_time_source is not None:
        updates.append("real_time_source = ?")
        params.append(real_time_source)
    if backup_source is not None:
        updates.append("backup_source = ?")
        params.append(backup_source)
    if subscribe_until is not None:
        updates.append("subscribe_until = ?")
        params.append(subscribe_until)

    if not updates:
        return {"status": "error", "message": "No fields to update"}

    params.append(symbol)
    try:
        with pool.transaction() as conn:
            conn.execute(
                f"UPDATE market_data_catalog SET {', '.join(updates)} WHERE symbol = ?",
                params,
            )
        return {"status": "ok", "symbol": symbol}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========== Source Status & Control ==========

@router.get("/sources", summary="所有数据源状态")
def get_sources():
    """List all data source statuses."""
    from tzdata_pkg.market.status_service import StatusService
    svc = StatusService(_get_market_pool())
    return {"sources": svc.get_all_sources()}


@router.get("/sources/{name}/health", summary="单个数据源健康检查")
def get_source_health(name: str):
    """Check single source health."""
    from tzdata_pkg.market.status_service import StatusService
    svc = StatusService(_get_market_pool())
    source = svc.get_source(name)
    if not source:
        return {"status": "error", "message": f"Source {name} not found"}

    # Also check driver heartbeat if adapter is running
    adapter = _get_adapter()
    if adapter and name in adapter._drivers:
        import asyncio
        try:
            heartbeat = asyncio.get_event_loop().run_until_complete(
                adapter._drivers[name].heartbeat()
            )
            source["driver_heartbeat"] = heartbeat
        except Exception:
            pass

    return {"source": source}


@router.post("/sources/{name}/connect", summary="连接数据源")
def connect_source(name: str):
    """Connect/reconnect a data source."""
    adapter = _get_adapter()
    if not adapter or name not in adapter._drivers:
        return {"status": "error", "message": f"Driver {name} not loaded"}

    import asyncio
    async def _connect():
        config = adapter._driver_configs.get(name, {})
        await adapter._drivers[name].connect(config)

    try:
        asyncio.get_event_loop().run_until_complete(_connect())
        from tzdata_pkg.market.event_logger import MarketEventLogger
        logger = MarketEventLogger(_get_market_pool())
        logger.log("connect", source_name=name, message=f"Source {name} connected via API")
        return {"status": "ok", "source": name}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/sources/{name}/disconnect", summary="断开数据源")
def disconnect_source(name: str):
    """Disconnect a data source."""
    adapter = _get_adapter()
    if not adapter or name not in adapter._drivers:
        return {"status": "error", "message": f"Driver {name} not loaded"}

    import asyncio
    try:
        asyncio.get_event_loop().run_until_complete(adapter._drivers[name].disconnect())
        return {"status": "ok", "source": name}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========== Quality Metrics ==========

@router.get("/quality", summary="质量指标查询")
def get_quality_metrics(
    symbol: Optional[str] = Query(None),
    trade_date: Optional[str] = Query(None),
    source_name: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """Query data quality metrics."""
    pool = _get_market_pool()
    conditions = []
    params = []
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol)
    if trade_date:
        conditions.append("trade_date = ?")
        params.append(trade_date)
    if source_name:
        conditions.append("source_name = ?")
        params.append(source_name)

    where = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * page_size

    try:
        with pool.connection() as conn:
            cur = conn.execute(
                f"SELECT COUNT(*) FROM data_quality_metrics WHERE {where}", params,
            )
            total = cur.fetchone()[0]
            cur = conn.execute(
                f"SELECT * FROM data_quality_metrics WHERE {where} ORDER BY trade_date DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]
            return {"total": total, "page": page, "items": rows}
    except Exception as e:
        return {"total": 0, "page": page, "items": [], "error": str(e)}


@router.get("/quality/summary", summary="质量汇总")
def get_quality_summary():
    """Quality summary: latency curve, heatmap, stats."""
    pool = _get_market_pool()
    try:
        with pool.connection() as conn:
            # Today's stats
            cur = conn.execute(
                """SELECT COUNT(*) as total_sources,
                          AVG(quality_score) as avg_score,
                          MIN(quality_score) as min_score,
                          SUM(gap_count) as total_gaps,
                          SUM(suspect_count) as total_suspects
                   FROM data_quality_metrics
                   WHERE trade_date = date('now')""",
            )
            row = dict(cur.fetchone())

            # Per-source latency
            cur = conn.execute(
                """SELECT source_name, AVG(delay_ms) as avg_delay,
                          MAX(delay_ms) as max_delay,
                          COUNT(*) as samples
                   FROM data_quality_metrics
                   WHERE trade_date = date('now')
                   GROUP BY source_name""",
            )
            sources = [dict(r) for r in cur.fetchall()]

            # Symbol health heatmap data
            cur = conn.execute(
                """SELECT symbol, quality_score,
                          CASE
                            WHEN quality_score >= 90 THEN 'green'
                            WHEN quality_score >= 60 THEN 'yellow'
                            ELSE 'red'
                          END as status
                   FROM data_quality_metrics
                   WHERE trade_date = date('now')""",
            )
            heatmap = [dict(r) for r in cur.fetchall()]

            return {
                "summary": row,
                "sources": sources,
                "heatmap": heatmap,
            }
    except Exception as e:
        return {"error": str(e)}


# ========== Event Log ==========

@router.get("/events", summary="事件日志查询")
def get_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None),
    source_name: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
):
    """Query event log with pagination and filters."""
    from tzdata_pkg.market.event_logger import MarketEventLogger
    logger = MarketEventLogger(_get_market_pool())
    rows, total = logger.query(
        page=page, page_size=page_size, severity=severity,
        source_name=source_name, event_type=event_type,
        start_time=start_time, end_time=end_time,
    )
    return {"total": total, "page": page, "page_size": page_size, "items": rows}


# ========== Realtime Snapshots ==========

@router.get("/realtime/{symbol}", summary="单个 symbol 最新快照")
def get_realtime_snapshot(symbol: str):
    """Get latest realtime snapshot for a symbol."""
    adapter = _get_adapter()
    if adapter:
        data = adapter.get_snapshot(symbol)
        if data:
            return {"symbol": symbol, "data": data}

    # Fallback to SQLite
    pool = _get_market_pool()
    try:
        with pool.connection() as conn:
            cur = conn.execute(
                "SELECT data_json, source_name, updated_at FROM realtime_snapshots_cache WHERE symbol = ?",
                (symbol,),
            )
            row = cur.fetchone()
            if row:
                import json
                return {"symbol": symbol, "data": json.loads(row["data_json"]), "source": row["source_name"], "updated_at": row["updated_at"]}
    except Exception:
        pass

    return {"symbol": symbol, "data": None, "error": "No data available"}


@router.get("/realtime/batch", summary="批量 symbol 最新快照")
def get_batch_snapshots(
    symbols: str = Query(..., description="Comma-separated symbol list"),
):
    """Get latest snapshots for multiple symbols."""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    adapter = _get_adapter()
    if adapter:
        data = adapter.get_batch_snapshots(symbol_list)
        if data:
            return {"count": len(data), "quotes": data}

    # Fallback to SQLite
    pool = _get_market_pool()
    try:
        with pool.connection() as conn:
            placeholders = ",".join("?" * len(symbol_list))
            cur = conn.execute(
                f"SELECT data_json FROM realtime_snapshots_cache WHERE symbol IN ({placeholders})",
                symbol_list,
            )
            import json
            results = [json.loads(row["data_json"]) for row in cur.fetchall()]
            return {"count": len(results), "quotes": results}
    except Exception as e:
        return {"count": 0, "quotes": [], "error": str(e)}


# ========== Adapter Stats ==========

@router.get("/stats", summary="适配器统计")
def get_adapter_stats():
    """Get market adapter statistics."""
    adapter = _get_adapter()
    if adapter:
        return adapter.get_stats()
    return {"error": "Adapter not initialized"}
