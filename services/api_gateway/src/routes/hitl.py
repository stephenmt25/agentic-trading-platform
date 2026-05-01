import json
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import get_current_user
from libs.storage import RedisClient
from libs.config import settings

router = APIRouter(tags=["hitl"])


def _get_redis():
    return RedisClient.get_instance(settings.REDIS_URL).get_connection()


# Source of truth for pending HITL requests is the Redis key prefix the
# hot_path HITL gate writes to; see services/hot_path/src/hitl_gate.py:99.
# Each key auto-expires HITL_TIMEOUT_S+30s after creation, so SCAN-then-GET
# returns the live queue without any background sweep on our side.
_PENDING_KEY_PREFIX = "hitl:pending:"


class HITLRespondRequest(BaseModel):
    request_id: str
    status: Literal["APPROVED", "REJECTED"]
    reason: Optional[str] = None


@router.get("/pending", response_model=List[dict])
async def list_pending(user_id: str = Depends(get_current_user)) -> List[Any]:
    """Return every HITL request currently awaiting human approval.

    The frontend's WebSocket subscription to `pubsub:hitl_pending` only
    surfaces events that arrive while the browser is connected, which means
    a fresh page load shows an empty queue even when trades are pending.
    This endpoint replays the live queue from Redis so the Approvals panel
    is honest at first paint.

    Sorted newest-first by `timestamp_us`; entries with parse errors are
    skipped (not surfaced) so a single corrupt payload can't blank the list.
    """
    redis = _get_redis()
    pattern = f"{_PENDING_KEY_PREFIX}*"
    requests: List[dict] = []

    # SCAN in batches; KEYS would block Redis on a busy queue.
    async for key in redis.scan_iter(match=pattern, count=100):
        raw = await redis.get(key)
        if raw is None:
            continue  # Expired between SCAN and GET — ignore.
        try:
            requests.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            continue

    requests.sort(key=lambda r: r.get("timestamp_us", 0), reverse=True)
    return requests


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
