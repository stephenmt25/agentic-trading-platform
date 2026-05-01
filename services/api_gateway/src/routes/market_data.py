"""API routes for market data (OHLCV candles for charting)."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException

from ..deps import get_market_data_repo
from libs.storage.repositories.market_data_repo import MarketDataRepository

router = APIRouter()


@router.get("/candles/{symbol:path}")
async def get_candles(
    symbol: str,
    timeframe: str = Query(default="1h", regex="^(1m|5m|15m|1h)$"),
    limit: int = Query(default=500, ge=1, le=2000),
    start: Optional[int] = Query(default=None, description="Range start as epoch seconds"),
    end: Optional[int] = Query(default=None, description="Range end as epoch seconds"),
    repo: MarketDataRepository = Depends(get_market_data_repo),
):
    """Get OHLCV candlestick data for charting.

    Default mode (no start/end): returns the most recent `limit` candles.
    Range mode (both start and end provided): returns every candle in that
    inclusive window, ordered oldest first. Used by decision-context chart
    lookups.
    """
    symbol = symbol.rstrip("/")

    if start is not None and end is not None:
        if end <= start:
            raise HTTPException(status_code=400, detail="end must be greater than start")
        start_dt = datetime.fromtimestamp(start, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end, tz=timezone.utc)
        candles = await repo.get_candles_by_range(symbol, timeframe, start_dt, end_dt)
    elif start is not None or end is not None:
        raise HTTPException(status_code=400, detail="start and end must both be provided for range queries")
    else:
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
