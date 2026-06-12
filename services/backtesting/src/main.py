import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from libs.config import settings
from libs.messaging import StreamConsumer, StreamPublisher
from libs.observability import get_logger, supervised_task
from libs.storage import MarketDataRepository, RedisClient, TimescaleClient
from libs.storage.repositories.backtest_repo import BacktestRepository

from .data_loader import BacktestDataLoader
from .job_runner import JobRunner

logger = get_logger("backtesting")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    # Job-runner xreadgroup uses block=5000 — right at the default pool's
    # socket_timeout boundary, which produces spurious TimeoutErrors. Give
    # the worker its own no-socket-timeout pool.
    job_redis = RedisClient.get_long_blocking_instance(
        settings.REDIS_URL
    ).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()

    # Dependencies
    consumer = StreamConsumer(redis_instance)
    publisher = StreamPublisher(redis_instance)
    market_repo = MarketDataRepository(timescale_client)
    backtest_repo = BacktestRepository(timescale_client)

    loader = BacktestDataLoader(market_repo)
    runner = JobRunner(
        consumer,
        publisher,
        loader,
        backtest_repo=backtest_repo,
        redis_client=job_redis,
    )

    # Loop
    logger.info("Starting Backtest Job Worker")
    worker_task = supervised_task(runner.run, name="backtesting.job_runner")

    yield

    # Teardown
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)
    await timescale_client.close()
    logger.info("Backtesting Agent shutdown")


app = FastAPI(title="Backtesting Agent", lifespan=lifespan)

# NOTE (2026-06-13, ruling D-B): the service-local POST /backtest/sweep was
# RETIRED — it was unauthenticated, took float slippage_pct, and supported
# neither risk_limits nor risk_limits_grid. The gateway's POST /backtest
# (auth'd, Decimal, grids via walk_forward) is the sole entry point; run_sweep
# remains reachable only as walk_forward's per-window train fit.


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.backtesting.src.main:app", host="0.0.0.0", port=8086)
