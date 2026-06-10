from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from libs.config import settings
from libs.core.enums import HaltLevel
from libs.core.schemas import (
    CommandIntent,
    KillSwitchStatusResponse,
    KillSwitchToggleResponse,
)
from libs.storage import RedisClient
from services.hot_path.src.kill_switch import KillSwitch

from ..deps import get_current_user

router = APIRouter(tags=["commands"])


def _get_redis():
    return RedisClient.get_instance(settings.REDIS_URL).get_connection()


class KillSwitchRequest(BaseModel):
    active: bool = True
    reason: Optional[str] = None
    # PR3: optional tiered level (NONE/STOP_OPENING/DE_RISK/NEUTRALIZE/FLATTEN).
    # When set it takes precedence over `active`. FLATTEN here is an explicit human
    # authorization — the HaltController will close all open positions.
    level: Optional[str] = None


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
        detail="Natural language command processing is not yet implemented",
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

    # Tiered level takes precedence (PR3). FLATTEN via the API is an explicit
    # human authorization to close all open positions.
    if body.level is not None:
        try:
            level = HaltLevel(body.level.strip().upper())
        except ValueError:
            raise HTTPException(
                status_code=422, detail=f"Invalid halt level: {body.level}"
            )
        await KillSwitch.set_level(redis, level, reason=reason, actor=user_id)
        return {"status": level.value.lower(), "reason": reason, "level": level.value}

    # Legacy binary toggle: active=True -> STOP_OPENING, active=False -> NONE.
    if body.active:
        await KillSwitch.activate(redis, reason=reason, activated_by=user_id)
        return {
            "status": "activated",
            "reason": reason,
            "level": HaltLevel.STOP_OPENING.value,
        }
    else:
        await KillSwitch.deactivate(redis, reason=reason, deactivated_by=user_id)
        return {
            "status": "deactivated",
            "reason": reason,
            "level": HaltLevel.NONE.value,
        }
