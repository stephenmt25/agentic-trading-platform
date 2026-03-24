"""Adversarial Bull/Bear Debate Service.

Runs every 5 minutes per symbol, producing debate_score and debate_confidence
written to Redis key agent:debate:{symbol}.
"""

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from libs.config import settings
from libs.storage import RedisClient
from libs.observability import get_logger
from services.sentiment.src.scorer import create_backend
from .engine import DebateEngine, MarketContext

logger = get_logger("debate-agent")

DEBATE_INTERVAL_S = 300  # 5 minutes
DEBATE_TTL_S = 600       # 10 minutes


async def _get_market_context(redis_client, symbol: str) -> MarketContext:
    """Gather current market context from Redis for debate prompts."""
    pipe = redis_client.pipeline(transaction=False)
    pipe.get(f"agent:ta_score:{symbol}")
    pipe.get(f"agent:sentiment:{symbol}")
    pipe.get(f"regime:{symbol}")
    pipe.get(f"indicators:{symbol}")
    ta_raw, sent_raw, regime_raw, ind_raw = await pipe.execute()

    ta_score = 0.0
    if ta_raw:
        try:
            ta_score = float(json.loads(ta_raw).get("score", 0))
        except Exception:
            pass

    sent_score = 0.0
    if sent_raw:
        try:
            sent_score = float(json.loads(sent_raw).get("score", 0))
        except Exception:
            pass

    regime = "UNKNOWN"
    if regime_raw:
        regime = regime_raw.decode() if isinstance(regime_raw, bytes) else str(regime_raw)

    # Indicator values (may not be cached — use defaults)
    rsi, macd_hist, adx, bb_pct_b, atr, price = 50.0, 0.0, 0.0, 0.5, 0.0, 0.0
    if ind_raw:
        try:
            ind = json.loads(ind_raw)
            rsi = float(ind.get("rsi", 50))
            macd_hist = float(ind.get("macd_histogram", 0))
            adx = float(ind.get("adx", 0))
            bb_pct_b = float(ind.get("bb_pct_b", 0.5))
            atr = float(ind.get("atr", 0))
            price = float(ind.get("price", 0))
        except Exception:
            pass

    return MarketContext(
        symbol=symbol,
        price=price,
        rsi=rsi,
        macd_histogram=macd_hist,
        adx=adx,
        bb_pct_b=bb_pct_b,
        atr=atr,
        regime=regime,
        ta_score=ta_score,
        sentiment_score=sent_score,
    )


async def debate_loop(redis_client, engine: DebateEngine):
    """Periodically run debates for tracked symbols and write results to Redis."""
    while True:
        try:
            for symbol in settings.TRADING_SYMBOLS:
                ctx = await _get_market_context(redis_client, symbol)
                result = await engine.run(ctx)

                key = f"agent:debate:{symbol}"
                await redis_client.set(
                    key,
                    json.dumps({
                        "score": result.score,
                        "confidence": result.confidence,
                        "reasoning": result.reasoning,
                        "num_rounds": len(result.rounds),
                        "latency_ms": result.total_latency_ms,
                    }),
                    ex=DEBATE_TTL_S,
                )
                logger.info(
                    "Debate completed",
                    symbol=symbol,
                    score=round(result.score, 3),
                    confidence=round(result.confidence, 3),
                    latency_ms=result.total_latency_ms,
                )

        except Exception as e:
            logger.error("Debate loop error", error=str(e))

        await asyncio.sleep(DEBATE_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_conn = RedisClient.get_instance(settings.REDIS_URL).get_connection()

    # Reuse the same LLM backend as sentiment (local or cloud)
    backends = create_backend(llm_key=settings.LLM_API_KEY)
    # Use the first available backend for debate
    backend = backends[0] if backends else None

    if backend is None:
        logger.error("No LLM backend available for debate service")
        yield
        return

    engine = DebateEngine(backend, num_rounds=2)

    task = asyncio.create_task(debate_loop(redis_conn, engine))
    logger.info("Debate Agent started", backend_mode=settings.LLM_BACKEND)
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    logger.info("Debate Agent shutdown")


app = FastAPI(title="Debate Agent", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.debate.src.main:app", host="0.0.0.0", port=8096)
