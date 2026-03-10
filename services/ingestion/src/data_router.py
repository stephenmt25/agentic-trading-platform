import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from libs.core.models import NormalisedTick
from libs.storage.repositories import MarketDataRepository
from libs.observability import get_logger

logger = get_logger("ingestion.router")

class DataRouter:
    def __init__(self, repo: MarketDataRepository):
        self._repo = repo
        # Structure: {"SYMBOL": { 'open': x, 'high': x, 'low': x, 'close': x, 'volume': x, 'bucket': ts }}
        self._current_candles: Dict[str, Dict[str, Any]] = {}

    def aggregate_tick(self, tick: NormalisedTick):
        # Determine 1-min bucket (floor to nearest minute)
        ts_sec = tick.timestamp / 1000000.0
        bucket_dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc).replace(second=0, microsecond=0)
        
        sym = tick.symbol
        if sym not in self._current_candles or self._current_candles[sym]['bucket'] != bucket_dt:
            # New bucket started
            new_candle = {
                'open': tick.price,
                'high': tick.price,
                'low': tick.price,
                'close': tick.price,
                'volume': tick.volume,
                'bucket': bucket_dt
            }
            # Flush old candle asynchronously if exists
            if sym in self._current_candles:
                asyncio.create_task(self._flush_candle(sym, self._current_candles[sym]))
                
            self._current_candles[sym] = new_candle
        else:
            c = self._current_candles[sym]
            c['high'] = max(c['high'], tick.price)
            c['low'] = min(c['low'], tick.price)
            c['close'] = tick.price
            c['volume'] += tick.volume

    async def _flush_candle(self, symbol: str, candle: Dict[str, Any]):
        try:
            await self._repo.write_candle(symbol, "1m", candle, candle['bucket'].isoformat())
        except Exception as e:
            logger.error("Failed to flush candle to timescale", error=str(e), symbol=symbol)

    async def force_flush(self):
        tasks = []
        for symbol, c in self._current_candles.items():
            tasks.append(self._flush_candle(symbol, c))
        if tasks:
            await asyncio.gather(*tasks)
