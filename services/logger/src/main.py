import asyncio
import time
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
from types import SimpleNamespace

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient, AuditRepository
from libs.messaging import StreamConsumer, PubSubBroadcaster
from libs.messaging._pubsub import PubSubSubscriber
from libs.observability import get_logger, supervised_task
from libs.observability.redis_invariants import scan as scan_invariants

from .alerter import Alerter
from .event_subscriber import EventSubscriber
from .heartbeat_watcher import HeartbeatWatcher

logger = get_logger("logger")


async def redis_invariants_loop(redis, alerter: Alerter):
    """Periodic Redis schema invariant scan. Logs healthy results, routes
    violations through the existing alerter so they share the same Slack /
    PagerDuty path as event-driven alerts.

    Disabled when settings.REDIS_INVARIANT_INTERVAL_S <= 0.
    """
    interval = settings.REDIS_INVARIANT_INTERVAL_S
    if interval <= 0:
        logger.info("Redis invariant scanner disabled (REDIS_INVARIANT_INTERVAL_S=0)")
        return
    logger.info("Redis invariant scanner started", interval_s=interval)
    while True:
        try:
            violations = await scan_invariants(redis)
            if not violations:
                logger.info("redis_invariants: 0 violations")
            else:
                logger.warning(
                    "redis_invariants: violations found",
                    count=len(violations),
                    samples=[
                        {"key": v.key, "expected": v.expected, "actual": v.actual,
                         "severity": v.severity}
                        for v in violations[:5]
                    ],
                )
                # Route HIGH-severity violations through the alerter. MEDIUM and
                # LOW are logged only — keeps Slack signal-to-noise reasonable.
                for v in violations:
                    if v.severity != "HIGH":
                        continue
                    event = SimpleNamespace(
                        event_type="REDIS_INVARIANT_VIOLATION",
                        profile_id="SYSTEM",
                        timestamp_us=0,
                        message=f"{v.key}: expected {v.expected}, got {v.actual}",
                    )
                    try:
                        await alerter.send_alert(event)
                    except Exception:
                        logger.exception("Failed to dispatch invariant alert", key=v.key)
        except Exception:
            logger.exception("redis_invariants scan raised — continuing loop")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()

    # Initialize Dependencies
    # Stream consumer uses the long-blocking Redis client (no socket_timeout)
    # so idle streams don't trip the default 5s socket_timeout and crash-loop
    # logger.stream_subscriber under the supervisor. redis_instance (default,
    # with socket_timeout) stays for pubsub + invariants + audit writes.
    consumer_redis = RedisClient.get_long_blocking_instance(settings.REDIS_URL).get_connection()
    consumer = StreamConsumer(consumer_redis)
    pubsub = PubSubBroadcaster(redis_instance)
    audit_repo = AuditRepository(timescale_client)

    alerter = Alerter(
        pagerduty_key=settings.PAGERDUTY_API_KEY or None,
        slack_webhook=settings.SLACK_WEBHOOK or None,
    )
    event_pubsub_subscriber = PubSubSubscriber(redis_instance)
    subscriber = EventSubscriber(consumer, pubsub, audit_repo, alerter, event_pubsub_subscriber)

    # Layer 2 heartbeat watcher — detects services whose health_check
    # loop has stopped emitting (silent fail). Uses a dedicated
    # PubSubSubscriber so its subscription is independent of the audit
    # subscriber's lifecycle. See heartbeat_watcher.py for full rationale.
    heartbeat_subscriber = PubSubSubscriber(redis_instance)
    heartbeat_watcher = HeartbeatWatcher(
        subscriber=heartbeat_subscriber,
        publisher=pubsub,
    )
    global _heartbeat_watcher_ref
    _heartbeat_watcher_ref = heartbeat_watcher

    # Background Tasks
    logger.info("Starting Event Subscriber Loops")
    stream_task = supervised_task(subscriber.run_streams, name="logger.stream_subscriber")
    pubsub_task = supervised_task(subscriber.run_pubsub, name="logger.pubsub_subscriber")
    invariants_task = supervised_task(
        lambda: redis_invariants_loop(redis_instance, alerter),
        name="logger.invariants",
    )
    # heartbeat watcher already has internal supervisor; create_task is fine
    heartbeat_sub_task = asyncio.create_task(heartbeat_watcher.run_subscriber())
    heartbeat_scan_task = asyncio.create_task(heartbeat_watcher.run_scanner())

    # Watchdog for the heartbeat watcher itself. If either of its tasks
    # silently exits — the failure mode this entire layer exists to
    # catch — surface it loudly. Mirrors hot_path/main.py done-callback.
    def _on_heartbeat_done(t):
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            import traceback as _tb
            tb = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
            logger.error(
                "heartbeat_watcher_task_crashed",
                task=t.get_name(),
                error=str(exc),
                traceback=tb,
            )

    heartbeat_sub_task.add_done_callback(_on_heartbeat_done)
    heartbeat_scan_task.add_done_callback(_on_heartbeat_done)

    # Stall watchdog over the watcher's own heartbeat. Same pattern as
    # services/hot_path/src/main.py:_processor_stall_watchdog.
    async def _heartbeat_self_watchdog():
        STALL_S = 60.0  # watcher loops bump every event or every check_interval
        dumped = False
        while True:
            await asyncio.sleep(15)
            stalled_for = time.monotonic() - heartbeat_watcher.last_progress_mono
            if stalled_for > STALL_S:
                if not dumped:
                    logger.error(
                        "heartbeat_watcher_self_stall",
                        stalled_for_s=round(stalled_for, 1),
                    )
                    dumped = True
            else:
                dumped = False

    heartbeat_self_watchdog_task = asyncio.create_task(_heartbeat_self_watchdog())

    yield

    # Teardown
    stream_task.cancel()
    pubsub_task.cancel()
    invariants_task.cancel()
    heartbeat_sub_task.cancel()
    heartbeat_scan_task.cancel()
    heartbeat_self_watchdog_task.cancel()
    await asyncio.gather(
        stream_task,
        pubsub_task,
        invariants_task,
        heartbeat_sub_task,
        heartbeat_scan_task,
        heartbeat_self_watchdog_task,
        return_exceptions=True,
    )
    await timescale_client.close()
    logger.info("Logger Agent shutdown safely")

app = FastAPI(title="Logger Agent", lifespan=lifespan)

# Module-level handle so the /heartbeats endpoint can introspect it.
_heartbeat_watcher_ref: HeartbeatWatcher | None = None


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/heartbeats")
def heartbeats():
    """Return per-service seconds-since-last-heartbeat. Useful as a
    diagnostic when a RED alert fires — shows the full set, not just
    the stalled one."""
    if _heartbeat_watcher_ref is None:
        return {"status": "watcher not initialised yet"}
    return _heartbeat_watcher_ref.snapshot()


if __name__ == "__main__":
    uvicorn.run("services.logger.src.main:app", host="0.0.0.0", port=8085)
