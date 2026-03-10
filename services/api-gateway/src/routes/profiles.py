from fastapi import APIRouter, Depends, HTTPException
from typing import List
from ..deps import get_profile_repo, get_current_user
from libs.storage.repositories import ProfileRepository
from libs.core.models import TradingProfile, RiskLimits
from services.strategy.src.rule_validator import RuleValidator

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/")
async def get_profiles(repo: ProfileRepository = Depends(get_profile_repo)):
    return await repo.get_active_profiles()

@router.post("/")
async def create_profile(profile_data: dict, repo: ProfileRepository = Depends(get_profile_repo)):
    """Validates rules dynamically via Strategy validator before permitting persistence"""
    # Quick route validator check against Agent 1 library
    val = RuleValidator.validate(profile_data.get("rules_json", {}))
    if not val.is_valid:
        raise HTTPException(status_code=400, detail={"errors": val.errors})
        
    # In full app: construct and store TradingProfile 
    return {"status": "created", "id": "mock_id"}

@router.put("/{profile_id}")
async def update_profile(profile_id: str, profile_data: dict, repo: ProfileRepository = Depends(get_profile_repo)):
    val = RuleValidator.validate(profile_data.get("rules_json", {}))
    if not val.is_valid:
        raise HTTPException(status_code=400, detail={"errors": val.errors})
    # Soft update mapping
    return {"status": "updated"}

@router.delete("/{profile_id}")
async def disable_profile(profile_id: str, repo: ProfileRepository = Depends(get_profile_repo)):
    # Emit pause / soft delete explicitly marking is_active=False
    return {"status": "disabled"}
