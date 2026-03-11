from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List
from ..deps import get_profile_repo, get_current_user
from libs.storage.repositories.profile_repo import ProfileRepository

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/")
async def get_profiles(repo: ProfileRepository = Depends(get_profile_repo)):
    """Return all trading profiles (active and inactive)."""
    profiles = await repo.get_all_profiles()
    # Normalize keys for frontend consumption
    result = []
    for p in profiles:
        result.append({
            "profile_id": str(p.get("profile_id", "")),
            "name": p.get("name", ""),
            "is_active": p.get("is_active", False),
            "rules_json": p.get("strategy_rules", {}),
            "allocation_pct": float(p.get("allocation_pct", 0)),
            "created_at": str(p.get("created_at", "")),
            "deleted_at": str(p.get("deleted_at", "")) if p.get("deleted_at") else None,
        })
    return result

@router.post("/")
async def create_profile(
    profile_data: dict,
    request: Request,
    repo: ProfileRepository = Depends(get_profile_repo),
):
    """Create a new trading profile with strategy rules."""
    rules = profile_data.get("rules_json", {})
    name = profile_data.get("name", "Untitled Profile")
    
    # Get the real user_id from the JWT (set by verify_jwt middleware)
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User identity not available")
    
    try:
        created = await repo.create_profile(
            user_id=user_id,
            name=name,
            strategy_rules=rules,
            risk_limits=profile_data.get("risk_limits", {}),
            allocation_pct=profile_data.get("allocation_pct", 1.0),
        )
        return {"status": "created", "id": str(created.get("profile_id", "")), "profile": created}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{profile_id}")
async def update_profile(profile_id: str, profile_data: dict, repo: ProfileRepository = Depends(get_profile_repo)):
    """Update strategy rules for an existing profile."""
    rules = profile_data.get("rules_json", {})
    is_active = profile_data.get("is_active", True)
    
    try:
        updated = await repo.update_profile(profile_id, rules, is_active)
        if not updated:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"status": "updated", "profile": updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{profile_id}/toggle")
async def toggle_profile(profile_id: str, body: dict, repo: ProfileRepository = Depends(get_profile_repo)):
    """Toggle a profile's active state."""
    is_active = body.get("is_active", False)
    result = await repo.toggle_active(profile_id, is_active)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"status": "toggled", "is_active": is_active}

@router.delete("/{profile_id}")
async def delete_profile(profile_id: str, repo: ProfileRepository = Depends(get_profile_repo)):
    """Soft-delete a profile by setting deleted_at timestamp."""
    result = await repo.soft_delete(profile_id)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"status": "deleted", "deleted_at": str(result.get("deleted_at", ""))}
