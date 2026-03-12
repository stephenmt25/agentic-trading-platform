"""API routes for ML agent status and risk monitoring (Phase 3)."""
import json
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import get_redis

router = APIRouter()


class AgentScore(BaseModel):
    symbol: str
    ta_score: Optional[float] = None
    sentiment_score: Optional[float] = None
    sentiment_confidence: Optional[float] = None
    sentiment_source: Optional[str] = None
    hmm_regime: Optional[str] = None
    hmm_state_index: Optional[int] = None


class RiskStatus(BaseModel):
    profile_id: str
    daily_pnl_pct: float = 0.0
    drawdown_pct: float = 0.0
    allocation_pct: float = 0.0
    circuit_breaker_threshold: Optional[float] = None


TRACKED_SYMBOLS = ["BTC/USDT", "ETH/USDT"]


@router.get("/status")
async def get_agent_status(redis=Depends(get_redis)):
    """Get current ML agent scores for all tracked symbols."""
    results = []

    for symbol in TRACKED_SYMBOLS:
        entry = AgentScore(symbol=symbol)

        # TA score
        raw = await redis.get(f"agent:ta_score:{symbol}")
        if raw:
            data = json.loads(raw)
            entry.ta_score = data.get("score")

        # Sentiment
        raw = await redis.get(f"agent:sentiment:{symbol}")
        if raw:
            data = json.loads(raw)
            entry.sentiment_score = data.get("score")
            entry.sentiment_confidence = data.get("confidence")
            entry.sentiment_source = data.get("source")

        # HMM regime
        raw = await redis.get(f"agent:regime_hmm:{symbol}")
        if raw:
            data = json.loads(raw)
            entry.hmm_regime = data.get("regime")
            entry.hmm_state_index = data.get("state_index")

        results.append(entry)

    return results


@router.get("/risk/{profile_id}")
async def get_risk_status(profile_id: str, redis=Depends(get_redis)):
    """Get current risk metrics for a profile."""
    result = RiskStatus(profile_id=profile_id)

    raw = await redis.get(f"pnl:daily:{profile_id}")
    if raw:
        data = json.loads(raw)
        result.daily_pnl_pct = data.get("total_pct", 0.0)

    raw = await redis.get(f"risk:drawdown:{profile_id}")
    if raw:
        data = json.loads(raw)
        result.drawdown_pct = data.get("drawdown_pct", 0.0)

    raw = await redis.get(f"risk:allocation:{profile_id}")
    if raw:
        data = json.loads(raw)
        result.allocation_pct = data.get("allocation_pct", 0.0)

    return result


@router.get("/risk")
async def get_all_risk_status(redis=Depends(get_redis)):
    """Get risk status for all known profiles by scanning Redis keys."""
    results = []

    # Scan for pnl:daily:* keys to discover active profiles
    cursor = 0
    profile_ids = set()
    while True:
        cursor, keys = await redis.scan(cursor, match="pnl:daily:*", count=100)
        for key in keys:
            key_str = key.decode() if isinstance(key, bytes) else key
            pid = key_str.replace("pnl:daily:", "")
            profile_ids.add(pid)
        if cursor == 0:
            break

    for pid in profile_ids:
        status = RiskStatus(profile_id=pid)

        raw = await redis.get(f"pnl:daily:{pid}")
        if raw:
            data = json.loads(raw)
            status.daily_pnl_pct = data.get("total_pct", 0.0)

        raw = await redis.get(f"risk:drawdown:{pid}")
        if raw:
            data = json.loads(raw)
            status.drawdown_pct = data.get("drawdown_pct", 0.0)

        raw = await redis.get(f"risk:allocation:{pid}")
        if raw:
            data = json.loads(raw)
            status.allocation_pct = data.get("allocation_pct", 0.0)

        results.append(status)

    return results
