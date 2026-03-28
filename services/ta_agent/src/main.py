import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from libs.config import settings
from libs.storage import RedisClient
from libs.storage.repositories.market_data_repo import MarketDataRepository
from libs.storage._timescale_client import TimescaleClient
from libs.observability import get_logger
from libs.observability.telemetry import TelemetryPublisher
from .confluence import TAConfluenceScorer

logger = get_logger("ta-agent")

SCORE_INTERVAL_S = 60
SCORE_TTL_S = 120
# MACD needs 26 (slow) + 9 (signal) = 35 warmup candles minimum.
# Use 150 to give all indicators ample warmup across timeframes.
CANDLE_LIMIT = 150


async def scoring_loop(redis_client, market_repo: MarketDataRepository, telemetry: TelemetryPublisher):
    """Periodically compute TA confluence scores and write to Redis."""
    symbols = settings.TRADING_SYMBOLS
    scorer_map = {sym: TAConfluenceScorer() for sym in symbols}

    while True:
        try:
            for symbol in symbols:
                await telemetry.emit("input_received", {"symbol": symbol, "message_type": "scoring_cycle"}, source_agent="ingestion")
                scorer = scorer_map[symbol]

                for tf in TAConfluenceScorer.TIMEFRAMES:
                    candles = await market_repo.get_candles(symbol, tf, limit=CANDLE_LIMIT)
                    # Re-initialize scorer for this cycle with fresh data
                    for candle in candles:
                        scorer.update_timeframe(
                            tf,
                            float(candle["high"]),
                            float(candle["low"]),
                            float(candle["close"]),
                        )

                score = scorer.score()
                if score is not None:
                    key = f"agent:ta_score:{symbol}"
                    await redis_client.set(key, json.dumps({"score": score}), ex=SCORE_TTL_S)
                    logger.info("TA score updated", symbol=symbol, score=score)
                    await telemetry.emit(
                        "output_emitted",
                        {"symbol": symbol, "score": score},
                        target_agent="hot_path",
                    )

                # Reset scorer for next cycle
                scorer_map[symbol] = TAConfluenceScorer()

        except Exception as e:
            logger.error("TA scoring loop error", error=str(e))

        # Re-read symbols in case config changes at runtime
        symbols = settings.TRADING_SYMBOLS
        await asyncio.sleep(SCORE_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale = TimescaleClient(settings.DATABASE_URL)
    await timescale.init_pool()
    market_repo = MarketDataRepository(timescale)

    telemetry = TelemetryPublisher(redis_instance, "ta_agent", "scoring")
    await telemetry.start_health_loop()

    task = asyncio.create_task(scoring_loop(redis_instance, market_repo, telemetry))
    logger.info("TA Agent started")
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await telemetry.stop()
    await timescale.close()
    logger.info("TA Agent shutdown")


app = FastAPI(title="TA Multi-Timeframe Agent", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.ta_agent.src.main:app", host="0.0.0.0", port=8090)
