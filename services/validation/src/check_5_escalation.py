from collections import defaultdict
import datetime
from typing import Dict, Any

class EscalationCheck:
    def __init__(self, validation_repo, pubsub):
        self._validation_repo = validation_repo
        self._pubsub = pubsub
        # Tracks timestamp list per profile/check_type
        self._amber_history = defaultdict(lambda: defaultdict(list))

    async def evaluate(self, profile_id: str, check_type: str, result: Dict[str, Any]):
        """
        Reads results from checks 2-5:
        If reason contains 'AMBER', adds to history.
        If 5 ambers in 24h -> Auto Escalate to RED.
        If reason contains 'RED', escalate to RED immediately.
        """
        reason = result.get("reason", "")
        if "RED" in reason.upper():
            await self._trigger_halt(profile_id, reason)
            return "RED"
            
        if "AMBER" in reason.upper():
            now = datetime.datetime.utcnow()
            history = self._amber_history[profile_id][check_type]
            history.append(now)
            
            # Prune > 24h
            cutoff = now - datetime.timedelta(hours=24)
            history = [ts for ts in history if ts > cutoff]
            self._amber_history[profile_id][check_type] = history
            
            if len(history) >= 5:
                # Escalation
                await self._trigger_halt(profile_id, f"Auto-Escalation: 5 AMBERs in 24h for {check_type}")
                return "RED"
                
            return "AMBER"
            
        return "GREEN"

    async def _trigger_halt(self, profile_id: str, reason: str):
        # Triggers PUB/SUB System Alert + Writes Trading Halt state
        print(f"[ESCALATION] Trading Halt on {profile_id}: {reason}")
        # await self._pubsub.publish("system_alerts", {"level": "RED", "profile_id": profile_id, "reason": reason})
