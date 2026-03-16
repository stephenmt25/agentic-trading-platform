from collections import defaultdict
import datetime
from typing import Dict, Any
from libs.core.schemas import AlertEvent
from libs.core.enums import EventType
from libs.messaging.channels import PUBSUB_SYSTEM_ALERTS
from libs.observability import get_logger

logger = get_logger("validation.escalation")

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
        """Publishes a RED system alert via PubSub and records the trading halt."""
        logger.critical("Trading halt triggered", profile_id=profile_id, reason=reason)

        # Publish structured alert over PubSub so all services (executor, PnL, alerter) react
        alert_event = AlertEvent(
            event_type=EventType.ALERT_RED,
            timestamp_us=int(datetime.datetime.utcnow().timestamp() * 1_000_000),
            source_service="validation",
            message=reason,
            level="RED",
            profile_id=profile_id,
        )
        try:
            await self._pubsub.publish(PUBSUB_SYSTEM_ALERTS, alert_event)
        except Exception as e:
            logger.error("Failed to publish halt alert via PubSub", error=str(e))

        # Write halt flag to Redis so executor fast-checks before placing orders
        try:
            # Convention: any service can check this key before allowing trades
            redis_conn = getattr(self._pubsub, '_redis', None)
            if redis_conn:
                halt_key = f"halt:{profile_id}"
                await redis_conn.set(halt_key, reason, ex=86400)  # 24h TTL
        except Exception as e:
            logger.error("Failed to persist halt flag to Redis", error=str(e))
