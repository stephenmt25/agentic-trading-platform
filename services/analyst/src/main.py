import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient
from libs.storage._timescale_client import TimescaleClient
from libs.storage.repositories.decision_repo import DecisionRepository
from libs.storage.repositories.gate_efficacy_repo import GateEfficacyRepository
from libs.storage.repositories.market_data_repo import MarketDataRepository
from libs.storage.repositories.profile_repo import ProfileRepository
from libs.storage.repositories.weight_history_repo import WeightHistoryRepository
from libs.observability import get_logger
from libs.observability.telemetry import TelemetryPublisher
from libs.core.agent_registry import (
    AgentPerformanceTracker,
    AGENT_DEFAULTS,
    TRACKER_KEY,
    WEIGHTS_KEY,
    _decode_hash,
)
from .insight_engine import insight_engine_loop

logger = get_logger("analyst")

WEIGHT_RECOMPUTE_INTERVAL_S = 300  # 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_conn = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale = TimescaleClient(settings.DATABASE_URL)
    await timescale.init_pool()
    weight_repo = WeightHistoryRepository(timescale)
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

                    # Persist weight snapshot to TimescaleDB for evolution charts
                    try:
                        snapshot = {}
                        for agent_name in AGENT_DEFAULTS:
                            tk = TRACKER_KEY.format(symbol=symbol, agent=agent_name)
                            tr = _decode_hash(await redis_conn.hgetall(tk))
                            wk = WEIGHTS_KEY.format(symbol=symbol)
                            w_raw = await redis_conn.hget(wk, agent_name)
                            snapshot[agent_name] = {
                                "weight": float(w_raw) if w_raw else AGENT_DEFAULTS[agent_name],
                                "ewma": float(tr.get("ewma_accuracy", 0)),
                                "samples": int(tr.get("sample_count", 0)),
                            }
                        await weight_repo.write_weights(symbol, snapshot)
                    except Exception as pe:
                        logger.warning("Failed to persist weight history", error=str(pe))

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

    profile_repo = ProfileRepository(timescale)
    decision_repo = DecisionRepository(timescale)
    market_repo = MarketDataRepository(timescale)
    gate_repo = GateEfficacyRepository(timescale)

    logger.info("Analyst Agent started — weight computation + insight engine")
    weight_task = asyncio.create_task(weight_recompute_loop())
    insight_task = asyncio.create_task(
        insight_engine_loop(profile_repo, decision_repo, market_repo, gate_repo)
    )

    yield

    weight_task.cancel()
    insight_task.cancel()
    await asyncio.gather(weight_task, insight_task, return_exceptions=True)
    await telemetry.stop()
    await timescale.close()
    logger.info("Analyst Agent shutdown")


app = FastAPI(title="Analyst Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.analyst.src.main:app", host="0.0.0.0", port=8087)
