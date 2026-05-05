import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
from types import SimpleNamespace

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient, AuditRepository
from libs.messaging import StreamConsumer, PubSubBroadcaster
from libs.observability import get_logger
from libs.observability.redis_invariants import scan as scan_invariants

from .alerter import Alerter
from .event_subscriber import EventSubscriber

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
    consumer = StreamConsumer(redis_instance)
    pubsub = PubSubBroadcaster(redis_instance)
    audit_repo = AuditRepository(timescale_client)

    alerter = Alerter(
        pagerduty_key=settings.PAGERDUTY_API_KEY or None,
        slack_webhook=settings.SLACK_WEBHOOK or None,
    )
    subscriber = EventSubscriber(consumer, pubsub, audit_repo, alerter)

    # Background Tasks
    logger.info("Starting Event Subscriber Loops")
    stream_task = asyncio.create_task(subscriber.run_streams())
    pubsub_task = asyncio.create_task(subscriber.run_pubsub())
    invariants_task = asyncio.create_task(redis_invariants_loop(redis_instance, alerter))

    yield

    # Teardown
    stream_task.cancel()
    pubsub_task.cancel()
    invariants_task.cancel()
    await asyncio.gather(stream_task, pubsub_task, invariants_task, return_exceptions=True)
    await timescale_client.close()
    logger.info("Logger Agent shutdown safely")

app = FastAPI(title="Logger Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.logger.src.main:app", host="0.0.0.0", port=8085)
