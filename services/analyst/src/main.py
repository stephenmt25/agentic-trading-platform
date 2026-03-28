import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient
from libs.observability import get_logger
from libs.observability.telemetry import TelemetryPublisher
from libs.core.agent_registry import AgentPerformanceTracker

logger = get_logger("analyst")

WEIGHT_RECOMPUTE_INTERVAL_S = 300  # 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_conn = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    tracker = AgentPerformanceTracker(redis_conn)

    telemetry = TelemetryPublisher(redis_conn, "analyst", "meta_learning")
    await telemetry.start_health_loop()

    async def weight_recompute_loop():
        """Periodically recompute agent weights from closed position outcomes."""
        while True:
            try:
                for symbol in settings.TRADING_SYMBOLS:
                    await telemetry.emit("input_received", {"symbol": symbol, "message_type": "outcome_read"}, source_agent="pnl")
                    await tracker.recompute_weights(symbol)
                    await telemetry.emit(
                        "output_emitted",
                        {"symbol": symbol, "weights": {}},
                        target_agent="hot_path",
                    )
                logger.info(
                    "Agent weights recomputed",
                    symbols=settings.TRADING_SYMBOLS,
                )
            except Exception as e:
                logger.error("Weight recomputation failed", error=str(e))
            await asyncio.sleep(WEIGHT_RECOMPUTE_INTERVAL_S)

    logger.info("Analyst Agent started — weight computation engine")
    weight_task = asyncio.create_task(weight_recompute_loop())

    yield

    weight_task.cancel()
    await asyncio.gather(weight_task, return_exceptions=True)
    await telemetry.stop()
    logger.info("Analyst Agent shutdown")


app = FastAPI(title="Analyst Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.analyst.src.main:app", host="0.0.0.0", port=8087)
