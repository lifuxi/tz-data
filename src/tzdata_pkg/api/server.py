"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

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
    description="Unified market data management for Chinese futures/options",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(market_router, prefix="/api/v1/market", tags=["market"])
app.include_router(positions_router, prefix="/api/v1/positions", tags=["positions"])
app.include_router(trading_router, prefix="/api/v1", tags=["trading"])
app.include_router(analysis_router, prefix="/api/v1", tags=["analysis"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(maintenance_router)  # maintenance_router already has prefix
app.include_router(data_layer_router, prefix="/api/v1")
