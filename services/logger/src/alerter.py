import logging
from libs.observability import get_logger

logger = get_logger("logger.alerter")

class Alerter:
    def __init__(self, pagerduty_key: str = None, slack_webhook: str = None):
        self.pd_key = pagerduty_key
        self.slack_webhook = slack_webhook

    async def send_alert(self, event):
        payload = {
            "type": event.event_type if hasattr(event, 'event_type') else "UNKNOWN",
            "profile_id": event.profile_id if hasattr(event, 'profile_id') else "SYSTEM",
            "timestamp": event.timestamp_us if hasattr(event, 'timestamp_us') else 0,
            "reason": getattr(event, "reason", "Critical Event Triggered")
        }
        
        # PagerDuty & Slack Mocking
        if not self.pd_key and not self.slack_webhook:
            logger.warning("No Alerting keys configured, dropping alert to standard out", json_payload=payload)
        else:
            logger.info("Dispatching external alert via configured webhooks", json_payload=payload)
