"""Tushare HTTP polling driver for realtime market data (Phase 1)."""

from __future__ import annotations

import asyncio
import time
from typing import Callable

import structlog

from tzdata_pkg.market.drivers.base_driver import BaseMarketDriver

logger = structlog.get_logger("tzdata_market")


class TushareDriver(BaseMarketDriver):
    SOURCE_NAME = "tushare"

    def __init__(self):
        self._config: dict = {}
        self._symbols: list[str] = []
        self._callback: Callable[[dict], None] | None = None
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._error_count = 0
        self._connected = False
        self._last_poll_ms = 0
        self._latency_samples: list[float] = []

    async def connect(self, config: dict) -> None:
        self._config = config
        self._connected = True
        self._error_count = 0
        logger.info("TushareDriver connected", api_endpoint=config.get("api_url", "default"))

    async def subscribe(self, symbols: list[str]) -> None:
        new_syms = set(symbols) - set(self._symbols)
        self._symbols.extend(new_syms)
        logger.info(f"TushareDriver subscribed to {len(new_syms)} new symbols")
        if not self._running and self._symbols:
            self._running = True
            self._poll_task = asyncio.create_task(self._poll_loop())

    async def unsubscribe(self, symbols: list[str]) -> None:
        self._symbols = [s for s in self._symbols if s not in symbols]
        if not self._symbols and self._running:
            self._running = False
            if self._poll_task:
                self._poll_task.cancel()
                self._poll_task = None

    def on_data(self, callback: Callable[[dict], None]) -> None:
        self._callback = callback

    async def heartbeat(self) -> dict:
        avg_latency = (
            sum(self._latency_samples[-20:]) / len(self._latency_samples[-20:])
            if self._latency_samples
            else 0
        )
        return {
            "status": "connected" if self._connected else "disconnected",
            "latency_ms": round(avg_latency),
            "error_count": self._error_count,
            "symbols_count": len(self._symbols),
            "last_poll_ms": self._last_poll_ms,
        }

    async def disconnect(self) -> None:
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        self._connected = False
        logger.info("TushareDriver disconnected")

    async def _poll_loop(self):
        """Poll Tushare API at a fixed interval (60s for minute-level data)."""
        interval = self._config.get("poll_interval", 60)
        while self._running:
            try:
                start = time.monotonic()
                await self._fetch_and_emit()
                elapsed_ms = (time.monotonic() - start) * 1000
                self._latency_samples.append(elapsed_ms)
                self._error_count = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._error_count += 1
                logger.warning(f"TushareDriver poll error: {e}")
            await asyncio.sleep(interval)

    async def _fetch_and_emit(self) -> None:
        """Fetch real-time quotes from Tushare and emit via callback."""
        import httpx

        api_url = self._config.get("api_url", "https://api.tushare.pro")
        token = self._config.get("api_token", "")

        if not token or not self._symbols:
            return

        # Tushare batch quote for futures
        sym_list = ",".join(self._symbols[:50])  # batch limit
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    api_url,
                    json={
                        "api_name": "futur_min",
                        "token": token,
                        "params": {"ts_code": sym_list, "freq": "1min"},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0 and data.get("data"):
                        for row in data["data"]["items"]:
                            raw = self._normalize_row(row)
                            if raw and self._callback:
                                self._callback(raw)
        except httpx.TimeoutException:
            logger.warning("TushareDriver request timed out")
        except Exception as e:
            logger.warning(f"TushareDriver fetch failed: {e}")

    def _normalize_row(self, row: list) -> dict | None:
        """Normalize a Tushare response row into a raw market data dict."""
        if not row or len(row) < 8:
            return None
        return {
            "symbol": row[0] if len(row) > 0 else "",
            "exchange": row[1] if len(row) > 1 else "",
            "timestamp": int(row[2]) if len(row) > 2 else 0,
            "open": float(row[3]) if row[3] is not None else None,
            "high": float(row[4]) if row[4] is not None else None,
            "low": float(row[5]) if row[5] is not None else None,
            "close": float(row[6]) if row[6] is not None else None,
            "volume": int(row[7]) if row[7] is not None else 0,
            "data_source": self.SOURCE_NAME,
        }
