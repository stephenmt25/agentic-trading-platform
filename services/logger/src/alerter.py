import json
import logging
import httpx
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
            "reason": getattr(event, "reason", getattr(event, "message", "Critical Event Triggered"))
        }

        dispatched = False

        # PagerDuty Events API v2
        if self.pd_key:
            try:
                await self._send_pagerduty(payload)
                dispatched = True
            except Exception as e:
                logger.error("PagerDuty dispatch failed", error=str(e))

        # Slack Incoming Webhook
        if self.slack_webhook:
            try:
                await self._send_slack(payload)
                dispatched = True
            except Exception as e:
                logger.error("Slack dispatch failed", error=str(e))

        if not dispatched:
            logger.warning("No alerting channels configured or all failed, logging alert locally", json_payload=payload)

    async def _send_pagerduty(self, payload: dict):
        """Send an alert to PagerDuty Events API v2."""
        pd_payload = {
            "routing_key": self.pd_key,
            "event_action": "trigger",
            "dedup_key": f"praxis-{payload['type']}-{payload['profile_id']}-{payload['timestamp']}",
            "payload": {
                "summary": f"[PRAXIS] {payload['type']}: {payload['reason']}",
                "severity": "critical" if "RED" in str(payload.get("type", "")) else "warning",
                "source": "praxis-trading-platform",
                "component": "validation",
                "custom_details": payload,
            },
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=pd_payload,
            )
            if resp.status_code not in (200, 202):
                logger.error("PagerDuty returned non-OK status", status=resp.status_code, body=resp.text)
            else:
                logger.info("PagerDuty alert dispatched", dedup_key=pd_payload["dedup_key"])

    async def _send_slack(self, payload: dict):
        """Send an alert to a Slack Incoming Webhook."""
        level_emoji = ":rotating_light:" if "RED" in str(payload.get("type", "")) else ":warning:"
        slack_payload = {
            "text": f"{level_emoji} *PRAXIS Alert — {payload['type']}*\n"
                    f"*Profile:* `{payload['profile_id']}`\n"
                    f"*Reason:* {payload['reason']}\n"
                    f"*Timestamp:* {payload['timestamp']}",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(self.slack_webhook, json=slack_payload)
            if resp.status_code != 200:
                logger.error("Slack returned non-OK status", status=resp.status_code, body=resp.text)
            else:
                logger.info("Slack alert dispatched")
