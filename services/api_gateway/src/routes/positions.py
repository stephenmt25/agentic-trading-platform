"""Positions API — open and recently-closed positions for the user-facing dashboard."""
import json
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..deps import get_position_repo, get_current_user, get_redis
from libs.storage.repositories.position_repo import PositionRepository
from libs.storage._redis_client import RedisClient

router = APIRouter(tags=["positions"])


def _serialise(row: dict) -> dict:
    """Convert a position row into JSON-safe primitives."""
    out = dict(row)
    for k, v in list(out.items()):
        if isinstance(v, Decimal):
            out[k] = str(v)
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif hasattr(v, "hex") and not isinstance(v, (bytes, bytearray)):
            out[k] = str(v)
    return out


async def _attach_unrealized_pnl(rows: list[dict], redis: RedisClient) -> list[dict]:
    """Merge the latest unrealized PnL snapshot from Redis into each open position row.

    PnL service writes pnl:<profile>:<position>:latest on every tick. We MGET them all
    in one round-trip so this stays cheap as portfolio size grows."""
    open_rows = [r for r in rows if r.get("status") == "OPEN"]
    if not open_rows:
        return rows
    keys = [f"pnl:{r['profile_id']}:{r['position_id']}:latest" for r in open_rows]
    raw_values = await redis.mget(keys)
    for r, raw in zip(open_rows, raw_values):
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            continue
        r["unrealized_net_pnl"] = payload.get("net_pnl")
        r["unrealized_gross_pnl"] = payload.get("gross_pnl")
        r["unrealized_pct_return"] = payload.get("pct_return")
    return rows


@router.get("/")
async def list_positions(
    status: str = Query(default="open", pattern="^(open|all)$"),
    profile_id: Optional[str] = Query(default=None),
    user_id: str = Depends(get_current_user),
    repo: PositionRepository = Depends(get_position_repo),
    redis: RedisClient = Depends(get_redis),
):
    """List positions, default to open. Optionally scoped to a profile.

    Response shape: list of positions with entry_price, quantity, opened_at, status,
    plus unrealized_net_pnl / unrealized_gross_pnl / unrealized_pct_return for OPEN
    rows when a fresh snapshot exists in Redis."""
    if status == "open":
        rows = await repo.get_open_positions(profile_id=profile_id)
    else:
        # All positions, optionally filtered by profile_id
        if profile_id:
            query = "SELECT * FROM positions WHERE profile_id = $1 ORDER BY opened_at DESC LIMIT 200"
            rows = await repo._fetch(query, profile_id)
        else:
            rows = await repo._fetch("SELECT * FROM positions ORDER BY opened_at DESC LIMIT 200")

    serialised = [_serialise(dict(r)) for r in rows]
    return await _attach_unrealized_pnl(serialised, redis)
