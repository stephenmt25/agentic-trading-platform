from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from ..deps import get_current_user
from libs.core.schemas import CommandIntent, KillSwitchStatusResponse, KillSwitchToggleResponse
from libs.storage import RedisClient
from libs.config import settings
from services.hot_path.src.kill_switch import KillSwitch

router = APIRouter(tags=["commands"])


def _get_redis():
    return RedisClient.get_instance(settings.REDIS_URL).get_connection()


class KillSwitchRequest(BaseModel):
    active: bool
    reason: Optional[str] = None


@router.post("/")
async def handle_command(
    cmd: CommandIntent,
    user_id: str = Depends(get_current_user),
):
    """
    LLM intent classification mapping sentences into executable payloads.
    NOTE: This endpoint is a placeholder for the LLM integration.
    """
    raise HTTPException(
        status_code=501,
        detail="Natural language command processing is not yet implemented"
    )


@router.get("/kill-switch", response_model=KillSwitchStatusResponse)
async def get_kill_switch_status(user_id: str = Depends(get_current_user)):
    """Get the current kill switch status and recent activity log."""
    redis = _get_redis()
    return await KillSwitch.status(redis)


@router.post("/kill-switch", response_model=KillSwitchToggleResponse)
async def set_kill_switch(
    body: KillSwitchRequest,
    user_id: str = Depends(get_current_user),
):
    """Activate or deactivate the global kill switch.

    When active, ALL trading is halted immediately across all profiles.
    """
    redis = _get_redis()
    reason = body.reason or "manual"

    if body.active:
        await KillSwitch.activate(redis, reason=reason, activated_by=user_id)
        return {"status": "activated", "reason": reason}
    else:
        await KillSwitch.deactivate(redis, reason=reason, deactivated_by=user_id)
        return {"status": "deactivated", "reason": reason}
