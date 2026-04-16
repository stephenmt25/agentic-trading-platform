"""API routes for agent performance evaluation, score history, and gate analytics."""
import json
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query

from ..deps import get_redis, get_agent_score_repo, get_decision_repo, get_weight_history_repo
from libs.storage.repositories.agent_score_repo import AgentScoreRepository
from libs.storage.repositories.decision_repo import DecisionRepository
from libs.storage.repositories.weight_history_repo import WeightHistoryRepository

router = APIRouter()


def _clean_symbol(symbol: str) -> str:
    """Strip trailing slashes from path-captured symbol params."""
    return symbol.rstrip("/")


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
    symbol = _clean_symbol(symbol)
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
    symbol = _clean_symbol(symbol)
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
        # Decode bytes keys/values from Redis pipeline
        decoded = {}
        for k, v in raw.items():
            dk = k.decode() if isinstance(k, bytes) else k
            dv = v.decode() if isinstance(v, bytes) else v
            decoded[dk] = dv
        ewma_val = decoded.get("ewma_accuracy") or decoded.get("ewma")
        samples_val = decoded.get("sample_count") or decoded.get("samples")
        return {
            "ewma": float(ewma_val) if ewma_val else None,
            "samples": int(float(samples_val)) if samples_val else 0,
            "last_updated": decoded.get("last_updated"),
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
    symbol = _clean_symbol(symbol)
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


@router.get("/weight-history/{symbol:path}")
async def get_weight_history(
    symbol: str,
    agents: Optional[str] = Query(default=None),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(default=500, ge=1, le=5000),
    repo: WeightHistoryRepository = Depends(get_weight_history_repo),
):
    """Get historical agent weight evolution data for charts."""
    symbol = _clean_symbol(symbol)
    if agents:
        agent_list = [a.strip() for a in agents.split(",")]
        results = []
        per_agent_limit = limit // len(agent_list) if agent_list else limit
        for agent in agent_list:
            history = await repo.get_history(
                symbol=symbol,
                agent_name=agent,
                start=start,
                end=end,
                limit=per_agent_limit,
            )
            results.extend(history)
        results.sort(key=lambda x: x["recorded_at"])
        return results
    else:
        return await repo.get_history(symbol=symbol, start=start, end=end, limit=limit)


@router.get("/gate-analytics/{symbol:path}")
async def get_gate_analytics(
    symbol: str,
    limit: int = Query(default=500, ge=1, le=5000),
    repo: DecisionRepository = Depends(get_decision_repo),
):
    """Aggregate gate block analytics from trade_decisions table.

    Returns per-outcome counts and per-gate block reasons.
    """
    symbol = _clean_symbol(symbol)
    decisions = await repo.get_decisions(symbol=symbol, limit=limit)

    outcome_counts: dict = {}
    gate_details: dict = {}
    total = len(decisions)

    for d in decisions:
        outcome = d.get("outcome", "UNKNOWN")
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

        gates = d.get("gates")
        if gates and isinstance(gates, str):
            gates = json.loads(gates)
        if gates and isinstance(gates, dict):
            for gate_name, gate_data in gates.items():
                if gate_name not in gate_details:
                    gate_details[gate_name] = {"passed": 0, "blocked": 0, "reasons": {}}
                if isinstance(gate_data, dict):
                    if gate_data.get("passed"):
                        gate_details[gate_name]["passed"] += 1
                    else:
                        gate_details[gate_name]["blocked"] += 1
                        reason = gate_data.get("reason", "unknown")
                        if reason:
                            gate_details[gate_name]["reasons"][reason] = (
                                gate_details[gate_name]["reasons"].get(reason, 0) + 1
                            )

    return {
        "total_decisions": total,
        "outcome_counts": outcome_counts,
        "gate_details": gate_details,
    }
