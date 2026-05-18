"""AKShare HTTP polling driver for realtime market data (Phase 1)."""

from __future__ import annotations

import asyncio
import time
from typing import Callable

import structlog

from tzdata_pkg.market.drivers.base_driver import BaseMarketDriver

logger = structlog.get_logger("tzdata_market")


class AKShareDriver(BaseMarketDriver):
    SOURCE_NAME = "akshare"

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
        logger.info("AKShareDriver connected")

    async def subscribe(self, symbols: list[str]) -> None:
        new_syms = set(symbols) - set(self._symbols)
        self._symbols.extend(new_syms)
        logger.info(f"AKShareDriver subscribed to {len(new_syms)} new symbols")
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
        logger.info("AKShareDriver disconnected")

    async def _poll_loop(self):
        """Poll AKShare at a fixed interval (30s for near-realtime)."""
        interval = self._config.get("poll_interval", 30)
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
                logger.warning(f"AKShareDriver poll error: {e}")
            await asyncio.sleep(interval)

    async def _fetch_and_emit(self) -> None:
        """Fetch realtime quotes from AKShare and emit via callback."""
        import httpx

        if not self._symbols:
            return

        # AKShare uses different endpoints per asset type
        # For futures: futures_zh_spot_sina is the common source
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                for symbol in self._symbols[:20]:  # limit batch size
                    raw = await self._fetch_symbol(client, symbol)
                    if raw and self._callback:
                        self._callback(raw)
        except Exception as e:
            logger.warning(f"AKShareDriver fetch failed: {e}")

    async def _fetch_symbol(self, client: httpx.AsyncClient, symbol: str) -> dict | None:
        """Fetch a single symbol from AKShare-compatible API."""
        # Using Tencent/QQ finance API as AKShare proxy (same underlying source)
        url = f"https://qt.gtimg.cn/q={symbol}"
        try:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.text.strip():
                return self._parse_qq_response(resp.text, symbol)
        except Exception as e:
            logger.warning(f"AKShareDriver fetch {symbol} failed: {e}")
        return None

    def _parse_qq_response(self, text: str, symbol: str) -> dict | None:
        """Parse Tencent/QQ format response."""
        if "~" not in text:
            return None
        parts = text.split("~")
        if len(parts) < 35:
            return None
        try:
            return {
                "symbol": symbol,
                "exchange": "",
                "timestamp": int(time.time() * 1000),
                "open": float(parts[5]) if parts[5] else None,
                "high": float(parts[33]) if parts[33] else None,
                "low": float(parts[34]) if parts[34] else None,
                "close": float(parts[3]) if parts[3] else None,
                "volume": int(parts[36]) if len(parts) > 36 and parts[36] else 0,
                "pre_close": float(parts[4]) if parts[4] else None,
                "data_source": self.SOURCE_NAME,
            }
        except (ValueError, IndexError):
            return None
