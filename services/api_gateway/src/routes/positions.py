"""Positions API — open and recently-closed positions for the user-facing dashboard."""
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import (
    get_closed_trade_repo,
    get_current_user,
    get_position_repo,
    get_profile_repo,
    get_redis,
)
from libs.config import settings
from libs.core.enums import OrderSide, PositionStatus
from libs.core.models import Position
from libs.core.notional import profile_notional
from libs.storage.repositories.closed_trade_repo import ClosedTradeRepository
from libs.storage.repositories.position_repo import PositionRepository
from libs.storage.repositories.profile_repo import ProfileRepository
from libs.storage._redis_client import RedisClient

router = APIRouter(tags=["positions"])

_ZERO = Decimal("0")

# Mirrors services/pnl/src/main.py — kept in sync by hand. If the canonical map
# moves to libs/, swap to importing from there.
_TAKER_RATES = {
    "BINANCE": Decimal("0.001"),
    "COINBASE": Decimal("0.006"),
}
_DEFAULT_TAKER_RATE = Decimal("0.002")


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


def _to_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


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


def _parse_risk_limits(raw) -> dict:
    """trading_profiles.risk_limits is a JSONB column. asyncpg may hand it back
    as a dict (already parsed) or a JSON string depending on the driver path."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _enrich_with_profile_context(rows: list[dict], profiles: dict[str, dict]) -> list[dict]:
    """Add notional, allocation %, mark price, and SL/TP price levels to each row.

    Math:
      notional        = entry_price * quantity
      allocation_used = notional / profile_notional        (fraction, e.g. 0.42 = 42%)
      mark_price      = entry_price ± gross_pnl / quantity (sign by side)
      stop_loss_price = entry_price * (1 ∓ stop_loss_pct)  (long subtracts, short adds)
      take_profit_px  = entry_price * (1 ± take_profit_pct)
      distance_to_sl  = (mark - sl_price) / mark           (signed; negative means past the level)
    """
    for r in rows:
        entry = _to_decimal(r.get("entry_price"))
        qty = _to_decimal(r.get("quantity"))
        side = r.get("side")
        is_long = side == "BUY"

        notional = entry * qty if entry is not None and qty is not None else None
        if notional is not None:
            r["notional"] = str(notional)

        profile = profiles.get(str(r.get("profile_id")))
        if profile is not None:
            pnotional = profile_notional(profile)
            if notional is not None and pnotional > _ZERO:
                r["allocation_used_pct"] = float(notional / pnotional)
            r["profile_notional"] = str(pnotional)

            risk = _parse_risk_limits(profile.get("risk_limits"))
            sl_pct = _to_decimal(risk.get("stop_loss_pct"))
            tp_pct = _to_decimal(risk.get("take_profit_pct"))
            if entry is not None and sl_pct is not None and sl_pct > _ZERO:
                sl = entry * (Decimal("1") - sl_pct) if is_long else entry * (Decimal("1") + sl_pct)
                r["stop_loss_price"] = str(sl)
                r["stop_loss_pct"] = str(sl_pct)
            if entry is not None and tp_pct is not None and tp_pct > _ZERO:
                tp = entry * (Decimal("1") + tp_pct) if is_long else entry * (Decimal("1") - tp_pct)
                r["take_profit_price"] = str(tp)
                r["take_profit_pct"] = str(tp_pct)

        # Derive mark price from gross pnl when available
        gross = r.get("unrealized_gross_pnl")
        gross_dec = _to_decimal(gross)
        if entry is not None and qty is not None and qty > _ZERO and gross_dec is not None:
            delta = gross_dec / qty
            mark = entry + delta if is_long else entry - delta
            r["mark_price"] = str(mark)

    return rows


@router.get("/")
async def list_positions(
    status: str = Query(default="open", pattern="^(open|all)$"),
    profile_id: Optional[str] = Query(default=None),
    user_id: str = Depends(get_current_user),
    repo: PositionRepository = Depends(get_position_repo),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    redis: RedisClient = Depends(get_redis),
):
    """List positions, default to open. Optionally scoped to a profile.

    Response shape: position rows with entry_price, quantity, opened_at, status,
    plus unrealized_net_pnl / unrealized_gross_pnl / unrealized_pct_return for OPEN
    rows when a fresh snapshot exists in Redis, plus enriched fields:
    notional, profile_notional, allocation_used_pct, mark_price, stop_loss_price,
    stop_loss_pct, take_profit_price, take_profit_pct.
    """
    if status == "open":
        rows = await repo.get_open_positions(profile_id=profile_id)
    else:
        if profile_id:
            query = "SELECT * FROM positions WHERE profile_id = $1 ORDER BY opened_at DESC LIMIT 200"
            rows = await repo._fetch(query, profile_id)
        else:
            rows = await repo._fetch("SELECT * FROM positions ORDER BY opened_at DESC LIMIT 200")

    serialised = [_serialise(dict(r)) for r in rows]
    serialised = await _attach_unrealized_pnl(serialised, redis)

    # Batch profile lookups so allocation/SL/TP enrichment is one DB hit per profile
    profile_ids = {str(r["profile_id"]) for r in serialised if r.get("profile_id")}
    profiles: dict[str, dict] = {}
    for pid in profile_ids:
        try:
            p = await profile_repo.get_profile(pid)
        except Exception:
            p = None
        if p:
            profiles[pid] = p

    return _enrich_with_profile_context(serialised, profiles)


# ─────────────────────────────────────────────────────────────────────────────
# Manual close
# ─────────────────────────────────────────────────────────────────────────────

async def _latest_mark_price(
    redis: RedisClient, profile_id: str, position_id: str, entry_price: Decimal,
    quantity: Decimal, is_long: bool,
) -> tuple[Decimal, bool]:
    """Reconstruct the latest mark from the pnl service's Redis snapshot.

    Returns (mark_price, fresh) — fresh=True when a snapshot was found and
    decoded; False when we fell back to entry_price."""
    raw = await redis.get(f"pnl:{profile_id}:{position_id}:latest")
    if not raw:
        return entry_price, False
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return entry_price, False
    gross = _to_decimal(payload.get("gross_pnl"))
    if gross is None or quantity <= _ZERO:
        return entry_price, False
    delta = gross / quantity
    return (entry_price + delta) if is_long else (entry_price - delta), True


@router.post("/{position_id}/close")
async def close_position(
    position_id: str,
    user_id: str = Depends(get_current_user),
    repo: PositionRepository = Depends(get_position_repo),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    closed_trade_repo: ClosedTradeRepository = Depends(get_closed_trade_repo),
    redis: RedisClient = Depends(get_redis),
):
    """Manually close an OPEN position at the latest mark price.

    Behaviour matches the existing exit_monitor close path: marks the
    position CLOSED in DB, computes final PnL, writes a closed_trades audit
    row tagged with `close_reason='manual'`, and updates agent EWMA weights.

    Caveat: this does NOT submit a closing order to the exchange — same
    limitation as stop_loss/take_profit/exit_monitor today. In paper/sim
    mode this is the correct behaviour; in live mode the real position on
    the exchange remains open and must be flattened separately. Tracked as
    pre-existing tech debt outside this endpoint's scope.
    """
    try:
        pid = UUID(position_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid position_id: '{position_id}' is not a UUID")

    row = await repo._fetchrow("SELECT * FROM positions WHERE position_id = $1", pid)
    if not row:
        raise HTTPException(status_code=404, detail=f"No position with id {pid} in DB")
    row = dict(row)

    if str(row.get("status", "")).upper() != PositionStatus.OPEN.value:
        raise HTTPException(status_code=409, detail=f"Position {pid} is not open (status={row.get('status')})")

    # Ownership check
    profile = await profile_repo.get_profile_for_user(str(row["profile_id"]), user_id)
    if not profile:
        raise HTTPException(status_code=403, detail="Position does not belong to this user")

    # Build a Position model for PositionCloser
    side = OrderSide.BUY if str(row["side"]).upper() == "BUY" else OrderSide.SELL
    is_long = side == OrderSide.BUY
    entry_price = Decimal(str(row["entry_price"]))
    quantity = Decimal(str(row["quantity"]))
    entry_fee = Decimal(str(row.get("entry_fee") or "0"))

    pos = Position(
        position_id=row["position_id"],
        profile_id=row["profile_id"],
        symbol=row["symbol"],
        side=side,
        entry_price=entry_price,
        quantity=quantity,
        entry_fee=entry_fee,
        opened_at=row["opened_at"],
        status=PositionStatus.OPEN,
        order_id=row.get("order_id"),
        decision_event_id=row.get("decision_event_id"),
    )

    mark_price, fresh = await _latest_mark_price(
        redis, str(row["profile_id"]), str(row["position_id"]),
        entry_price, quantity, is_long,
    )

    # Taker rate by exchange. Profile.exchange_key_ref is "BINANCE:user:1" etc.
    exchange_name = "BINANCE"
    ref = profile.get("exchange_key_ref") if profile else None
    if isinstance(ref, str) and ":" in ref:
        exchange_name = ref.split(":", 1)[0].upper()
    taker_rate = _TAKER_RATES.get(exchange_name, _DEFAULT_TAKER_RATE)

    # Import here to avoid module-load coupling between api_gateway and pnl
    # service code paths during cold start.
    from services.pnl.src.closer import PositionCloser

    closer = PositionCloser(
        position_repo=repo,
        redis_client=redis,
        closed_trade_repo=closed_trade_repo,
        profile_repo=profile_repo,
    )

    try:
        snapshot = await closer.close(pos, mark_price, taker_rate, close_reason="manual")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Close failed: {e}") from e

    return {
        "status": "closed",
        "position_id": str(pid),
        "symbol": row["symbol"],
        "side": side.value,
        "entry_price": str(entry_price),
        "exit_price": str(mark_price),
        "mark_price_was_fresh": fresh,
        "quantity": str(quantity),
        "gross_pnl": str(snapshot.gross_pnl),
        "net_pnl_pre_tax": str(snapshot.net_pre_tax),
        "pct_return": float(snapshot.pct_return),
        "closed_at": datetime.utcnow().isoformat(),
        "trading_mode": "PAPER" if settings.PAPER_TRADING_MODE else (
            "TESTNET" if (settings.BINANCE_TESTNET or settings.COINBASE_SANDBOX) else "LIVE"
        ),
    }
