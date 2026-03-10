import asyncio
from libs.messaging import StreamConsumer, PubSubBroadcaster
from libs.storage.repositories import AuditRepository
from libs.observability import get_logger
from libs.messaging.channels import MARKET_DATA_STREAM, ORDERS_STREAM, VALIDATION_STREAM, PUBSUB_SYSTEM_ALERTS
from .alerter import Alerter

logger = get_logger("logger.subscriber")

class EventSubscriber:
    def __init__(
        self,
        consumer: StreamConsumer,
        pubsub: PubSubBroadcaster,
        audit_repo: AuditRepository,
        alerter: Alerter
    ):
        self.consumer = consumer
        self.pubsub = pubsub
        self.audit_repo = audit_repo
        self.alerter = alerter

    async def run_streams(self):
        streams = [MARKET_DATA_STREAM, ORDERS_STREAM, VALIDATION_STREAM]
        group = "logger_group"
        consumer_name = "global_auditor"
        
        while True:
            for s in streams:
                events = await self.consumer.consume(s, group, consumer_name, count=100, block_ms=5)
                for msg_id, ev in events:
                    if ev:
                        await self.audit_repo.write_audit_event(ev, {"stream": s})
                        
                        # Trigger alert on specific event types (e.g. Reject, Error)
                        if getattr(ev, 'event_type', '') in ['OrderRejectedEvent', 'ReconciliationDriftError']:
                            await self.alerter.send_alert(ev)
                            
                if events:
                    await self.consumer.ack(s, group, [m for m, _ in events])
            
            await asyncio.sleep(0.01)

    async def run_pubsub(self):
        async for channel, message in self.pubsub.subscribe(PUBSUB_SYSTEM_ALERTS):
            # Parse alert level
            level = message.get("level", "INFO")
            if level == "RED":
                # Need to convert raw message to mock event for Alerter
                class MockEv:
                    event_type = "SYSTEM_ALERT"
                    profile_id = message.get("profile_id", "GLOBAL")
                    reason = message.get("reason", "Unknown Alert")
                # Dispatch Outbound
                await self.alerter.send_alert(MockEv())
            
            # Audit log pubsub writes
            await self.audit_repo.write_audit_event({"raw_message": message}, {"channel": PUBSUB_SYSTEM_ALERTS})
