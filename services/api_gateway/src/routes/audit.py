"""Audit API routes — read-only access to the PR1 ledger.

Surfaces:
  - GET /closed-trades                          → recent closed trades
  - GET /closed-trades/by-position/{pid}        → single closed trade by position
  - GET /closed-trades/by-decision/{eid}        → closed trade by decision event
  - GET /debate                                 → recent debate cycles
  - GET /debate/{cycle_id}                      → cycle + full transcript
  - GET /chain/{decision_event_id}              → full decision → close lineage

All endpoints are read-only and authenticated via the shared verify_token_dep.
"""

import json
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from libs.storage.repositories.closed_trade_repo import ClosedTradeRepository
from libs.storage.repositories.debate_repo import DebateRepository
from libs.storage.repositories.decision_repo import DecisionRepository
from libs.storage.repositories.order_repo import OrderRepository
from libs.storage.repositories.position_repo import PositionRepository

from ..deps import (
    get_closed_trade_repo,
    get_debate_repo,
    get_decision_repo,
    get_order_repo,
    get_position_repo,
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
