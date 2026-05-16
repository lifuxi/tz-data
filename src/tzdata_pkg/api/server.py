"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from tzdata_pkg.api.routes.market import router as market_router
from tzdata_pkg.api.routes.positions import router as positions_router
from tzdata_pkg.api.routes.trading import router as trading_router
from tzdata_pkg.api.routes.analysis import router as analysis_router
from tzdata_pkg.api.routes.admin import router as admin_router
from tzdata_pkg.api.routes.maintenance import router as maintenance_router
from tzdata_pkg.api.routes.data_layer import router as data_layer_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: run schema migrations
    try:
        from tzdata_pkg.maintenance.metadata.migrate_calendar_v3 import migrate
        migrate()
        logger.info("Calendar schema migration v3 applied")
    except Exception as e:
        logger.warning(f"Calendar migration v3 failed: {e}")

    try:
        from tzdata_pkg.maintenance.metadata.migrate_data_layer_v4 import migrate
        migrate()
        logger.info("Data layer schema migration v4 applied")
    except Exception as e:
        logger.warning(f"Data layer migration v4 failed: {e}")

    # Startup: preload calendar cache
    try:
        from tzdata_pkg.maintenance.metadata.calendar_cache import CalendarCache
        cache = CalendarCache.get_instance()
        cache.preload(years=[2025, 2026, 2027])
        logger.info("CalendarCache preloaded on startup")
    except Exception as e:
        logger.warning(f"CalendarCache preload failed: {e}")
    yield


app = FastAPI(
    title="tz-data API",
    description="统一市场数据管理平台 — 中国期货/期权市场数据采集、存储、查询与分析。"
                "提供 REST API（`/docs` 查看交互式文档）和 Python SDK（`tzdata_pkg.query`）。",
    version="0.7.0",
    lifespan=lifespan,
)

# Mount docs directory for online documentation browsing
docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "docs")
if os.path.isdir(docs_dir):
    app.mount("/docs-api", StaticFiles(directory=docs_dir), name="docs")

app.include_router(market_router, prefix="/api/v1/market", tags=["market"])
app.include_router(positions_router, prefix="/api/v1/positions", tags=["positions"])
app.include_router(trading_router, prefix="/api/v1", tags=["trading"])
app.include_router(analysis_router, prefix="/api/v1", tags=["analysis"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(maintenance_router)  # maintenance_router already has prefix
app.include_router(data_layer_router, prefix="/api/v1")
