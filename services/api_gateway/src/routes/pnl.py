from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from datetime import datetime, timezone
from ..deps import get_pnl_repo, get_redis, get_current_user, get_profile_repo
from libs.storage.repositories import PnlRepository
from libs.storage.repositories.profile_repo import ProfileRepository
from libs.storage._redis_client import RedisClient
import json

router = APIRouter(prefix="/pnl", tags=["pnl"])


@router.get("/summary")
async def get_pnl_summary(
    user_id: str = Depends(get_current_user),
    redis: RedisClient = Depends(get_redis),
    profile_repo: ProfileRepository = Depends(get_profile_repo),
):
    """Aggregate P&L summary across the current user's profiles."""
    profiles = await profile_repo.get_active_profiles_for_user(user_id)
    total_net_pnl = 0.0
    positions = []

    for p in profiles:
        pid = str(p.get("profile_id", ""))
        raw = await redis.get(f"pnl:daily:{pid}")
        if raw:
            data = json.loads(raw)
            total_net_pnl += data.get("net_pnl", 0.0)
            positions.append({"profile_id": pid, **data})

    return {"status": "active", "total_net_pnl": total_net_pnl, "positions": positions}


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
):
    """Current P&L snapshot for a profile owned by the current user."""
    profile = await profile_repo.get_profile_for_user(profile_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    raw = await redis.get(f"pnl:daily:{profile_id}")
    snapshot = json.loads(raw) if raw else {}
    return {"profile_id": profile_id, "snapshot": snapshot}
