import json
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from libs.config import settings
from libs.storage import RedisClient
from ..deps import get_redis, get_current_user

router = APIRouter()


class BacktestRequest(BaseModel):
    symbol: str = Field(..., example="BTC/USDT")
    strategy_rules: dict = Field(..., example={
        "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
        "logic": "AND",
        "direction": "BUY",
        "base_confidence": 0.85,
    })
    start_date: str = Field(..., example="2025-01-01T00:00:00")
    end_date: str = Field(..., example="2025-06-01T00:00:00")
    slippage_pct: float = Field(default=0.001, ge=0.0, le=0.05)


class BacktestResponse(BaseModel):
    job_id: str
    status: str


@router.post("", response_model=BacktestResponse)
async def create_backtest(
    req: BacktestRequest,
    user_id: str = Depends(get_current_user),
    redis=Depends(get_redis),
):
    """Submit a backtest job (authenticated, with queue depth limit)."""
    # Validate dates
    try:
        datetime.fromisoformat(req.start_date)
        datetime.fromisoformat(req.end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO 8601.")

    # Backpressure: check queue depth before accepting
    queue_len = await redis.xlen("auto_backtest_queue")
    if queue_len >= settings.BACKTEST_MAX_QUEUE_DEPTH:
        raise HTTPException(
            status_code=429,
            detail="Backtest queue is full. Please try again later."
        )

    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "user_id": user_id,
        "symbol": req.symbol,
        "strategy_rules": req.strategy_rules,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "slippage_pct": req.slippage_pct,
    }

    await redis.xadd("auto_backtest_queue", {"data": json.dumps(payload)})

    await redis.set(
        f"backtest:status:{job_id}",
        json.dumps({"status": "queued", "job_id": job_id, "user_id": user_id}),
        ex=3600,
    )

    return BacktestResponse(job_id=job_id, status="queued")


@router.get("/{job_id}")
async def get_backtest_result(
    job_id: str,
    user_id: str = Depends(get_current_user),
    redis=Depends(get_redis),
):
    """Get backtest result (only if the job belongs to the current user)."""
    cached = await redis.get(f"backtest:status:{job_id}")
    if not cached:
        raise HTTPException(status_code=404, detail="Backtest job not found")

    data = json.loads(cached)
    if data.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Backtest job not found")

    return data
