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
from .hmm_model import HMMRegimeModel
from .regime_mapper import map_state_to_regime

logger = get_logger("regime-hmm")

CLASSIFY_INTERVAL_S = 300  # 5 minutes
SCORE_TTL_S = 600
HMM_FIT_TIMEOUT_S = 30
# Number of recent points to hold out from training for prediction
HMM_PREDICT_WINDOW = 1


async def classification_loop(redis_client, market_repo: MarketDataRepository, telemetry: TelemetryPublisher):
    """Periodically classify market regime using HMM and write to Redis."""
    symbols = settings.TRADING_SYMBOLS
    models: dict[str, HMMRegimeModel] = {sym: HMMRegimeModel() for sym in symbols}

    while True:
        try:
            for symbol in symbols:
                await telemetry.emit("input_received", {"symbol": symbol, "message_type": "candle_load"}, source_agent="ingestion")
                # Fetch recent 1h candles for regime classification
                candles = await market_repo.get_candles(symbol, "1h", limit=500)
                if not candles:
                    continue

                prices = [float(c["close"]) for c in candles]
                model = models[symbol]

                # Split: train on all but last N points, predict on full series
                train_prices = prices[:-HMM_PREDICT_WINDOW]

                # Re-fit only when model has not been fitted yet
                if not model._is_fitted:
                    models[symbol] = HMMRegimeModel()
                    model = models[symbol]
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(model.fit, train_prices),
                            timeout=HMM_FIT_TIMEOUT_S,
                        )
                    except asyncio.TimeoutError:
                        logger.error("HMM fit timed out", symbol=symbol)
                        continue

                # Predict on the full price series (last point is unseen by training)
                state = model.predict_state(prices)
                if state is not None:
                    regime = map_state_to_regime(model, state)
                    if regime:
                        key = f"agent:regime_hmm:{symbol}"
                        await redis_client.set(
                            key,
                            json.dumps({"regime": regime.value, "state_index": state}),
                            ex=SCORE_TTL_S,
                        )
                        logger.info("HMM regime updated", symbol=symbol, regime=regime.value)
                        await telemetry.emit(
                            "state_update",
                            {"symbol": symbol, "regime": regime.value, "state_index": state},
                            target_agent="hot_path",
                        )

        except Exception as e:
            logger.error("HMM classification loop error", error=str(e))

        await asyncio.sleep(CLASSIFY_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale = TimescaleClient(settings.DATABASE_URL)
    await timescale.init_pool()
    market_repo = MarketDataRepository(timescale)

    telemetry = TelemetryPublisher(redis_instance, "regime_hmm", "regime")
    await telemetry.start_health_loop()

    task = asyncio.create_task(classification_loop(redis_instance, market_repo, telemetry))
    logger.info("Regime HMM Agent started")
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await telemetry.stop()
    await timescale.close()
    logger.info("Regime HMM Agent shutdown")


app = FastAPI(title="Regime HMM Agent", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.regime_hmm.src.main:app", host="0.0.0.0", port=8091)
