import asyncio
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from libs.config import settings
from libs.messaging import PubSubBroadcaster, StreamConsumer, StreamPublisher
from libs.messaging.channels import ORDERS_STREAM
from libs.observability import get_logger
from libs.observability.telemetry import TelemetryPublisher
from libs.storage import (
    AuditRepository,
    OrderRepository,
    PositionRepository,
    RedisClient,
    TimescaleClient,
)
from libs.storage.repositories import ProfileRepository

from .executor import OrderExecutor
from .ledger import OptimisticLedger
from .reconciler import BalanceReconciler

logger = get_logger("execution")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()

    # Initialize Dependencies
    publisher = StreamPublisher(redis_instance)
    consumer = StreamConsumer(redis_instance)

    order_repo = OrderRepository(timescale_client)
    position_repo = PositionRepository(timescale_client)
    audit_repo = AuditRepository(timescale_client)
    profile_repo = ProfileRepository(timescale_client)
    pubsub = PubSubBroadcaster(redis_instance)

    ledger = OptimisticLedger(order_repo)

    telemetry = TelemetryPublisher(redis_instance, "execution", "execution")
    await telemetry.start_health_loop()

    executor = OrderExecutor(
        publisher=publisher,
        consumer=consumer,
        order_repo=order_repo,
        position_repo=position_repo,
        audit_repo=audit_repo,
        ledger=ledger,
        orders_channel=ORDERS_STREAM,
        redis_client=redis_instance,
        telemetry=telemetry,
    )

    # Wired live (PR2): profile_repo lets it iterate active profiles instead of
    # early-returning; pubsub lets a >0.1% drift publish an ALERT_RED to
    # PUBSUB_SYSTEM_ALERTS. No-op for paper profiles (skipped by key_ref).
    reconciler = BalanceReconciler(
        position_repo, profile_repo=profile_repo, pubsub=pubsub
    )

    # Background Tasks
    logger.info("Starting Execution Loop")
    exec_task = asyncio.create_task(executor.run())
    logger.info("Starting Reconciler Cron")
    recon_task = asyncio.create_task(reconciler.run_cron())

    def _on_executor_done(t):
        # executor.run() is `while True` — if the task ever completes, it
        # raised. The task object is held for the app's lifetime, so asyncio
        # never GCs it and never logs the exception: the crash is otherwise
        # completely silent (this exact failure mode was the 2026-05-26
        # overnight bug — 17 APPROVED decisions, 0 fills). Surface it loudly.
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            import traceback as _tb

            tb = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
            logger.error("executor_task_crashed", error=str(exc), traceback=tb)

    exec_task.add_done_callback(_on_executor_done)

    # Stall watchdog. Silent while healthy; if the consume loop stops
    # advancing (a hung await — e.g. Redis socket with no timeout, or any
    # deadlock that stops last_progress_mono from updating), dumps every
    # live asyncio task's suspended stack once per stall episode so the
    # stuck coroutine is diagnosable instead of an invisible freeze.
    async def _executor_stall_watchdog():
        STALL_S = 30.0
        dumped = False
        while True:
            await asyncio.sleep(10)
            if not hasattr(executor, "last_progress_mono"):
                continue  # supervisor hasn't initialised the heartbeat yet
            stalled_for = time.monotonic() - executor.last_progress_mono
            if stalled_for > STALL_S:
                if not dumped:
                    logger.error(
                        "executor_stall_detected", stalled_for_s=round(stalled_for, 1)
                    )
                    for t in asyncio.all_tasks():
                        if t.done():
                            continue
                        frames = t.get_stack()
                        parts = []
                        for fr in reversed(frames[-12:]):
                            fn = fr.f_code.co_filename.replace("\\", "/").split("/")[-1]
                            parts.append(f"{fr.f_code.co_name}@{fn}:{fr.f_lineno}")
                        logger.error(
                            "stall_taskdump",
                            task=t.get_name(),
                            frames=len(frames),
                            stack=" <- ".join(parts),
                        )
                    dumped = True
            else:
                dumped = False

    watchdog_task = asyncio.create_task(_executor_stall_watchdog())

    yield

    # Teardown
    exec_task.cancel()
    recon_task.cancel()
    watchdog_task.cancel()
    await asyncio.gather(exec_task, recon_task, watchdog_task, return_exceptions=True)
    await telemetry.stop()
    await timescale_client.close()
    logger.info("Execution Agent shutdown successfully")


app = FastAPI(title="Execution Agent", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.execution.src.main:app", host="0.0.0.0", port=8083)
