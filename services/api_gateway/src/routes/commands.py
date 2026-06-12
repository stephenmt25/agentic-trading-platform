from typing import FrozenSet, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from libs.config import settings
from libs.core.enums import HaltLevel
from libs.core.schemas import KillSwitchStatusResponse, KillSwitchToggleResponse
from libs.storage import RedisClient
from services.hot_path.src.kill_switch import KillSwitch

from ..deps import get_current_user
from ..middleware.rate_limit import user_rate_limit

router = APIRouter(tags=["commands"])

# Post-auth per-user bucket for kill-switch WRITES (registry row 64c): the
# pre-auth RateLimiterMiddleware keys on client IP (shared behind a proxy),
# so a single authenticated account could flood the safety-critical halt log.
# 10 writes/min is generous for frantic-but-legitimate operator use while
# stopping scripted log-flooding. Fail-open on Redis errors (see factory).
_kill_switch_write_bucket = user_rate_limit("kill-switch", limit=10, window_s=60)


def _get_redis():
    return RedisClient.get_instance(settings.REDIS_URL).get_connection()


def _operator_allowlist() -> Optional[FrozenSet[str]]:
    """Per-deployment operator allowlist for destructive halt control.

    Source: the typed `settings.KILL_SWITCH_OPERATORS` Pydantic setting
    (env `PRAXIS_KILL_SWITCH_OPERATORS`, comma-separated user_ids) —
    registry row 64a; the raw environment-variable fallback is gone.

    Returns None when unconfigured — single-operator mode: every authenticated
    user is the operator. This preserves the current single-user deployment
    (a halt control that nobody can pull is worse than one without tiers) but
    MUST be configured before the gateway serves more than one human.
    """
    raw = settings.KILL_SWITCH_OPERATORS
    if raw is None or not str(raw).strip():
        return None
    return frozenset(x.strip() for x in str(raw).split(",") if x.strip())


def is_operator(user_id: str) -> bool:
    """True when `user_id` may perform destructive/clearing kill-switch actions
    (NEUTRALIZE / FLATTEN / clearing a halt) and view the actor-attributed
    activity log. See `_operator_allowlist` for the unconfigured default."""
    allow = _operator_allowlist()
    return True if allow is None else user_id in allow


class KillSwitchRequest(BaseModel):
    active: bool = True
    # Bounded: the reason is persisted verbatim to the praxis:kill_switch:log
    # Redis list and re-served on every status poll — an unbounded string lets
    # any authenticated user bloat the safety-critical read path (CWE-400).
    reason: Optional[str] = Field(None, max_length=256)
    # PR3: optional tiered level (NONE/STOP_OPENING/DE_RISK/NEUTRALIZE/FLATTEN).
    # When set it takes precedence over `active`. FLATTEN here is an explicit human
    # authorization — the HaltController will close all open positions.
    # max_length bounds the value before it is reflected into the 422 detail.
    level: Optional[str] = Field(None, max_length=32)


# NOTE: the former `POST /commands/` LLM intent-classification endpoint (a
# permanent 501 stub) was removed per ruling D-F (2026-06-13, wontfix): the
# command palette shipped without natural-language commands and nothing calls
# the route. If NL command processing is ever built, design it fresh against
# `CommandIntent` in libs/core/schemas.py rather than reviving the stub.


@router.get("/kill-switch", response_model=KillSwitchStatusResponse)
async def get_kill_switch_status(user_id: str = Depends(get_current_user)):
    """Get the current kill switch status and recent activity log.

    The activity log carries actor user_ids and free-text reasons from every
    account — operator-only when an allowlist is configured (CWE-200);
    non-operators still get the level/active truth they need for the UI.
    """
    redis = _get_redis()
    status = await KillSwitch.status(redis)
    if not is_operator(user_id):
        status["recent_log"] = []
    return status


@router.post(
    "/kill-switch",
    response_model=KillSwitchToggleResponse,
    dependencies=[Depends(_kill_switch_write_bucket)],
)
async def set_kill_switch(
    body: KillSwitchRequest,
    user_id: str = Depends(get_current_user),
):
    """Activate or deactivate the global kill switch.

    When active, ALL trading is halted immediately across all profiles.

    Authorization (CWE-862 fix): the switch is platform-global, so anyone may
    PULL the brake (STOP_OPENING / DE_RISK — non-destructive escalation), but
    position-destructive levels (NEUTRALIZE / FLATTEN close other users'
    positions via the HaltController) and CLEARING a halt (NONE — silently
    resumes trading someone else stopped) require operator authorization.

    Rate limit (row 64c): writes pass a post-auth per-user sliding window
    (10/min) — see `_kill_switch_write_bucket`.
    """
    redis = _get_redis()
    reason = body.reason or "manual"

    def _require_operator(action: str) -> None:
        if not is_operator(user_id):
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Operator authorization required for {action}. "
                    "Configure PRAXIS_KILL_SWITCH_OPERATORS."
                ),
            )

    # Tiered level takes precedence (PR3). FLATTEN via the API is an explicit
    # human authorization to close all open positions.
    if body.level is not None:
        try:
            level = HaltLevel(body.level.strip().upper())
        except ValueError:
            # body.level is bounded to 32 chars by the request model, so the
            # reflection cannot bloat the response.
            raise HTTPException(
                status_code=422, detail=f"Invalid halt level: {body.level}"
            )
        if level.at_least(HaltLevel.NEUTRALIZE) or level == HaltLevel.NONE:
            _require_operator(
                f"halt level {level.value}"
                if level != HaltLevel.NONE
                else "clearing the halt (NONE)"
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
        _require_operator("clearing the halt (deactivate)")
        await KillSwitch.deactivate(redis, reason=reason, deactivated_by=user_id)
        return {
            "status": "deactivated",
            "reason": reason,
            "level": HaltLevel.NONE.value,
        }
