from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Awaitable, Optional, Tuple, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis

from libs.storage.repositories import PnlRepository
from libs.storage.repositories.closed_trade_repo import ClosedTradeRepository
from libs.storage.repositories.profile_repo import ProfileRepository

from ..deps import (
    get_closed_trade_repo,
    get_current_user,
    get_pnl_repo,
    get_profile_repo,
    get_redis,
)

router = APIRouter(tags=["pnl"])

_MICRO = Decimal("1000000")


async def _read_daily_loss(
    redis: Optional[Redis], profile_id: str
) -> Tuple[float, Optional[str]]:
    """Read the per-profile daily-loss counter written by services/pnl/src/closer.py.

    The key `pnl:daily:{profile_id}` is a Redis HASH with fields
    `date` (ISO date) and `total_pct_micro` (signed integer micro-fraction of
    profile equity since UTC midnight). The previous string-shaped read here
    raised WRONGTYPE for any profile that had ever closed a trade.
    Returns (daily_loss_pct, date) — defaults (0.0, None) when the hash is
    absent or unreadable.
    """
    if redis is None:
        return 0.0, None
    try:
        # redis-py shares command stubs between sync and async clients, so hget
        # is typed `Awaitable[str|None] | str|None`; on redis.asyncio it is
        # always awaitable. Cast to Awaitable[Any] (not str — values arrive as
        # bytes without decode_responses; the isinstance checks below narrow).
        raw_micro = await cast(
            Awaitable[Any],
            redis.hget(f"pnl:daily:{profile_id}", "total_pct_micro"),
        )
        raw_date = await cast(
            Awaitable[Any], redis.hget(f"pnl:daily:{profile_id}", "date")
        )
    except Exception:
        return 0.0, None
    if isinstance(raw_micro, (bytes, bytearray)):
        raw_micro = raw_micro.decode()
    if isinstance(raw_date, (bytes, bytearray)):
        raw_date = raw_date.decode()
    if raw_micro is None:
        return 0.0, raw_date
    try:
        pct = Decimal(raw_micro) / _MICRO
    except Exception:
        return 0.0, raw_date
    return float(pct), raw_date


def _snapshot_to_dict(row) -> Optional[dict]:
    """Convert a pnl_snapshots asyncpg Record (or None) into a JSON-friendly dict.
    Decimal -> float at the wire boundary; calculations stay on Decimal upstream."""
    if row is None:
        return None
    return {
        "gross_pnl": float(row["gross_pnl"]),
        "net_pnl_pre_tax": float(row["net_pnl_pre_tax"]),
        "net_pnl_post_tax": float(row["net_pnl_post_tax"]),
        "total_fees": float(row["total_fees"]),
        "estimated_tax": float(row["estimated_tax"]),
        "cost_basis": float(row["cost_basis"]),
        "pct_return": float(row["pct_return"]),
        "symbol": row["symbol"],
        "snapshot_at": (
            row["snapshot_at"].isoformat() if row.get("snapshot_at") else None
        ),
    }


@router.get("/summary")
async def get_pnl_summary(
    user_id: str = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    repo: PnlRepository = Depends(get_pnl_repo),
):
    """Aggregate P&L summary across the current user's profiles.

    Dollar P&L (`total_net_pnl`, per-profile `net_pnl`) is sourced from
    `pnl_snapshots`. The Redis hash `pnl:daily:{pid}` is a circuit-breaker
    counter — its `total_pct_micro` field is exposed as `daily_loss_pct`.
    """
    profiles = await profile_repo.get_active_profiles_for_user(user_id)
    total_net_pnl = Decimal("0")
    positions = []

    for p in profiles:
        pid = str(p.get("profile_id", ""))
        if not pid:
            continue
        latest = await repo.get_latest(pid)
        net_pnl = Decimal(str(latest["net_pnl_post_tax"])) if latest else Decimal("0")
        total_net_pnl += net_pnl

        daily_loss_pct, daily_date = await _read_daily_loss(redis, pid)
        snap = _snapshot_to_dict(latest)
        positions.append(
            {
                "profile_id": pid,
                "net_pnl": float(net_pnl),
                "snapshot": snap,
                "daily_loss_pct": daily_loss_pct,
                "daily_date": daily_date,
            }
        )

    return {
        "status": "active",
        "total_net_pnl": float(total_net_pnl),
        "positions": positions,
    }


@router.get("/history")
async def get_pnl_history(
    profile_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    repo: PnlRepository = Depends(get_pnl_repo),
):
    """Historical P&L snapshots for a profile owned by the current user."""
    profile = await profile_repo.get_profile_for_user(profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    start_dt = datetime.fromisoformat(start) if start else datetime.min
    end_dt = datetime.fromisoformat(end) if end else datetime.now(timezone.utc)
    snapshots = await repo.get_snapshots(profile_id, start_dt, end_dt)
    return [dict(s) for s in snapshots]


@router.get("/net-of-cost")
async def get_net_of_cost(
    window_hours: int = Query(default=168),
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    closed_trade_repo: ClosedTradeRepository = Depends(get_closed_trade_repo),
):
    """Per-strategy (profile) net-of-cost rollup over a rolling window (PR5).

    The honest number: realized net P&L with fee / slippage / funding
    attribution per profile, filtered to the current user's profiles.
    Row fields: profile_id, trade_count, win_count, loss_count, net_pnl,
    total_fees, total_slippage, total_funding, gross_pnl, avg_pnl_pct,
    win_rate, net_negative. Money fields are STRING-encoded Decimals
    (CLAUDE.md 2A — never IEEE floats on the wire); gross_pnl is derived
    server-side with Decimal as net_pnl + total_fees (slippage/funding are
    attribution overlays already embedded in realized_pnl per migration 024
    — never re-subtracted). The FE parses for display only.

    NB: this route must stay registered BEFORE the `/{profile_id}` catch-all.
    """
    # Clamp to a sane range (1h .. 90d) instead of rejecting — display read.
    window_hours = max(1, min(2160, window_hours))

    profiles = await profile_repo.get_all_profiles_for_user(user_id)
    owned = {str(p.get("profile_id", "")) for p in profiles}
    rows = await closed_trade_repo.net_of_cost_by_profile(window_hours=window_hours)

    # The repo converts NUMERIC(20,8) sums to float at its boundary
    # (closed_trade_repo.net_of_cost_by_profile — pre-existing, owned by
    # another lane); re-anchor to Decimal-as-string here so this route never
    # serializes IEEE floats. Residual debt (repo-side float()) is registry
    # material, not fixable from the gateway.
    def _money(v) -> Optional[str]:
        return None if v is None else str(Decimal(str(v)))

    out_rows = []
    for r in rows:
        if str(r.get("profile_id", "")) not in owned:
            continue
        net = None if r.get("net_pnl") is None else Decimal(str(r["net_pnl"]))
        fees = None if r.get("total_fees") is None else Decimal(str(r["total_fees"]))
        gross = net + fees if net is not None and fees is not None else net
        out_rows.append(
            {
                "profile_id": str(r.get("profile_id", "")),
                "trade_count": r.get("trade_count"),
                "win_count": r.get("win_count"),
                "loss_count": r.get("loss_count"),
                "net_pnl": None if net is None else str(net),
                "total_fees": None if fees is None else str(fees),
                "total_slippage": _money(r.get("total_slippage")),
                "total_funding": _money(r.get("total_funding")),
                "gross_pnl": None if gross is None else str(gross),
                "avg_pnl_pct": _money(r.get("avg_pnl_pct")),
                "win_rate": r.get("win_rate"),
                "net_negative": bool(r.get("net_negative", False)),
            }
        )
    return {"window_hours": window_hours, "rows": out_rows}


@router.get("/{profile_id}")
async def get_profile_pnl(
    profile_id: str,
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    redis: Redis = Depends(get_redis),
    repo: PnlRepository = Depends(get_pnl_repo),
):
    """Current P&L snapshot for a profile owned by the current user."""
    profile = await profile_repo.get_profile_for_user(profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    latest = await repo.get_latest(profile_id)
    daily_loss_pct, daily_date = await _read_daily_loss(redis, profile_id)
    return {
        "profile_id": profile_id,
        "snapshot": _snapshot_to_dict(latest),
        "daily_loss_pct": daily_loss_pct,
        "daily_date": daily_date,
    }
