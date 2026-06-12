import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal

import uvicorn
from fastapi import FastAPI

from libs.config import settings
from libs.core.schemas import RiskCheckResponse
from libs.observability import get_logger
from libs.observability.telemetry import TelemetryPublisher
from libs.storage import PositionRepository, RedisClient, TimescaleClient
from libs.storage.repositories import ProfileRepository

from . import RiskService
from .portfolio import PortfolioRiskAggregator

logger = get_logger("risk")

_risk_service: RiskService | None = None
_telemetry: TelemetryPublisher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _risk_service, _telemetry

    redis_conn = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()

    # Use real repositories — previously the raw TimescaleClient was passed as
    # both repos, so get_profile/get_open_positions raised AttributeError (caught
    # + logged), silently skipping the profile-allocation and concentration
    # checks. Fixed here so those checks — and the PR4 portfolio check — run.
    position_repo = PositionRepository(timescale_client)
    profile_repo = ProfileRepository(timescale_client)

    _risk_service = RiskService(
        profile_repo=profile_repo,
        position_repo=position_repo,
        redis_client=redis_conn,
    )

    # PR4: portfolio-exposure aggregator — snapshots cross-profile gross + per-
    # cluster exposure to Redis for the hot-path gate to read.
    aggregator = PortfolioRiskAggregator(position_repo, redis_conn)
    aggregator_task = asyncio.create_task(aggregator.run_loop())

    _telemetry = TelemetryPublisher(redis_conn, "risk", "risk")
    await _telemetry.start_health_loop()

    logger.info("Risk Service started")

    yield

    aggregator_task.cancel()
    await asyncio.gather(aggregator_task, return_exceptions=True)
    await _telemetry.stop()
    await timescale_client.close()
    logger.info("Risk Service shutdown gracefully")


app = FastAPI(title="Risk Service", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/check", response_model=RiskCheckResponse)
async def check_order(
    profile_id: str,
    symbol: str,
    quantity: float,
    price: float,
    side: str = "BUY",
):
    if _telemetry:
        await _telemetry.emit(
            "input_received",
            {"message_type": "risk_check_request"},
            source_agent="hot_path",
        )
    # _risk_service is initialised in lifespan() before any request is served;
    # typing-only ignore (a None-raise here would change runtime behavior).
    result = await _risk_service.check_order(  # type: ignore[union-attr]
        profile_id=profile_id,
        symbol=symbol,
        # JSON/query boundary: FastAPI parses these as float; check_order
        # re-normalises via Decimal(str(...)) so this conversion is
        # behavior-identical — it just satisfies the Decimal contract.
        quantity=Decimal(str(quantity)),
        price=Decimal(str(price)),
        side=side,
    )
    if _telemetry:
        await _telemetry.emit(
            "output_emitted",
            {"passed": result.allowed, "reason": result.reason, "symbol": symbol},
            source_agent="hot_path",
        )
    return {"allowed": result.allowed, "reason": result.reason}


if __name__ == "__main__":
    uvicorn.run("services.risk.src.main:app", host="0.0.0.0", port=8093)
