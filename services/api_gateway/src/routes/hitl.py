import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import get_current_user
from libs.storage import RedisClient
from libs.config import settings

router = APIRouter(tags=["hitl"])


def _get_redis():
    return RedisClient.get_instance(settings.REDIS_URL).get_connection()


class HITLRespondRequest(BaseModel):
    request_id: str
    status: Literal["APPROVED", "REJECTED"]
    reason: Optional[str] = None


@router.post("/respond")
async def respond_to_hitl(
    body: HITLRespondRequest,
    user_id: str = Depends(get_current_user),
):
    """Process a human approve/reject decision for a pending HITL trade request.

    Pushes the response to the Redis list that the hot-path HITL gate is
    blocking on (BLPOP on hitl:response:{request_id}).
    """
    redis = _get_redis()
    response_key = f"hitl:response:{body.request_id}"
    payload = json.dumps({
        "status": body.status,
        "reason": body.reason or "",
        "reviewer": user_id,
    })
    await redis.lpush(response_key, payload)
    return {"ok": True, "request_id": body.request_id, "status": body.status}
