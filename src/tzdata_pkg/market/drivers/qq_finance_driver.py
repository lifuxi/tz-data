"""Tencent/QQ Finance HTTP polling driver for realtime market data (Phase 1)."""

from __future__ import annotations

import asyncio
import time
from typing import Callable

import structlog

from tzdata_pkg.market.drivers.base_driver import BaseMarketDriver

logger = structlog.get_logger("tzdata_market")


class QQFinanceDriver(BaseMarketDriver):
    """Tencent/QQ Finance driver — 1~3 second polling.

    Tencent finance API returns a compact text format with all fields
    separated by '~'. This is the fastest free source in Phase 1.
    """

    SOURCE_NAME = "qq_finance"

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
        logger.info("QQFinanceDriver connected")

    async def subscribe(self, symbols: list[str]) -> None:
        new_syms = set(symbols) - set(self._symbols)
        self._symbols.extend(new_syms)
        logger.info(f"QQFinanceDriver subscribed to {len(new_syms)} new symbols")
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
        logger.info("QQFinanceDriver disconnected")

    async def _poll_loop(self):
        """Poll Tencent API every 2-5 seconds."""
        interval = self._config.get("poll_interval", 3)
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
                logger.warning(f"QQFinanceDriver poll error: {e}")
            await asyncio.sleep(interval)

    async def _fetch_and_emit(self) -> None:
        """Fetch realtime quotes from Tencent Finance and emit via callback."""
        import httpx

        if not self._symbols:
            return

        # Tencent batch: q=f_shfeIF2506,f_cffexIM2506
        prefixed = [self._prefix_symbol(s) for s in self._symbols[:50]]
        sym_query = ",".join(prefixed)
        url = f"https://qt.gtimg.cn/q={sym_query}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    for line in resp.text.strip().split("\n"):
                        if "=" in line:
                            raw = self._parse_line(line)
                            if raw and self._callback:
                                self._callback(raw)
        except Exception as e:
            logger.warning(f"QQFinanceDriver fetch failed: {e}")

    def _prefix_symbol(self, symbol: str) -> str:
        """Add exchange prefix for Tencent API: f_cffexIF2506."""
        upper = symbol.upper()
        # Default to futures prefix, adjust per symbol pattern
        if any(ex in upper for ex in ("IF", "IC", "IM", "IH", "HO", "MO", "IO")):
            exchange = self._guess_exchange(upper)
            return f"f_{exchange.lower()}{upper}"
        return f"f_{upper}"

    def _guess_exchange(self, symbol: str) -> str:
        """Guess exchange from symbol code."""
        if any(prefix in symbol for prefix in ("IF", "IC", "IM", "IH", "MO", "IO")):
            return "CFFEX"
        if any(prefix in symbol for prefix in ("CU", "AL", "ZN", "NI", "PB", "SN", "AU", "AG")):
            return "SHFE"
        if any(prefix in symbol for prefix in ("RB", "HC", "I", "J", "JM", "V", "PP")):
            return "DCE"
        if any(prefix in symbol for prefix in ("MA", "TA", "SR", "CF", "FG", "SA")):
            return "CZCE"
        return "CFFEX"

    def _parse_line(self, line: str) -> dict | None:
        """Parse Tencent single-line response: v_...="name~price~..."."""
        if "~" not in line:
            return None
        content = line.split('="', 1)[-1].strip('"')
        parts = content.split("~")
        if len(parts) < 35:
            return None

        try:
            symbol_raw = parts[2] if len(parts) > 2 else ""
            return {
                "symbol": symbol_raw,
                "exchange": self._guess_exchange(symbol_raw),
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
