"""API routes for pipeline configuration and agent tuning."""
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_redis, get_current_user, get_profile_repo
from libs.storage.repositories.profile_repo import ProfileRepository
from libs.core.agent_registry import AGENT_DEFAULTS

router = APIRouter()

# Default linear pipeline — the 9-gate sequence from processor.py
DEFAULT_PIPELINE = {
    "nodes": [
        {"id": "market_tick", "type": "input", "label": "Market Tick", "position": {"x": 0, "y": 200}},
        {"id": "strategy_eval", "type": "gate", "label": "Strategy Eval", "config": {}, "position": {"x": 200, "y": 200}},
        {"id": "abstention", "type": "gate", "label": "Abstention", "config": {"min_confidence": 0.2}, "position": {"x": 400, "y": 200}},
        {"id": "regime_dampener", "type": "gate", "label": "Regime Dampener", "config": {}, "position": {"x": 600, "y": 200}},
        {"id": "ta_agent", "type": "agent_input", "label": "TA Agent", "config": {"timeframe_weights": [0.1, 0.2, 0.3, 0.4], "candle_limit": 150, "score_ttl_s": 120}, "position": {"x": 600, "y": 0}},
        {"id": "sentiment_agent", "type": "agent_input", "label": "Sentiment", "config": {"score_interval_s": 300, "llm_backend": "cloud", "score_ttl_s": 900}, "position": {"x": 800, "y": 0}},
        {"id": "debate_agent", "type": "agent_input", "label": "Debate", "config": {"num_rounds": 2, "debate_interval_s": 300}, "position": {"x": 1000, "y": 0}},
        {"id": "regime_hmm", "type": "agent_input", "label": "Regime HMM", "config": {"confidence_threshold": 0.70, "classify_interval_s": 300}, "position": {"x": 400, "y": 0}},
        {"id": "agent_modifier", "type": "gate", "label": "Agent Modifier", "config": {}, "position": {"x": 800, "y": 200}},
        {"id": "circuit_breaker", "type": "gate", "label": "Circuit Breaker", "config": {}, "position": {"x": 1000, "y": 200}},
        {"id": "blacklist", "type": "gate", "label": "Blacklist", "config": {}, "position": {"x": 1200, "y": 200}},
        {"id": "risk_gate", "type": "gate", "label": "Risk Gate", "config": {}, "position": {"x": 1400, "y": 200}},
        {"id": "hitl_gate", "type": "gate", "label": "HITL Gate", "config": {}, "position": {"x": 1600, "y": 200}},
        {"id": "validation", "type": "gate", "label": "Validation", "config": {}, "position": {"x": 1800, "y": 200}},
        {"id": "exit_monitor", "type": "gate", "label": "Exit Monitor", "config": {"stop_loss_pct": 0.05, "take_profit_pct": 0.015, "max_holding_hours": 48}, "position": {"x": 1800, "y": 400}},
        {"id": "order_output", "type": "output", "label": "Order Approved", "position": {"x": 2000, "y": 200}},
    ],
    "edges": [
        {"id": "e-tick-strat", "source": "market_tick", "target": "strategy_eval"},
        {"id": "e-strat-abs", "source": "strategy_eval", "target": "abstention"},
        {"id": "e-abs-regime", "source": "abstention", "target": "regime_dampener"},
        {"id": "e-regime-agent", "source": "regime_dampener", "target": "agent_modifier"},
        {"id": "e-ta-agent", "source": "ta_agent", "target": "agent_modifier"},
        {"id": "e-sent-agent", "source": "sentiment_agent", "target": "agent_modifier"},
        {"id": "e-debate-agent", "source": "debate_agent", "target": "agent_modifier"},
        {"id": "e-hmm-regime", "source": "regime_hmm", "target": "regime_dampener"},
        {"id": "e-agent-cb", "source": "agent_modifier", "target": "circuit_breaker"},
        {"id": "e-cb-bl", "source": "circuit_breaker", "target": "blacklist"},
        {"id": "e-bl-risk", "source": "blacklist", "target": "risk_gate"},
        {"id": "e-risk-hitl", "source": "risk_gate", "target": "hitl_gate"},
        {"id": "e-hitl-val", "source": "hitl_gate", "target": "validation"},
        {"id": "e-val-order", "source": "validation", "target": "order_output"},
        {"id": "e-risk-exit", "source": "risk_gate", "target": "exit_monitor"},
    ],
}

# Agent tunable parameters catalog
AGENT_CATALOG = {
    "ta_agent": {
        "label": "TA Agent",
        "type": "agent_input",
        "params": {
            "timeframe_weights": {"type": "array", "default": [0.1, 0.2, 0.3, 0.4], "description": "Weights for [1m, 5m, 15m, 1h]"},
            "candle_limit": {"type": "integer", "default": 150, "min": 50, "max": 500, "description": "Warmup candle count"},
            "score_ttl_s": {"type": "integer", "default": 120, "min": 30, "max": 600, "description": "Score TTL in Redis (seconds)"},
        },
    },
    "sentiment_agent": {
        "label": "Sentiment Agent",
        "type": "agent_input",
        "params": {
            "score_interval_s": {"type": "integer", "default": 300, "min": 60, "max": 1800, "description": "Scoring interval (seconds)"},
            "llm_backend": {"type": "select", "default": "cloud", "options": ["cloud", "local", "auto"], "description": "LLM backend mode"},
            "score_ttl_s": {"type": "integer", "default": 900, "min": 60, "max": 3600, "description": "Score TTL in Redis (seconds)"},
        },
    },
    "debate_agent": {
        "label": "Debate Agent",
        "type": "agent_input",
        "params": {
            "num_rounds": {"type": "integer", "default": 2, "min": 1, "max": 5, "description": "Number of debate rounds"},
            "debate_interval_s": {"type": "integer", "default": 300, "min": 60, "max": 1800, "description": "Debate interval (seconds)"},
        },
    },
    "regime_hmm": {
        "label": "Regime HMM",
        "type": "agent_input",
        "params": {
            "confidence_threshold": {"type": "float", "default": 0.70, "min": 0.1, "max": 1.0, "step": 0.05, "description": "Min confidence to publish regime"},
            "classify_interval_s": {"type": "integer", "default": 300, "min": 60, "max": 1800, "description": "Classification interval (seconds)"},
        },
    },
    "analyst": {
        "label": "Analyst (Meta-Learning)",
        "type": "meta",
        "params": {
            "ewma_alpha": {"type": "float", "default": 0.1, "min": 0.01, "max": 0.5, "step": 0.01, "description": "EWMA learning rate"},
            "min_samples": {"type": "integer", "default": 10, "min": 1, "max": 100, "description": "Min samples before overriding defaults"},
            "min_weight": {"type": "float", "default": 0.05, "min": 0.0, "max": 0.5, "step": 0.01, "description": "Minimum agent weight"},
            "max_weight": {"type": "float", "default": 1.0, "min": 0.5, "max": 2.0, "step": 0.1, "description": "Maximum agent weight"},
        },
    },
    "exit_monitor": {
        "label": "Exit Monitor",
        "type": "gate",
        "params": {
            "stop_loss_pct": {"type": "float", "default": 0.05, "min": 0.01, "max": 0.20, "step": 0.005, "description": "Stop-loss threshold"},
            "take_profit_pct": {"type": "float", "default": 0.015, "min": 0.005, "max": 0.10, "step": 0.005, "description": "Take-profit threshold"},
            "max_holding_hours": {"type": "integer", "default": 48, "min": 1, "max": 168, "description": "Max position hold time (hours)"},
        },
    },
}


@router.get("/agents")
async def list_agent_catalog():
    """List all available agent types and their configurable parameters."""
    return AGENT_CATALOG


@router.get("/{profile_id}/pipeline")
async def get_pipeline_config(
    profile_id: str,
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
):
    """Get pipeline config for a profile. Returns default if none saved."""
    profile = await profile_repo.get_profile_for_user(profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    config = profile.get("pipeline_config")
    if config:
        if isinstance(config, str):
            config = json.loads(config)
        return config
    return DEFAULT_PIPELINE


@router.put("/{profile_id}/pipeline")
async def save_pipeline_config(
    profile_id: str,
    body: dict,
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
):
    """Save a custom pipeline DAG config for a profile."""
    profile = await profile_repo.get_profile_for_user(profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Validate basic structure
    if "nodes" not in body or "edges" not in body:
        raise HTTPException(status_code=422, detail="Pipeline config must have 'nodes' and 'edges'")

    await profile_repo.update_pipeline_config(profile_id, body)
    return {"status": "saved", "profile_id": profile_id}


@router.post("/{profile_id}/pipeline/reset")
async def reset_pipeline_config(
    profile_id: str,
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
):
    """Reset pipeline config to default."""
    profile = await profile_repo.get_profile_for_user(profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    await profile_repo.update_pipeline_config(profile_id, None)
    return {"status": "reset", "profile_id": profile_id}


@router.put("/{profile_id}/weights")
async def override_weights(
    profile_id: str,
    body: dict,
    user_id: str = Depends(get_current_user),
    redis=Depends(get_redis),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
):
    """Manually override agent weights (bypasses Analyst auto-computation)."""
    profile = await profile_repo.get_profile_for_user(profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Write weights to Redis for all tracked symbols
    from libs.config import settings
    for symbol in settings.TRADING_SYMBOLS:
        mapping = {k: str(v) for k, v in body.items() if k in AGENT_DEFAULTS}
        if mapping:
            await redis.hset(f"agent:weights:{symbol}", mapping=mapping)
            await redis.expire(f"agent:weights:{symbol}", 900)
            # Set override flag so Analyst skips recomputation
            await redis.set(f"agent:weights_override:{symbol}", "true", ex=900)

    return {"status": "weights_overridden", "weights": body}


@router.delete("/{profile_id}/weights")
async def clear_weight_override(
    profile_id: str,
    user_id: str = Depends(get_current_user),
    redis=Depends(get_redis),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
):
    """Clear manual weight override, return to Analyst auto-weights."""
    profile = await profile_repo.get_profile_for_user(profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    from libs.config import settings
    for symbol in settings.TRADING_SYMBOLS:
        await redis.delete(f"agent:weights_override:{symbol}")

    return {"status": "override_cleared"}
