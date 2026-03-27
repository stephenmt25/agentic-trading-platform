import asyncio
import json
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage._redis_client import RedisClient
from libs.observability import get_logger, MetricsCollector
from .quota_config import EXCHANGE_QUOTAS

logger = get_logger("rate-limiter")


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    app.state.redis = redis_client

    async def metrics_loop():
        """Publish quota usage metrics every 30 seconds."""
        while True:
            try:
                for exchange, quota in EXCHANGE_QUOTAS.items():
                    # Count active keys for this exchange
                    cursor = b"0"
                    total_keys = 0
                    pattern = f"rate_limit:{exchange.lower()}:*"
                    while True:
                        cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                        total_keys += len(keys)
                        if cursor == 0 or cursor == b"0":
                            break

                    MetricsCollector.increment_counter(
                        "rate_limiter.active_profiles",
                        tags={"exchange": exchange, "count": str(total_keys)},
                    )

                MetricsCollector.increment_counter("system.heartbeat", tags={"service": "rate-limiter"})
            except Exception as e:
                logger.error("Metrics loop error", error=str(e))

            await asyncio.sleep(30)

    logger.info("Starting Rate Limiter Service")
    metrics_task = asyncio.create_task(metrics_loop())

    yield

    metrics_task.cancel()
    await asyncio.gather(metrics_task, return_exceptions=True)
    logger.info("Rate Limiter Service shutdown")


app = FastAPI(title="Rate Limiter Service", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/quotas")
async def get_quotas():
    """Return configured exchange rate limits."""
    return {
        exchange: {"limit": q.limit, "window_sec": q.window_sec}
        for exchange, q in EXCHANGE_QUOTAS.items()
    }


if __name__ == "__main__":
    uvicorn.run("services.rate_limiter.src.main:app", host="0.0.0.0", port=8094)
