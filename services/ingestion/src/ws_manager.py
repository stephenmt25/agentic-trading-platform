import asyncio
from typing import Any, Callable, Coroutine, Dict, List, Optional

from libs.core.models import NormalisedCandle, NormalisedTick
from libs.exchange import ExchangeAdapter
from libs.exchange._base import NormalisedOrderBook, NormalisedTrade


class WebSocketManager:
    def __init__(self, adapters: List[ExchangeAdapter], symbols: List[str]):
        self.adapters = adapters
        self.symbols = symbols
        self.retry_count: Dict[str, int] = {adapter.name: 0 for adapter in adapters}
        self._tasks: List[asyncio.Task] = []
        self._tick_cb: Callable[[NormalisedTick], Coroutine[Any, Any, None]] = None
        self._candle_cb: Callable[[NormalisedCandle], Coroutine[Any, Any, None]] = None
        self._orderbook_cb: Optional[Callable[[NormalisedOrderBook], Coroutine[Any, Any, None]]] = None
        self._trade_cb: Optional[Callable[[NormalisedTrade], Coroutine[Any, Any, None]]] = None

    async def start(
        self,
        tick_callback: Callable[[NormalisedTick], Coroutine[Any, Any, None]],
        candle_callback: Callable[[NormalisedCandle], Coroutine[Any, Any, None]] = None,
        orderbook_callback: Optional[Callable[[NormalisedOrderBook], Coroutine[Any, Any, None]]] = None,
        trade_callback: Optional[Callable[[NormalisedTrade], Coroutine[Any, Any, None]]] = None,
    ):
        """Start one concurrent task per adapter per stream.

        Streams (live pricing, candles, orderbook, trades) run independently;
        a failure in one does not affect the others. Optional callbacks are
        no-ops when omitted, so adapters that don't implement orderbook or
        trades simply don't spawn those tasks (the base class raises
        NotImplementedError, which we catch and log per stream).
        """
        self._tick_cb = tick_callback
        self._candle_cb = candle_callback
        self._orderbook_cb = orderbook_callback
        self._trade_cb = trade_callback
        for adapter in self.adapters:
            self._tasks.append(asyncio.create_task(self._run_ticks(adapter)))
            if candle_callback is not None:
                self._tasks.append(asyncio.create_task(self._run_candles(adapter)))
            if orderbook_callback is not None:
                self._tasks.append(asyncio.create_task(self._run_orderbook(adapter)))
            if trade_callback is not None:
                self._tasks.append(asyncio.create_task(self._run_trades(adapter)))

    async def _run_ticks(self, adapter: ExchangeAdapter):
        while True:
            try:
                await adapter.connect_websocket(self.symbols, self._tick_cb)
                break
            except Exception:
                if not await self._should_retry(adapter, stream="ticks"):
                    break

    async def _run_candles(self, adapter: ExchangeAdapter):
        while True:
            try:
                await adapter.stream_candles(self.symbols, self._candle_cb)
                break
            except Exception:
                if not await self._should_retry(adapter, stream="candles"):
                    break

    async def _run_orderbook(self, adapter: ExchangeAdapter):
        while True:
            try:
                await adapter.stream_orderbook(self.symbols, self._orderbook_cb)
                break
            except NotImplementedError:
                # Adapter doesn't expose depth — skip silently rather than retry.
                return
            except Exception:
                if not await self._should_retry(adapter, stream="orderbook"):
                    break

    async def _run_trades(self, adapter: ExchangeAdapter):
        while True:
            try:
                await adapter.stream_trades(self.symbols, self._trade_cb)
                break
            except NotImplementedError:
                return
            except Exception:
                if not await self._should_retry(adapter, stream="trades"):
                    break

    async def _should_retry(self, adapter: ExchangeAdapter, stream: str) -> bool:
        self.retry_count[adapter.name] += 1
        if self.retry_count[adapter.name] > 10:
            print(f"[{adapter.name}/{stream}] Max retries exceeded (10). SYSTEM_ALERT")
            return False
        await asyncio.sleep(min(2 ** self.retry_count[adapter.name], 30))
        return True

    def is_healthy(self) -> bool:
        return all(adapter.is_connected for adapter in self.adapters)

    def is_partially_healthy(self) -> bool:
        return any(adapter.is_connected for adapter in self.adapters)

    async def stop(self):
        for adapter in self.adapters:
            await adapter.close()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
