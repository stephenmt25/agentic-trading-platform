import asyncio
import time
from uuid import UUID

import msgpack

from libs.core.enums import EventType
from libs.core.schemas import AlertEvent
from libs.messaging import PubSubBroadcaster, StreamConsumer
from libs.messaging._pubsub import PubSubSubscriber
from libs.messaging._serialisation import decode_event
from libs.messaging.channels import (
    MARKET_DATA_STREAM,
    ORDERS_STREAM,
    PUBSUB_SYSTEM_ALERTS,
    VALIDATION_STREAM,
)
from libs.observability import get_logger
from libs.storage.repositories import AuditRepository

from .alerter import Alerter

logger = get_logger("logger.subscriber")


class EventSubscriber:
    def __init__(
        self,
        consumer: StreamConsumer,
        pubsub: PubSubBroadcaster,
        audit_repo: AuditRepository,
        alerter: Alerter,
        subscriber: PubSubSubscriber,
    ):
        self.consumer = consumer
        self.pubsub = pubsub
        self.audit_repo = audit_repo
        self.alerter = alerter
        self.subscriber = subscriber

    async def run_streams(self):
        streams = [MARKET_DATA_STREAM, ORDERS_STREAM, VALIDATION_STREAM]
        group = "logger_group"
        consumer_name = "global_auditor"

        while True:
            for s in streams:
                events = await self.consumer.consume(
                    s, group, consumer_name, count=100, block_ms=5
                )
                for msg_id, ev in events:
                    if ev:
                        await self.audit_repo.write_audit_event(ev, {"stream": s})

                        # Trigger alert on specific event types (e.g. Reject, Error)
                        if getattr(ev, "event_type", "") in [
                            "OrderRejectedEvent",
                            "ReconciliationDriftError",
                        ]:
                            await self.alerter.send_alert(ev)

                if events:
                    await self.consumer.ack(s, group, [m for m, _ in events])

            await asyncio.sleep(0.01)

    def _decode_alert(self, raw) -> AlertEvent | None:
        """Decode a pubsub:system_alerts payload into a real AlertEvent.

        Every publisher on this channel sends an AlertEvent through
        PubSubBroadcaster (msgpack via encode_event), so decode_event is the
        canonical path. A defensive fallback synthesises an AlertEvent from a
        bare msgpack dict (no ``__type__``) so a legacy/foreign publisher
        degrades to a usable event instead of crash-looping the subscriber.
        """
        try:
            ev = decode_event(raw)
            if isinstance(ev, AlertEvent):
                return ev
        except Exception:
            pass

        try:
            message = (
                msgpack.unpackb(raw, raw=False)
                if isinstance(raw, (bytes, bytearray))
                else dict(raw)
            )
            return AlertEvent(
                event_type=EventType.SYSTEM_ALERT,
                timestamp_us=int(
                    message.get("timestamp_us") or time.time() * 1_000_000
                ),
                source_service=str(message.get("source_service", "unknown")),
                message=str(
                    message.get("message") or message.get("reason") or "Unknown Alert"
                ),
                level=str(message.get("level", "INFO")),
                profile_id=message.get("profile_id"),
            )
        except Exception:
            logger.warning("Failed to decode system-alert message, skipping")
            return None

    async def _on_alert(self, raw):
        """Handle one pubsub:system_alerts message.

        Historical bugs fixed here: the handler used to (a) forward a MockEv
        reading non-existent ``reason``/``profile_id`` keys (AlertEvent
        carries ``message``/``source_service``), so RED alerts re-dispatched
        as "Unknown Alert"/"GLOBAL"; and (b) pass a raw dict to
        ``write_audit_event``, which reads ``event.event_id`` — crash-looping
        the whole pubsub subscriber on EVERY alert
        ("'dict' object has no attribute 'event_id'").
        """
        ev = self._decode_alert(raw)
        if ev is None:
            return

        try:
            if ev.level == "RED":
                # Alerter resolves the text via getattr(event, "reason",
                # getattr(event, "message", ...)) — the real AlertEvent fields
                # flow through (message/source_service/profile_id).
                await self.alerter.send_alert(ev)

            # Audit-log every alert seen on the channel. The audit_log
            # profile_id column is UUID — only pass it through when it parses
            # (publishers may use sentinel strings); the raw value is always
            # preserved inside the JSON payload.
            payload = {
                "channel": PUBSUB_SYSTEM_ALERTS,
                "message": ev.message,
                "level": ev.level,
                "source_service": ev.source_service,
                "alert_profile_id": ev.profile_id,
            }
            if ev.profile_id:
                try:
                    UUID(str(ev.profile_id))
                    payload["profile_id"] = ev.profile_id
                except ValueError:
                    pass
            await self.audit_repo.write_audit_event(ev, payload)
        except Exception as exc:
            # Survive per-message failures (e.g. a transient DB blip on the
            # audit write) instead of killing the pubsub subscription loop.
            logger.error(
                "system-alert handling failed",
                error_type=type(exc).__name__,
                error=repr(exc),
            )

    async def run_pubsub(self):
        await self.subscriber.subscribe(PUBSUB_SYSTEM_ALERTS, self._on_alert)
