from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
from ..deps import get_pnl_repo, get_redis, get_current_user, get_profile_repo
from libs.storage.repositories import PnlRepository
from libs.storage.repositories.profile_repo import ProfileRepository
from libs.storage._redis_client import RedisClient

router = APIRouter(tags=["pnl"])

_MICRO = Decimal("1000000")


async def _read_daily_loss(redis: RedisClient, profile_id: str) -> Tuple[float, Optional[str]]:
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
        raw_micro = await redis.hget(f"pnl:daily:{profile_id}", "total_pct_micro")
        raw_date = await redis.hget(f"pnl:daily:{profile_id}", "date")
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
        "snapshot_at": row["snapshot_at"].isoformat() if row.get("snapshot_at") else None,
    }


@router.get("/summary")
async def get_pnl_summary(
    user_id: str = Depends(get_current_user),
    redis: RedisClient = Depends(get_redis),
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
        positions.append({
            "profile_id": pid,
            "net_pnl": float(net_pnl),
            "snapshot": snap,
            "daily_loss_pct": daily_loss_pct,
            "daily_date": daily_date,
        })

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


@router.get("/{profile_id}")
async def get_profile_pnl(
    profile_id: str,
    user_id: str = Depends(get_current_user),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
    redis: RedisClient = Depends(get_redis),
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
