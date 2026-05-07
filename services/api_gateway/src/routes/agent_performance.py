"""API routes for agent performance evaluation, score history, and gate analytics."""
import json
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query

from ..deps import (
    get_redis,
    get_agent_score_repo,
    get_closed_trade_repo,
    get_decision_repo,
    get_weight_history_repo,
    get_gate_efficacy_repo,
)
from libs.core.agent_registry import AGENT_DEFAULTS
from libs.storage.repositories.agent_score_repo import AgentScoreRepository
from libs.storage.repositories.closed_trade_repo import ClosedTradeRepository
from libs.storage.repositories.decision_repo import DecisionRepository
from libs.storage.repositories.gate_efficacy_repo import GateEfficacyRepository
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

    # The shared RedisClient does not set decode_responses=True, so hgetall
    # returns {bytes: bytes}. Decode here so the JSON response carries str
    # keys — otherwise the frontend's weights[agent] lookup misses every
    # time. Same root cause as acb25ae (analyst tracker) — fixed there but
    # the duplicate read path here was missed.
    weights: dict = {}
    if weights_raw:
        for k, v in weights_raw.items():
            dk = k.decode() if isinstance(k, bytes) else k
            dv = v.decode() if isinstance(v, bytes) else v
            try:
                weights[dk] = float(dv)
            except (TypeError, ValueError):
                continue

    # Fall back to AGENT_DEFAULTS for any agent the analyst hasn't recomputed
    # yet. After a clean-baseline reset (or first boot) the Redis hash is
    # empty until 10+ closed trades have been observed; without this, the
    # dashboard panel shows "—" for hours despite the system using the
    # defaults internally.
    for agent, default in AGENT_DEFAULTS.items():
        weights.setdefault(agent, default)

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
    profile_id: Optional[str] = Query(default=None),
    repo: DecisionRepository = Depends(get_decision_repo),
):
    """Aggregate gate block analytics from trade_decisions table.

    Returns per-outcome counts and per-gate block reasons. Optionally filtered to
    a single profile via the profile_id query param.
    """
    symbol = _clean_symbol(symbol)
    decisions = await repo.get_decisions(symbol=symbol, profile_id=profile_id, limit=limit)

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


@router.get("/agent-attribution/{symbol:path}")
async def get_agent_attribution_summary(
    symbol: str,
    profile_id: Optional[str] = Query(default=None),
    window_hours: int = Query(default=168, ge=1, le=8760),
    threshold: float = Query(default=0.15, ge=0.0, le=1.0),
    limit: int = Query(default=25, ge=1, le=100),
    repo: ClosedTradeRepository = Depends(get_closed_trade_repo),
):
    """Agent agreement-pattern outcomes (Second Brain PR2 §agent attribution).

    Buckets each closed trade by the agreement pattern of its originating
    decision (TA / sentiment / debate score → BULL / BEAR / NEUTRAL,
    threshold default ±0.15) and reports realized win rate + average PnL
    per bucket. Companion to ``/agent-performance/attribution`` — that one
    is per-trade; this one is the realized-outcome aggregate.
    """
    from uuid import UUID
    symbol = _clean_symbol(symbol)
    pid: Optional[UUID] = None
    if profile_id:
        try:
            pid = UUID(profile_id)
        except (ValueError, TypeError):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid profile_id (expected UUID)")
    return await repo.aggregate_agent_attribution(
        profile_id=pid,
        symbol=symbol,
        window_hours=window_hours,
        threshold=threshold,
        limit=limit,
    )


@router.get("/gate-efficacy/{symbol:path}")
async def get_gate_efficacy(
    symbol: str,
    profile_id: Optional[str] = Query(default=None),
    gate_name: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    repo: GateEfficacyRepository = Depends(get_gate_efficacy_repo),
):
    """Read the most recent gate efficacy reports for a symbol.

    Reports are produced every 6h by the analyst service's Insight Engine
    (services/analyst/src/insight_engine.py). NULL win-rate / PnL fields
    indicate sample size below MIN_SAMPLE_SIZE — the partner-facing UI
    should render these as "not enough data yet" rather than 0.
    """
    symbol = _clean_symbol(symbol)
    rows = await repo.get_recent(
        symbol=symbol,
        profile_id=profile_id,
        gate_name=gate_name,
        limit=limit,
    )

    def _normalise(row: dict) -> dict:
        out = dict(row)
        for key in (
            "blocked_would_be_win_rate",
            "blocked_would_be_pnl_pct",
            "passed_realized_win_rate",
            "passed_realized_pnl_pct",
            "confidence_band",
        ):
            v = out.get(key)
            out[key] = float(v) if v is not None else None
        for ts_key in ("window_start", "window_end", "created_at"):
            v = out.get(ts_key)
            if hasattr(v, "isoformat"):
                out[ts_key] = v.isoformat()
        return out

    return [_normalise(r) for r in rows]
