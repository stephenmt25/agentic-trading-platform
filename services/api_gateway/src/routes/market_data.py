"""API routes for market data (OHLCV candles for charting)."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from ..deps import get_market_data_repo
from libs.storage.repositories.market_data_repo import MarketDataRepository

router = APIRouter()


@router.get("/candles/{symbol:path}")
async def get_candles(
    symbol: str,
    timeframe: str = Query(default="1h", regex="^(1m|5m|15m|1h|4h|1d)$"),
    limit: int = Query(default=500, ge=1, le=2000),
    repo: MarketDataRepository = Depends(get_market_data_repo),
):
    """Get OHLCV candlestick data for charting.

    Returns candles in ascending time order (oldest first).
    """
    candles = await repo.get_candles(symbol, timeframe, limit)
    # Convert Decimal fields to float for JSON serialization
    result = []
    for c in candles:
        result.append({
            "time": int(c["time"].timestamp()) if hasattr(c["time"], "timestamp") else c["time"],
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
            "volume": float(c["volume"]) if c.get("volume") else 0,
        })
    return result
