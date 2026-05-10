"""Audit API routes — read-only access to the PR1 ledger.

Surfaces:
  - GET /closed-trades                          → recent closed trades
  - GET /closed-trades/by-position/{pid}        → single closed trade by position
  - GET /closed-trades/by-decision/{eid}        → closed trade by decision event
  - GET /debate                                 → recent debate cycles
  - GET /debate/{cycle_id}                      → cycle + full transcript
  - GET /chain/{decision_event_id}              → full decision → close lineage
  - GET /user-events                            → user-action audit log (kill switch, etc.)

All endpoints are read-only and authenticated via the shared verify_token_dep.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from libs.storage.repositories.closed_trade_repo import ClosedTradeRepository
from libs.storage.repositories.debate_repo import DebateRepository
from libs.storage.repositories.decision_repo import DecisionRepository
from libs.storage.repositories.order_repo import OrderRepository
from libs.storage.repositories.position_repo import PositionRepository
from services.hot_path.src.kill_switch import KILL_SWITCH_LOG_KEY

from ..deps import (
    get_closed_trade_repo,
    get_debate_repo,
    get_decision_repo,
    get_order_repo,
    get_position_repo,
    get_redis,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _to_jsonable(value: Any) -> Any:
    """Convert DB values (Decimal, UUID, datetime) into JSON-safe primitives."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, str):
        # JSONB columns may already be parsed by asyncpg; if they arrive as
        # strings, parse so the response stays structured.
        return value
    return value


def _serialize_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, str) and k in ("indicators", "strategy", "regime", "agents",
                                        "gates", "profile_rules", "entry_agent_scores",
                                        "market_context"):
            try:
                out[k] = json.loads(v)
                continue
            except (ValueError, TypeError):
                pass
        out[k] = _to_jsonable(v)
    return out


def _parse_uuid(value: str, name: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid {name} (expected UUID)")


# ---------------------------------------------------------------------------
# Closed trades
# ---------------------------------------------------------------------------

@router.get("/closed-trades")
async def list_closed_trades(
    symbol: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    repo: ClosedTradeRepository = Depends(get_closed_trade_repo),
):
    """Return recent closed trades, optionally filtered by symbol."""
    rows = await repo.get_recent(symbol=symbol, limit=limit)
    return [_serialize_row(r) for r in rows]


@router.get("/close-reasons")
async def aggregate_close_reasons(
    profile_id: Optional[str] = Query(default=None),
    symbol: Optional[str] = Query(default=None),
    regime: Optional[str] = Query(default=None),
    window_hours: int = Query(default=168, ge=1, le=8760),
    group_by_regime: bool = Query(default=False),
    repo: ClosedTradeRepository = Depends(get_closed_trade_repo),
):
    """Per-close_reason aggregates over the closed_trades ledger.

    Implements PR2 §close-reason taxonomy from SECOND-BRAIN-PRS-REMAINING.md.
    Read-only; pure aggregation; one row per close_reason (× regime when
    ``group_by_regime`` is set). ``win_rate`` is null when the bucket is
    empty — rare but possible at narrow window/profile combos.
    """
    pid = _parse_uuid(profile_id, "profile_id") if profile_id else None
    rows = await repo.aggregate_close_reasons(
        profile_id=pid,
        symbol=symbol,
        regime=regime,
        window_hours=window_hours,
        group_by_regime=group_by_regime,
    )
    return [_serialize_row(r) for r in rows]


@router.get("/closed-trades/by-position/{position_id}")
async def get_closed_trade_by_position(
    position_id: str,
    repo: ClosedTradeRepository = Depends(get_closed_trade_repo),
):
    pid = _parse_uuid(position_id, "position_id")
    row = await repo.get_by_position(pid)
    if not row:
        raise HTTPException(status_code=404, detail="Closed trade not found for this position")
    return _serialize_row(row)


@router.get("/closed-trades/by-decision/{decision_event_id}")
async def get_closed_trade_by_decision(
    decision_event_id: str,
    repo: ClosedTradeRepository = Depends(get_closed_trade_repo),
):
    eid = _parse_uuid(decision_event_id, "decision_event_id")
    row = await repo.get_by_decision_event(eid)
    if not row:
        raise HTTPException(status_code=404, detail="No closed trade for this decision")
    return _serialize_row(row)


# ---------------------------------------------------------------------------
# Debate transcripts
# ---------------------------------------------------------------------------

@router.get("/debate")
async def list_debate_cycles(
    symbol: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=200),
    repo: DebateRepository = Depends(get_debate_repo),
):
    """Return recent debate cycle summaries (no per-round detail)."""
    rows = await repo.get_recent_cycles(symbol=symbol, limit=limit)
    return [_serialize_row(r) for r in rows]


@router.get("/debate/{cycle_id}")
async def get_debate_cycle(
    cycle_id: str,
    repo: DebateRepository = Depends(get_debate_repo),
):
    """Return a single debate cycle with all bull/bear rounds."""
    cid = _parse_uuid(cycle_id, "cycle_id")
    payload = await repo.get_cycle_with_rounds(cid)
    if payload is None:
        raise HTTPException(status_code=404, detail="Debate cycle not found")
    return {
        "cycle": _serialize_row(payload["cycle"]),
        "rounds": [_serialize_row(r) for r in payload["rounds"]],
    }


# ---------------------------------------------------------------------------
# Full chain
# ---------------------------------------------------------------------------

@router.get("/chain/{decision_event_id}")
async def get_decision_chain(
    decision_event_id: str,
    decision_repo: DecisionRepository = Depends(get_decision_repo),
    order_repo: OrderRepository = Depends(get_order_repo),
    position_repo: PositionRepository = Depends(get_position_repo),
    closed_trade_repo: ClosedTradeRepository = Depends(get_closed_trade_repo),
):
    """Return the full lineage for a single decision: trade_decision → order → position → closed_trade.

    Stages downstream of the decision will be `null` if they haven't happened
    yet (e.g. position still open, or order rejected).
    """
    eid = _parse_uuid(decision_event_id, "decision_event_id")

    decision = await decision_repo.get_decision(str(eid))
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    order = await order_repo.get_by_decision_event_id(eid)
    position = await position_repo.get_by_decision_event_id(eid)
    closed_trade = await closed_trade_repo.get_by_decision_event(eid)

    return {
        "decision": _serialize_row(decision),
        "order": _serialize_row(order),
        "position": _serialize_row(position),
        "closed_trade": _serialize_row(closed_trade),
    }


# ---------------------------------------------------------------------------
# User-action audit log (Settings → Audit log surface)
# ---------------------------------------------------------------------------

# Event-type tags surfaced by the audit log UI. Source spec:
# docs/design/05-surface-specs/06-profiles-settings.md §10.
USER_EVENT_TYPES = ("kill_switch", "profile", "api_key", "override", "auth_fail")


def _kill_switch_log_to_events(raw_entries: List[Any]) -> List[Dict[str, Any]]:
    """Convert Redis kill-switch log entries to the unified audit shape.

    Each Redis entry is a JSON object with action / reason / timestamp +
    actor field (activated_by or deactivated_by). We project to a flat
    {id, type, description, actor, timestamp_ms} record.
    """
    events: List[Dict[str, Any]] = []
    for i, entry in enumerate(raw_entries or []):
        try:
            data = json.loads(entry) if isinstance(entry, (bytes, str)) else entry
            if not isinstance(data, dict):
                continue
            action = data.get("action", "UNKNOWN")
            reason = data.get("reason") or "manual"
            actor = data.get("activated_by") or data.get("deactivated_by") or "system"
            ts = data.get("timestamp")
            timestamp_ms = int(float(ts) * 1000) if ts else 0
            descr = (
                f"Kill switch {action.lower()} — {reason}"
                if action != "UNKNOWN"
                else reason
            )
            events.append(
                {
                    "id": f"ks-{timestamp_ms}-{i}",
                    "type": "kill_switch",
                    "description": descr,
                    "actor": actor,
                    "timestamp_ms": timestamp_ms,
                }
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
    return events


@router.get("/user-events")
async def list_user_audit_events(
    event_type: Optional[str] = Query(default=None, description="Filter by type tag"),
    from_ts: Optional[int] = Query(default=None, alias="from", description="ms epoch lower bound (inclusive)"),
    to_ts: Optional[int] = Query(default=None, alias="to", description="ms epoch upper bound (inclusive)"),
    limit: int = Query(default=200, ge=1, le=1000),
    redis=Depends(get_redis),
):
    """Read-only feed of significant user actions for the Settings → Audit
    log surface.

    Aggregates from the sources that emit user-action events today:
      - kill_switch: praxis:kill_switch:log Redis list (last 100 entries).

    Profile changes, API key rotations, agent overrides, and failed
    sign-ins are documented event types in the surface spec but their
    sources don't emit yet — when they land, they'll be added here and
    the response shape stays the same.
    """
    if event_type and event_type != "all" and event_type not in USER_EVENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown event_type. Valid: {', '.join(USER_EVENT_TYPES)}",
        )

    events: List[Dict[str, Any]] = []

    # --- kill_switch ---
    if event_type in (None, "all", "kill_switch"):
        try:
            raw = await redis.lrange(KILL_SWITCH_LOG_KEY, 0, 99)
        except Exception:
            raw = []
        events.extend(_kill_switch_log_to_events(raw))

    # Future sources land here with the same shape:
    #   if event_type in (None, "all", "profile"): events.extend(...)
    #   if event_type in (None, "all", "api_key"): events.extend(...)
    #   if event_type in (None, "all", "override"): events.extend(...)
    #   if event_type in (None, "all", "auth_fail"): events.extend(...)

    if from_ts is not None:
        events = [e for e in events if e["timestamp_ms"] >= from_ts]
    if to_ts is not None:
        events = [e for e in events if e["timestamp_ms"] <= to_ts]

    events.sort(key=lambda e: e["timestamp_ms"], reverse=True)
    events = events[:limit]

    # Track which event types are currently emitted vs. defined-but-empty
    # so the UI can correctly tag which Pending notes still apply.
    return {
        "events": events,
        "available_types": ["kill_switch"],
        "pending_types": ["profile", "api_key", "override", "auth_fail"],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
