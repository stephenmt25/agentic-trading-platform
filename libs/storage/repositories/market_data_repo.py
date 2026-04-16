from typing import List, Dict, Any
from datetime import datetime
from ._repository_base import BaseRepository

class MarketDataRepository(BaseRepository):
    async def get_candles(self, symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
        query = """
        SELECT bucket as "time", open, high, low, close, volume
        FROM market_data_ohlcv
        WHERE symbol = $1 AND timeframe = $2
        ORDER BY bucket DESC
        LIMIT $3
        """
        records = await self._fetch(query, symbol, timeframe, limit)
        return [dict(r) for r in reversed(records)]  # Return oldest to newest

    async def get_candles_by_range(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> List[Dict[str, Any]]:
        query = """
        SELECT bucket as "time", open, high, low, close, volume
        FROM market_data_ohlcv
        WHERE symbol = $1 AND timeframe = $2
          AND bucket BETWEEN $3 AND $4
        ORDER BY bucket ASC
        """
        records = await self._fetch(query, symbol, timeframe, start, end)
        return [dict(r) for r in records]

    async def write_candle(self, symbol: str, timeframe: str, ohlcv: Dict[str, Any], bucket: datetime):
        query = """
        INSERT INTO market_data_ohlcv (symbol, timeframe, open, high, low, close, volume, bucket)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (symbol, timeframe, bucket) DO UPDATE
        SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, 
            close = EXCLUDED.close, volume = EXCLUDED.volume
        """
        await self._execute(
            query,
            symbol,
            timeframe,
            ohlcv['open'],
            ohlcv['high'],
            ohlcv['low'],
            ohlcv['close'],
            ohlcv['volume'],
            bucket
        )
