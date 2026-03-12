import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient, MarketDataRepository
from libs.storage.repositories.backtest_repo import BacktestRepository
from libs.messaging import StreamConsumer, StreamPublisher
from libs.observability import get_logger

from .simulator import TradingSimulator
from .data_loader import BacktestDataLoader
from .job_runner import JobRunner

logger = get_logger("backtesting")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()

    # Dependencies
    consumer = StreamConsumer(redis_instance)
    publisher = StreamPublisher(redis_instance)
    market_repo = MarketDataRepository(timescale_client)
    backtest_repo = BacktestRepository(timescale_client)

    loader = BacktestDataLoader(market_repo)
    runner = JobRunner(
        consumer, publisher, loader,
        backtest_repo=backtest_repo,
        redis_client=redis_instance,
    )

    # Loop
    logger.info("Starting Backtest Job Worker")
    worker_task = asyncio.create_task(runner.run())

    yield

    # Teardown
    worker_task.cancel()
    await asyncio.gather(worker_task, return_exceptions=True)
    await timescale_client.close()
    logger.info("Backtesting Agent shutdown")


app = FastAPI(title="Backtesting Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.backtesting.src.main:app", host="0.0.0.0", port=8086)
