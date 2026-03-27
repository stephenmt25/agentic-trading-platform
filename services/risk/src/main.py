from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient
from libs.observability import get_logger

from . import RiskService

logger = get_logger("risk")

_risk_service: RiskService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _risk_service

    redis_conn = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()

    _risk_service = RiskService(
        profile_repo=timescale_client,
        position_repo=timescale_client,
        redis_client=redis_conn,
    )
    logger.info("Risk Service started")

    yield

    await timescale_client.close()
    logger.info("Risk Service shutdown gracefully")


app = FastAPI(title="Risk Service", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/check")
async def check_order(
    profile_id: str,
    symbol: str,
    quantity: float,
    price: float,
    side: str = "BUY",
):
    result = await _risk_service.check_order(
        profile_id=profile_id,
        symbol=symbol,
        quantity=quantity,
        price=price,
        side=side,
    )
    return {"allowed": result.allowed, "reason": result.reason}


if __name__ == "__main__":
    uvicorn.run("services.risk.src.main:app", host="0.0.0.0", port=8093)
