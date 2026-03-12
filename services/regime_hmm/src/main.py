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
from .hmm_model import HMMRegimeModel
from .regime_mapper import map_state_to_regime

logger = get_logger("regime-hmm")

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
CLASSIFY_INTERVAL_S = 300  # 5 minutes
SCORE_TTL_S = 600


async def classification_loop(redis_client, market_repo: MarketDataRepository):
    """Periodically classify market regime using HMM and write to Redis."""
    models = {sym: HMMRegimeModel() for sym in SYMBOLS}

    while True:
        try:
            for symbol in SYMBOLS:
                # Fetch recent 1h candles for regime classification
                candles = await market_repo.get_candles(symbol, "1h", limit=500)
                if not candles:
                    continue

                prices = [float(c["close"]) for c in candles]
                model = models[symbol]

                # Re-fit periodically with latest data
                if not model._is_fitted or True:  # Always re-fit for freshness
                    models[symbol] = HMMRegimeModel()
                    model = models[symbol]
                    model.fit(prices)

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

        except Exception as e:
            logger.error("HMM classification loop error", error=str(e))

        await asyncio.sleep(CLASSIFY_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale = TimescaleClient(settings.DATABASE_URL)
    await timescale.init_pool()
    market_repo = MarketDataRepository(timescale)

    task = asyncio.create_task(classification_loop(redis_instance, market_repo))
    logger.info("Regime HMM Agent started")
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await timescale.close()
    logger.info("Regime HMM Agent shutdown")


app = FastAPI(title="Regime HMM Agent", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.regime_hmm.src.main:app", host="0.0.0.0", port=8091)
