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
from typing import Optional

from libs.observability import get_logger

logger = get_logger("hot-path.kill-switch")

KILL_SWITCH_KEY = "praxis:kill_switch"
KILL_SWITCH_LOG_KEY = "praxis:kill_switch:log"


class KillSwitch:
    """Stateless kill switch backed by a single Redis key.

    Reading is a single GET — sub-microsecond overhead per tick.
    """

    @staticmethod
    async def is_active(redis_client) -> bool:
        """Returns True if the kill switch is engaged."""
        try:
            val = await redis_client.get(KILL_SWITCH_KEY)
            return val is not None and val in (b"1", "1", b"true", "true")
        except Exception as e:
            # If Redis is unreachable, fail SAFE — block trading
            logger.error("Kill switch Redis check failed — defaulting to ACTIVE (safe)", error=str(e))
            return True

    @staticmethod
    async def activate(redis_client, reason: str = "manual", activated_by: str = "system"):
        """Engage the kill switch. All trading stops immediately."""
        await redis_client.set(KILL_SWITCH_KEY, "1")
        log_entry = json.dumps({
            "action": "ACTIVATED",
            "reason": reason,
            "activated_by": activated_by,
            "timestamp": time.time(),
        })
        await redis_client.lpush(KILL_SWITCH_LOG_KEY, log_entry)
        await redis_client.ltrim(KILL_SWITCH_LOG_KEY, 0, 99)  # keep last 100 entries
        logger.critical(
            "KILL SWITCH ACTIVATED — all trading halted",
            reason=reason,
            activated_by=activated_by,
        )

    @staticmethod
    async def deactivate(redis_client, reason: str = "manual", deactivated_by: str = "system"):
        """Disengage the kill switch. Trading resumes."""
        await redis_client.delete(KILL_SWITCH_KEY)
        log_entry = json.dumps({
            "action": "DEACTIVATED",
            "reason": reason,
            "deactivated_by": deactivated_by,
            "timestamp": time.time(),
        })
        await redis_client.lpush(KILL_SWITCH_LOG_KEY, log_entry)
        await redis_client.ltrim(KILL_SWITCH_LOG_KEY, 0, 99)
        logger.warning(
            "KILL SWITCH DEACTIVATED — trading resumed",
            reason=reason,
            deactivated_by=deactivated_by,
        )

    @staticmethod
    async def status(redis_client) -> dict:
        """Return current kill switch status and recent log."""
        active = await KillSwitch.is_active(redis_client)
        log_raw = await redis_client.lrange(KILL_SWITCH_LOG_KEY, 0, 9)
        log = []
        for entry in (log_raw or []):
            try:
                log.append(json.loads(entry))
            except (json.JSONDecodeError, TypeError):
                pass
        return {"active": active, "recent_log": log}
