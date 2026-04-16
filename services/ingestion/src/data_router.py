import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from libs.core.models import NormalisedTick
from libs.storage.repositories import MarketDataRepository
from libs.observability import get_logger

logger = get_logger("ingestion.router")

TIMEFRAMES = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


def _bucket_for_timeframe(ts_sec: float, interval_sec: int) -> datetime:
    """Floor the timestamp to the nearest timeframe boundary."""
    epoch_sec = int(ts_sec)
    floored = epoch_sec - (epoch_sec % interval_sec)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


class DataRouter:
    def __init__(self, repo: MarketDataRepository):
        self._repo = repo
        # Structure: {symbol: {timeframe: candle_dict}}
        self._current_candles: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def aggregate_tick(self, tick: NormalisedTick):
        ts_sec = tick.timestamp / 1000000.0
        sym = tick.symbol

        if sym not in self._current_candles:
            self._current_candles[sym] = {}

        for tf_label, tf_seconds in TIMEFRAMES.items():
            bucket_dt = _bucket_for_timeframe(ts_sec, tf_seconds)
            tf_candles = self._current_candles[sym]

            if tf_label not in tf_candles or tf_candles[tf_label]['bucket'] != bucket_dt:
                # New bucket started for this timeframe
                new_candle = {
                    'open': tick.price,
                    'high': tick.price,
                    'low': tick.price,
                    'close': tick.price,
                    'volume': tick.volume,
                    'bucket': bucket_dt,
                }
                # Flush the previous candle if one exists
                if tf_label in tf_candles:
                    asyncio.create_task(
                        self._flush_candle(sym, tf_label, tf_candles[tf_label])
                    )

                tf_candles[tf_label] = new_candle
            else:
                c = tf_candles[tf_label]
                c['high'] = max(c['high'], tick.price)
                c['low'] = min(c['low'], tick.price)
                c['close'] = tick.price
                c['volume'] += tick.volume

    async def _flush_candle(self, symbol: str, timeframe: str, candle: Dict[str, Any]):
        try:
            await self._repo.write_candle(symbol, timeframe, candle, candle['bucket'])
        except Exception as e:
            logger.error(
                "Failed to flush candle to timescale",
                error=str(e),
                symbol=symbol,
                timeframe=timeframe,
            )

    async def force_flush(self):
        tasks = []
        for symbol, tf_map in self._current_candles.items():
            for tf_label, candle in tf_map.items():
                tasks.append(self._flush_candle(symbol, tf_label, candle))
        if tasks:
            await asyncio.gather(*tasks)
