from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List
from ..deps import get_profile_repo, get_current_user
from libs.core.schemas import ProfileCreate, ProfileUpdate, ProfileToggle, ProfileResponse
from libs.storage.repositories.profile_repo import ProfileRepository

router = APIRouter(tags=["profiles"])


@router.get("/", response_model=List[ProfileResponse])
async def get_profiles(
    user_id: str = Depends(get_current_user),
    repo: ProfileRepository = Depends(get_profile_repo),
):
    """Return all trading profiles for the current user."""
    profiles = await repo.get_all_profiles_for_user(user_id)
    results = []
    for p in profiles:
        raw_rules = p.get("strategy_rules", {})
        if isinstance(raw_rules, str):
            import json as _json
            try:
                raw_rules = _json.loads(raw_rules)
            except (ValueError, TypeError):
                raw_rules = {}
        results.append(ProfileResponse(
            profile_id=str(p.get("profile_id", "")),
            name=p.get("name", ""),
            is_active=p.get("is_active", False),
            rules_json=raw_rules,
            allocation_pct=Decimal(str(p.get("allocation_pct", 0))),
            created_at=str(p.get("created_at", "")),
            deleted_at=str(p.get("deleted_at", "")) if p.get("deleted_at") else None,
        ))
    return results


@router.post("/", status_code=201)
async def create_profile(
    profile_data: ProfileCreate,
    user_id: str = Depends(get_current_user),
    repo: ProfileRepository = Depends(get_profile_repo),
):
    """Create a new trading profile with strategy rules."""
    try:
        created = await repo.create_profile(
            user_id=user_id,
            name=profile_data.name,
            strategy_rules=profile_data.rules_json,
            risk_limits=profile_data.risk_limits,
            allocation_pct=profile_data.allocation_pct,
        )
        return {"status": "created", "id": str(created.get("profile_id", "")), "profile": created}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create profile")


@router.put("/{profile_id}")
async def update_profile(
    profile_id: UUID,
    profile_data: ProfileUpdate,
    user_id: str = Depends(get_current_user),
    repo: ProfileRepository = Depends(get_profile_repo),
):
    """Update strategy rules for an existing profile (owned by current user)."""
    updated = await repo.update_profile(str(profile_id), user_id, profile_data.rules_json, profile_data.is_active)
    if not updated:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"status": "updated", "profile": updated}


@router.patch("/{profile_id}/toggle")
async def toggle_profile(
    profile_id: UUID,
    body: ProfileToggle,
    user_id: str = Depends(get_current_user),
    repo: ProfileRepository = Depends(get_profile_repo),
):
    """Toggle a profile's active state (owned by current user)."""
    result = await repo.toggle_active(str(profile_id), user_id, body.is_active)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"status": "toggled", "is_active": body.is_active}


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: UUID,
    user_id: str = Depends(get_current_user),
    repo: ProfileRepository = Depends(get_profile_repo),
):
    """Soft-delete a profile (owned by current user)."""
    result = await repo.soft_delete(str(profile_id), user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"status": "deleted", "deleted_at": str(result.get("deleted_at", ""))}
