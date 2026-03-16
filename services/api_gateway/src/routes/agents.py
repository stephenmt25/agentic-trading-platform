"""API routes for ML agent status and risk monitoring (Phase 3)."""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel

from ..deps import get_redis, get_current_user, get_profile_repo
from libs.storage.repositories.profile_repo import ProfileRepository

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


@router.get("/status", response_model=List[AgentScore])
async def get_agent_status(redis=Depends(get_redis)):
    """Get current ML agent scores for all tracked symbols."""
    results = []

    for symbol in TRACKED_SYMBOLS:
        entry = AgentScore(symbol=symbol)

        # Use pipeline to batch Redis reads per symbol
        pipe = redis.pipeline()
        pipe.get(f"agent:ta_score:{symbol}")
        pipe.get(f"agent:sentiment:{symbol}")
        pipe.get(f"agent:regime_hmm:{symbol}")
        ta_raw, sent_raw, hmm_raw = await pipe.execute()

        if ta_raw:
            data = json.loads(ta_raw)
            entry.ta_score = data.get("score")

        if sent_raw:
            data = json.loads(sent_raw)
            entry.sentiment_score = data.get("score")
            entry.sentiment_confidence = data.get("confidence")
            entry.sentiment_source = data.get("source")

        if hmm_raw:
            data = json.loads(hmm_raw)
            entry.hmm_regime = data.get("regime")
            entry.hmm_state_index = data.get("state_index")

        results.append(entry)

    return results


@router.get("/risk/{profile_id}", response_model=RiskStatus)
async def get_risk_status(
    profile_id: str,
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    redis=Depends(get_redis),
):
    """Get current risk metrics for a profile owned by the current user."""
    profile = await profile_repo.get_profile_for_user(profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Pipeline all Redis reads for this profile
    pipe = redis.pipeline()
    pipe.get(f"pnl:daily:{profile_id}")
    pipe.get(f"risk:drawdown:{profile_id}")
    pipe.get(f"risk:allocation:{profile_id}")
    pnl_raw, dd_raw, alloc_raw = await pipe.execute()

    result = RiskStatus(profile_id=profile_id)
    if pnl_raw:
        data = json.loads(pnl_raw)
        result.daily_pnl_pct = data.get("total_pct", 0.0)
    if dd_raw:
        data = json.loads(dd_raw)
        result.drawdown_pct = data.get("drawdown_pct", 0.0)
    if alloc_raw:
        data = json.loads(alloc_raw)
        result.allocation_pct = data.get("allocation_pct", 0.0)

    return result


@router.get("/risk", response_model=List[RiskStatus])
async def get_all_risk_status(
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    redis=Depends(get_redis),
):
    """Get risk status for all profiles owned by the current user."""
    profiles = await profile_repo.get_all_profiles_for_user(user_id)
    results = []

    for p in profiles:
        pid = str(p.get("profile_id", ""))
        status = RiskStatus(profile_id=pid)

        pipe = redis.pipeline()
        pipe.get(f"pnl:daily:{pid}")
        pipe.get(f"risk:drawdown:{pid}")
        pipe.get(f"risk:allocation:{pid}")
        pnl_raw, dd_raw, alloc_raw = await pipe.execute()

        if pnl_raw:
            data = json.loads(pnl_raw)
            status.daily_pnl_pct = data.get("total_pct", 0.0)
        if dd_raw:
            data = json.loads(dd_raw)
            status.drawdown_pct = data.get("drawdown_pct", 0.0)
        if alloc_raw:
            data = json.loads(alloc_raw)
            status.allocation_pct = data.get("allocation_pct", 0.0)

        results.append(status)

    return results
