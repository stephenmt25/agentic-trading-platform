import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from decimal import Decimal

from libs.config import settings
from libs.storage import RedisClient
from libs.storage._timescale_client import TimescaleClient
from libs.storage.repositories.agent_score_repo import AgentScoreRepository
from libs.observability import get_logger
from libs.observability.telemetry import TelemetryPublisher
from .news_client import NewsClient
from .scorer import LLMSentimentScorer, create_backend

logger = get_logger("sentiment-agent")

SCORE_INTERVAL_S = 300  # 5 minutes
SCORE_TTL_S = 900  # 15 minutes


async def sentiment_loop(redis_client, scorer: LLMSentimentScorer, news_client: NewsClient, telemetry: TelemetryPublisher, score_repo: AgentScoreRepository = None):
    """Periodically score sentiment for tracked symbols and write to Redis."""
    while True:
        try:
            for symbol in settings.TRADING_SYMBOLS:
                await telemetry.emit("input_received", {"symbol": symbol, "message_type": "headline_fetch"}, source_agent="external")
                headlines = await news_client.get_headlines(symbol, limit=5)
                result = await scorer.score(symbol, headlines)

                # Skip the agent:sentiment:{symbol} Redis write on LLM error
                # or no-headlines fallback. The TimescaleDB persist below
                # still captures the failure for charting/audit, but the
                # meta-learning loop downstream (executor, EWMA tracker)
                # treats absent-key as "no signal" rather than a fake
                # bearish/neutral vote.
                if result.source not in ("llm_error", "fallback"):
                    key = f"agent:sentiment:{symbol}"
                    await redis_client.set(
                        key,
                        json.dumps({
                            "score": result.score,
                            "confidence": result.confidence,
                            "source": result.source,
                        }),
                        ex=SCORE_TTL_S,
                    )
                else:
                    logger.warning(
                        "Sentiment unhealthy — skipping agent:sentiment Redis write",
                        symbol=symbol,
                        source=result.source,
                    )

                # Persist to TimescaleDB for charting overlays — always, so
                # the dashboard can show "tried, failed" as well as success.
                if score_repo:
                    try:
                        await score_repo.write_score(
                            symbol, "sentiment",
                            Decimal(str(result.score)),
                            confidence=Decimal(str(result.confidence)),
                            metadata={"source": result.source},
                        )
                    except Exception as pe:
                        logger.warning("Failed to persist sentiment score", error=str(pe))
                logger.info(
                    "Sentiment score updated",
                    symbol=symbol,
                    score=result.score,
                    source=result.source,
                )
                await telemetry.emit(
                    "output_emitted",
                    {"symbol": symbol, "score": result.score, "confidence": result.confidence},
                    target_agent="hot_path",
                )

        except Exception as e:
            logger.error("Sentiment loop error", error=str(e))

        await asyncio.sleep(SCORE_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale = TimescaleClient(settings.DATABASE_URL)
    await timescale.init_pool()
    score_repo = AgentScoreRepository(timescale)
    news_client = NewsClient(api_key=settings.NEWS_API_KEY)
    backends = create_backend(llm_key=settings.LLM_API_KEY)
    scorer = LLMSentimentScorer(
        llm_key=settings.LLM_API_KEY,
        cache_client=redis_instance,
        cache_ttl=SCORE_TTL_S,
        backends=backends,
    )
    logger.info("Sentiment scorer initialized", backend_mode=settings.LLM_BACKEND,
                num_backends=len(backends))

    telemetry = TelemetryPublisher(redis_instance, "sentiment", "sentiment")
    await telemetry.start_health_loop()

    task = asyncio.create_task(sentiment_loop(redis_instance, scorer, news_client, telemetry, score_repo))
    logger.info("Sentiment Agent started")
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await telemetry.stop()
    await timescale.close()
    logger.info("Sentiment Agent shutdown")


app = FastAPI(title="Sentiment Agent", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.sentiment.src.main:app", host="0.0.0.0", port=8092)
