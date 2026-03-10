import asyncio
from typing import List, Callable, Coroutine, Dict, Any
from libs.exchange import ExchangeAdapter
from libs.core.models import NormalisedTick

class WebSocketManager:
    def __init__(self, adapters: List[ExchangeAdapter], symbols: List[str]):
        self.adapters = adapters
        self.symbols = symbols
        self.retry_count: Dict[str, int] = {adapter.name: 0 for adapter in adapters}
        self._tasks: List[asyncio.Task] = []
        self._callback: Callable[[NormalisedTick], Coroutine[Any, Any, None]] = None

    async def start(self, callback: Callable[[NormalisedTick], Coroutine[Any, Any, None]]):
        self._callback = callback
        for adapter in self.adapters:
            # Create isolated tasks to avoid one exchange crashing the other
            t = asyncio.create_task(self._run_adapter(adapter))
            self._tasks.append(t)

    async def _run_adapter(self, adapter: ExchangeAdapter):
        while True:
            try:
                await adapter.connect_websocket(self.symbols, self._callback)
                # If cleanly exits (which usually implies shutdown or close)
                break
            except Exception as e:
                # CCXT internal exceptions already handled inside adapter, this is last resort
                self.retry_count[adapter.name] += 1
                if self.retry_count[adapter.name] > 10:
                    # Emitting SYSTEM_ALERT
                    print(f"[{adapter.name}] Max retries exceeded (10). SYSTEM_ALERT")
                    break
                await asyncio.sleep(min(2 ** self.retry_count[adapter.name], 30))

    def is_healthy(self) -> bool:
        return all(adapter.is_connected for adapter in self.adapters)

    def is_partially_healthy(self) -> bool:
        return any(adapter.is_connected for adapter in self.adapters)

    async def stop(self):
        for adapter in self.adapters:
            await adapter.close()
        # Cancel tasks
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
