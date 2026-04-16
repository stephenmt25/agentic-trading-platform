"""API routes for agent performance evaluation and score history."""
import json
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query

from ..deps import get_redis, get_agent_score_repo, get_decision_repo
from libs.storage.repositories.agent_score_repo import AgentScoreRepository
from libs.storage.repositories.decision_repo import DecisionRepository

router = APIRouter()


@router.get("/scores/{symbol:path}")
async def get_score_history(
    symbol: str,
    agents: Optional[str] = Query(default=None, description="Comma-separated agent names: ta,sentiment,debate,regime_hmm"),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(default=500, ge=1, le=5000),
    repo: AgentScoreRepository = Depends(get_agent_score_repo),
):
    """Get historical agent scores for charting overlays.

    Returns continuous score history (every scoring cycle, not just decision-time).
    """
    if agents:
        agent_list = [a.strip() for a in agents.split(",")]
        results = []
        per_agent_limit = limit // len(agent_list) if agent_list else limit
        for agent in agent_list:
            scores = await repo.get_scores(
                symbol=symbol,
                agent_name=agent,
                start=start,
                end=end,
                limit=per_agent_limit,
            )
            results.extend(scores)
        # Sort by recorded_at for interleaved display
        results.sort(key=lambda x: x["recorded_at"])
        return results
    else:
        return await repo.get_scores(
            symbol=symbol,
            start=start,
            end=end,
            limit=limit,
        )


@router.get("/weights/{symbol:path}")
async def get_agent_weights(
    symbol: str,
    redis=Depends(get_redis),
):
    """Get current agent weights and EWMA tracker state.

    Returns dynamic weights from the Analyst agent and per-agent accuracy tracking.
    """
    pipe = redis.pipeline()
    pipe.hgetall(f"agent:weights:{symbol}")
    pipe.hgetall(f"agent:tracker:{symbol}:ta")
    pipe.hgetall(f"agent:tracker:{symbol}:sentiment")
    pipe.hgetall(f"agent:tracker:{symbol}:debate")
    weights_raw, ta_tracker, sent_tracker, debate_tracker = await pipe.execute()

    weights = {}
    if weights_raw:
        weights = {k: float(v) for k, v in weights_raw.items()}

    def _parse_tracker(raw: dict) -> dict:
        if not raw:
            return {"ewma": None, "samples": 0, "last_updated": None}
        return {
            "ewma": float(raw.get("ewma", 0)),
            "samples": int(raw.get("samples", 0)),
            "last_updated": raw.get("last_updated"),
        }

    return {
        "weights": weights,
        "trackers": {
            "ta": _parse_tracker(ta_tracker),
            "sentiment": _parse_tracker(sent_tracker),
            "debate": _parse_tracker(debate_tracker),
        },
    }


@router.get("/attribution/{symbol:path}")
async def get_trade_attribution(
    symbol: str,
    limit: int = Query(default=50, ge=1, le=500),
    repo: DecisionRepository = Depends(get_decision_repo),
):
    """Get per-trade agent attribution data.

    Shows which agents contributed positively/negatively to each decision.
    Reads from the trade_decisions table (agents JSONB column).
    """
    decisions = await repo.get_decisions(
        symbol=symbol,
        outcome="APPROVED",
        limit=limit,
    )
    results = []
    for d in decisions:
        agents_data = d.get("agents")
        if agents_data and isinstance(agents_data, str):
            agents_data = json.loads(agents_data)
        results.append({
            "event_id": str(d.get("event_id", "")),
            "symbol": d.get("symbol"),
            "outcome": d.get("outcome"),
            "input_price": float(d["input_price"]) if d.get("input_price") else None,
            "agents": agents_data,
            "created_at": d["created_at"].isoformat() if d.get("created_at") else None,
        })
    return results
