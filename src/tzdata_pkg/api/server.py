"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from tzdata_pkg.api.routes.market import router as market_router
from tzdata_pkg.api.routes.positions import router as positions_router
from tzdata_pkg.api.routes.trading import router as trading_router
from tzdata_pkg.api.routes.analysis import router as analysis_router
from tzdata_pkg.api.routes.admin import router as admin_router
from tzdata_pkg.api.routes.maintenance import router as maintenance_router


@asynccontextmanager
async def lifespan(app: FastAPI):
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
