"""Cross-service heartbeat watcher (fail-safe Layer 2).

Each service runs a TelemetryPublisher.start_health_loop() that emits a
`health_check` event every 5 s to `pubsub:agent_telemetry`. This watcher
tracks the most recent heartbeat per service and raises a RED alert when
one stops beating for longer than the threshold — even if the underlying
HTTP /health endpoint is still up. That covers the 2026-05-26/27 silent-
fail mode where execution's run() task died with a Redis timeout but the
FastAPI process kept the /health endpoint responding 200, so external
observers saw no problem for 18 hours.

Independent guarantee from Layer 1 (per-service supervisor): the
supervisor *rescues* a hung loop by restarting it; this watcher *detects*
when even the supervisor has lost coverage — supervisor itself crashed,
or the supervised loop spins inside an infinite synchronous block. The
two layers catch overlapping but non-identical failure modes.
"""

import asyncio
import json
import time
from datetime import datetime, timezone

from libs.core.enums import EventType
from libs.core.schemas import AlertEvent
from libs.messaging import PubSubBroadcaster
from libs.messaging._pubsub import PubSubSubscriber
from libs.messaging.channels import PUBSUB_AGENT_TELEMETRY, PUBSUB_SYSTEM_ALERTS
from libs.observability import get_logger

logger = get_logger("logger.heartbeat_watcher")


class HeartbeatWatcher:
    """Track last-seen timestamps per service. Emit RED alert on stall."""

    # Default thresholds. Heartbeats are emitted every 5 s; tolerate up to
    # 6 missed beats before alerting. Short enough to be useful, long
    # enough that one Redis hiccup doesn't fire false alarms.
    DEFAULT_STALL_THRESHOLD_S = 30.0
    DEFAULT_CHECK_INTERVAL_S = 10.0

    def __init__(
        self,
        subscriber: PubSubSubscriber,
        publisher: PubSubBroadcaster,
        stall_threshold_s: float = DEFAULT_STALL_THRESHOLD_S,
        check_interval_s: float = DEFAULT_CHECK_INTERVAL_S,
    ):
        self._subscriber = subscriber
        self._publisher = publisher
        self._stall_threshold_s = stall_threshold_s
        self._check_interval_s = check_interval_s

        # agent_id -> monotonic time of last health_check observed
        self._last_seen: dict[str, float] = {}
        # agent_ids we've already alerted on; cleared when service returns
        self._alerted_stale: set[str] = set()

        # Heartbeat for this watcher's own loops (eat your own dogfood;
        # main.py's stall watchdog reads this).
        self.last_progress_mono = time.monotonic()

    async def run_subscriber(self):
        """Consume telemetry events and update last-seen timestamps.

        Wrapped supervisor: a Redis hiccup on this subscription would
        otherwise blind us to silent fails — which is the exact opposite
        of what this watcher exists to do."""
        while True:
            try:
                await self._subscriber.subscribe(
                    PUBSUB_AGENT_TELEMETRY, self._on_telemetry
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "heartbeat watcher subscriber crashed — restarting",
                    error=str(exc),
                )
                await asyncio.sleep(1)

    async def _on_telemetry(self, raw):
        """Handle one telemetry event. Bumps progress + updates last-seen."""
        self.last_progress_mono = time.monotonic()
        try:
            # PubSubBroadcaster.publish encodes with msgpack via
            # encode_event; the TelemetryPublisher path bypasses that and
            # publishes raw json (see libs/observability/telemetry.py:65).
            # Tolerate both shapes.
            if isinstance(raw, bytes):
                try:
                    msg = json.loads(raw)
                except Exception:
                    return  # msgpack-encoded events aren't ours
            elif isinstance(raw, str):
                msg = json.loads(raw)
            else:
                return

            if msg.get("event_type") != "health_check":
                return

            agent_id = msg.get("agent_id")
            if not agent_id:
                return

            self._last_seen[agent_id] = time.monotonic()
            # If this service had been flagged stale, clear and emit
            # recovery alert so frontend can surface the OK transition.
            if agent_id in self._alerted_stale:
                self._alerted_stale.discard(agent_id)
                await self._publish_recovery(agent_id)
        except Exception:
            logger.exception("heartbeat _on_telemetry handler error")

    async def run_scanner(self):
        """Periodic scan: any service whose last_seen is older than
        threshold gets a RED alert (once, until it recovers)."""
        while True:
            try:
                self.last_progress_mono = time.monotonic()
                now = time.monotonic()
                for agent_id, last_seen in list(self._last_seen.items()):
                    stalled_for = now - last_seen
                    if stalled_for > self._stall_threshold_s:
                        if agent_id not in self._alerted_stale:
                            self._alerted_stale.add(agent_id)
                            await self._publish_stall(agent_id, stalled_for)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("heartbeat scanner pass failed")
            await asyncio.sleep(self._check_interval_s)

    async def _publish_stall(self, agent_id: str, stalled_for_s: float):
        """Emit a RED alert. Surfaces in frontend chrome via existing
        api_gateway WS fan-out of pubsub:system_alerts."""
        msg = (
            f"Service '{agent_id}' has not emitted a health heartbeat "
            f"for {stalled_for_s:.0f}s (threshold {self._stall_threshold_s:.0f}s). "
            f"Loop may be wedged. Investigate before the soak window is contaminated."
        )
        logger.error(
            "service_stall_detected",
            agent_id=agent_id,
            stalled_for_s=round(stalled_for_s, 1),
            threshold_s=self._stall_threshold_s,
        )
        event = AlertEvent(
            event_type=EventType.ALERT_RED,
            timestamp_us=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            source_service="logger.heartbeat_watcher",
            message=msg,
            level="RED",
        )
        try:
            await self._publisher.publish(PUBSUB_SYSTEM_ALERTS, event)
        except Exception:
            logger.exception(
                "Failed to publish stall alert to pubsub:system_alerts",
                agent_id=agent_id,
            )

    async def _publish_recovery(self, agent_id: str):
        """Emit an AMBER alert when a stalled service starts beating again."""
        msg = f"Service '{agent_id}' is heartbeating again — stall cleared."
        logger.info("service_stall_recovered", agent_id=agent_id)
        event = AlertEvent(
            event_type=EventType.ALERT_AMBER,
            timestamp_us=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            source_service="logger.heartbeat_watcher",
            message=msg,
            level="AMBER",
        )
        try:
            await self._publisher.publish(PUBSUB_SYSTEM_ALERTS, event)
        except Exception:
            logger.exception(
                "Failed to publish recovery alert to pubsub:system_alerts",
                agent_id=agent_id,
            )

    def snapshot(self) -> dict:
        """For debug/tests: dict of agent_id -> seconds since last heartbeat."""
        now = time.monotonic()
        return {
            agent_id: round(now - last_seen, 1)
            for agent_id, last_seen in self._last_seen.items()
        }
