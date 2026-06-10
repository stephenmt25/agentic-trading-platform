"""Global kill switch for emergency trading halt.

When activated, ALL order processing stops immediately across all profiles
and symbols. No trades will be evaluated, approved, or executed until the
kill switch is deactivated.

Activation methods:
  1. API: POST /commands/kill-switch {active: true/false}
  2. Redis: SET praxis:kill_switch "1"
  3. Code: await KillSwitch.activate(redis, reason="...")

The kill switch is checked at the top of every hot-path tick processing
loop — before strategy evaluation, risk gates, or any other logic.
"""

import json
import time

from libs.core.enums import HaltLevel
from libs.observability import get_logger

logger = get_logger("hot-path.kill-switch")

KILL_SWITCH_KEY = "praxis:kill_switch"
KILL_SWITCH_LOG_KEY = "praxis:kill_switch:log"


def _parse_level(val) -> HaltLevel:
    """Read the stored kill-switch value into a HaltLevel.

    Backward compatible: a legacy "1"/"true" means STOP_OPENING; empty/None/"0"
    means NONE; otherwise the value is a HaltLevel name. An unrecognised value is
    treated as STOP_OPENING (conservative — assume *some* halt rather than none).
    """
    if val is None:
        return HaltLevel.NONE
    if isinstance(val, bytes):
        val = val.decode()
    val = str(val).strip().upper()
    if val in ("", "0", "FALSE", "NONE"):
        return HaltLevel.NONE
    if val in ("1", "TRUE"):
        return HaltLevel.STOP_OPENING
    try:
        return HaltLevel(val)
    except ValueError:
        return HaltLevel.STOP_OPENING


class KillSwitch:
    """Stateless kill switch backed by a single Redis key.

    Reading is a single GET — sub-microsecond overhead per tick.
    """

    @staticmethod
    async def is_active(redis_client) -> bool:
        """True if trading entry is halted (any level STOP_OPENING and above).

        This is the hot-path per-tick check — a single GET. Fail-safe: if Redis
        is unreachable, block trading.
        """
        try:
            val = await redis_client.get(KILL_SWITCH_KEY)
            return _parse_level(val).at_least(HaltLevel.STOP_OPENING)
        except Exception as e:
            # If Redis is unreachable, fail SAFE — block trading
            logger.error(
                "Kill switch Redis check failed — defaulting to ACTIVE (safe)",
                error=str(e),
            )
            return True

    @staticmethod
    async def get_level(redis_client) -> HaltLevel:
        """Return the current tiered halt level. Used by the HaltController to
        decide actions (incl. FLATTEN). Fail-safe is DELIBERATELY non-destructive:
        on a Redis error we return STOP_OPENING (assume a halt, but never trigger
        an automated FLATTEN off a transient blip — the policy's false-positive
        self-harm concern)."""
        try:
            return _parse_level(await redis_client.get(KILL_SWITCH_KEY))
        except Exception as e:
            logger.error(
                "Kill switch level read failed — defaulting to STOP_OPENING",
                error=str(e),
            )
            return HaltLevel.STOP_OPENING

    @staticmethod
    async def set_level(
        redis_client, level: HaltLevel, reason: str = "manual", actor: str = "system"
    ):
        """Set the tiered halt level. NONE clears the halt; any other level
        engages it. NEUTRALIZE+ is logged CRITICAL (it triggers position closes
        via the HaltController)."""
        if level == HaltLevel.NONE:
            await redis_client.delete(KILL_SWITCH_KEY)
        else:
            await redis_client.set(KILL_SWITCH_KEY, level.value)
        log_entry = json.dumps(
            {
                "action": f"SET_{level.value}",
                "reason": reason,
                "actor": actor,
                "timestamp": time.time(),
            }
        )
        await redis_client.lpush(KILL_SWITCH_LOG_KEY, log_entry)
        await redis_client.ltrim(KILL_SWITCH_LOG_KEY, 0, 99)
        emit = (
            logger.critical if level.at_least(HaltLevel.NEUTRALIZE) else logger.warning
        )
        emit("HALT LEVEL SET", level=level.value, reason=reason, actor=actor)

    @staticmethod
    async def activate(
        redis_client, reason: str = "manual", activated_by: str = "system"
    ):
        """Engage the kill switch. All trading stops immediately."""
        await redis_client.set(KILL_SWITCH_KEY, "1")
        log_entry = json.dumps(
            {
                "action": "ACTIVATED",
                "reason": reason,
                "activated_by": activated_by,
                "timestamp": time.time(),
            }
        )
        await redis_client.lpush(KILL_SWITCH_LOG_KEY, log_entry)
        await redis_client.ltrim(KILL_SWITCH_LOG_KEY, 0, 99)  # keep last 100 entries
        logger.critical(
            "KILL SWITCH ACTIVATED — all trading halted",
            reason=reason,
            activated_by=activated_by,
        )

    @staticmethod
    async def deactivate(
        redis_client, reason: str = "manual", deactivated_by: str = "system"
    ):
        """Disengage the kill switch. Trading resumes."""
        await redis_client.delete(KILL_SWITCH_KEY)
        log_entry = json.dumps(
            {
                "action": "DEACTIVATED",
                "reason": reason,
                "deactivated_by": deactivated_by,
                "timestamp": time.time(),
            }
        )
        await redis_client.lpush(KILL_SWITCH_LOG_KEY, log_entry)
        await redis_client.ltrim(KILL_SWITCH_LOG_KEY, 0, 99)
        logger.warning(
            "KILL SWITCH DEACTIVATED — trading resumed",
            reason=reason,
            deactivated_by=deactivated_by,
        )

    @staticmethod
    async def status(redis_client) -> dict:
        """Return current kill switch status (level + active flag) and recent log."""
        level = await KillSwitch.get_level(redis_client)
        active = level.at_least(HaltLevel.STOP_OPENING)
        log = []
        try:
            log_raw = await redis_client.lrange(KILL_SWITCH_LOG_KEY, 0, 9)
            for entry in log_raw or []:
                try:
                    log.append(json.loads(entry))
                except (json.JSONDecodeError, TypeError):
                    pass
        except Exception as e:
            # Redis unreachable — is_active already returned True (fail-safe).
            # Don't let a follow-on lrange failure 500 the endpoint; operators
            # need to see active=true cleanly.
            logger.error(
                "Kill switch log fetch failed — returning empty log", error=str(e)
            )
        return {"active": active, "level": level.value, "recent_log": log}
