from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from ..deps import get_current_user

router = APIRouter(prefix="/commands", tags=["commands"])


class CommandIntent(BaseModel):
    natural_language: str


@router.post("/")
async def handle_command(
    cmd: CommandIntent,
    user_id: str = Depends(get_current_user),
):
    """
    LLM intent classification mapping sentences into executable payloads.
    Example: "stop trading on my BTC profile" -> STOP_TRADING {"profile": "BTC"}

    NOTE: This endpoint is a placeholder for the LLM integration.
    Full implementation will classify intents and execute actions
    scoped to the authenticated user's profiles only.
    """
    raise HTTPException(
        status_code=501,
        detail="Natural language command processing is not yet implemented"
    )
