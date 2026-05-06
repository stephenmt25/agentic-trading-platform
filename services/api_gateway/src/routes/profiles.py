import json as _json
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List
from ..deps import get_profile_repo, get_current_user
from libs.core.schemas import (
    ProfileCreate,
    ProfileUpdate,
    ProfileToggle,
    ProfileResponse,
    strategy_rules_to_canonical,
    strategy_rules_from_canonical,
)
from libs.storage.repositories.profile_repo import ProfileRepository

router = APIRouter(tags=["profiles"])


@router.get("/", response_model=List[ProfileResponse])
async def get_profiles(
    user_id: str = Depends(get_current_user),
    repo: ProfileRepository = Depends(get_profile_repo),
):
    """Return all trading profiles for the current user (rules in user-facing shape)."""
    profiles = await repo.get_all_profiles_for_user(user_id)
    results = []
    for p in profiles:
        raw_rules = p.get("strategy_rules", {})
        if isinstance(raw_rules, str):
            try:
                raw_rules = _json.loads(raw_rules)
            except (ValueError, TypeError):
                raw_rules = {}
        # Stored shape is canonical; transform back to user-facing for the response.
        try:
            user_rules = strategy_rules_from_canonical(raw_rules)
        except (KeyError, ValueError, TypeError):
            # Defensive: skip rows whose stored rules can't round-trip. Migration 017
            # is the long-term cleanup; this guard keeps GET safe in the meantime.
            continue
        # Clean up the user-facing payload: drop null fields, then drop the
        # legacy `signals: []` when the both-legs shape is in use. Otherwise
        # the editor shows phantom nulls/empties that have no meaning for the
        # active rule shape and confuse round-trip edits.
        rules_dict = user_rules.model_dump(exclude_none=True, mode="json")
        if "entry_long" in rules_dict or "entry_short" in rules_dict:
            rules_dict.pop("signals", None)
        raw_risk = p.get("risk_limits") or {}
        if isinstance(raw_risk, str):
            try:
                raw_risk = _json.loads(raw_risk)
            except (ValueError, TypeError):
                raw_risk = {}
        if not isinstance(raw_risk, dict):
            raw_risk = {}
        results.append(ProfileResponse(
            profile_id=str(p.get("profile_id", "")),
            name=p.get("name", ""),
            is_active=p.get("is_active", False),
            rules_json=rules_dict,
            rules_json_canonical=raw_rules,
            allocation_pct=Decimal(str(p.get("allocation_pct", 0))),
            risk_limits=raw_risk,
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
    """Create a new trading profile. Validates user-facing input, stores canonical."""
    canonical_rules = strategy_rules_to_canonical(profile_data.rules_json)
    try:
        created = await repo.create_profile(
            user_id=user_id,
            name=profile_data.name,
            strategy_rules=canonical_rules,
            risk_limits=profile_data.risk_limits,
            allocation_pct=profile_data.allocation_pct,
        )
        return {"status": "created", "id": str(created.get("profile_id", "")), "profile": created}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create profile")


@router.put("/{profile_id}")
async def update_profile(
    profile_id: UUID,
    profile_data: ProfileUpdate,
    user_id: str = Depends(get_current_user),
    repo: ProfileRepository = Depends(get_profile_repo),
):
    """Update strategy rules, optionally risk_limits and allocation_pct.

    risk_limits is JSONB-merged so callers can update a single key (e.g. just
    max_allocation_pct) without overwriting the rest. allocation_pct is a
    scalar update — None = leave unchanged.
    """
    canonical_rules = strategy_rules_to_canonical(profile_data.rules_json)
    updated = await repo.update_profile(
        str(profile_id),
        user_id,
        canonical_rules,
        profile_data.is_active,
        risk_limits=profile_data.risk_limits,
        allocation_pct=profile_data.allocation_pct,
    )
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
