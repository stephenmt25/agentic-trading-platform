import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from libs.config import settings
from libs.storage import RedisClient
from libs.observability import get_logger
from .news_client import NewsClient
from .scorer import LLMSentimentScorer

logger = get_logger("sentiment-agent")

SCORE_INTERVAL_S = 300  # 5 minutes
SCORE_TTL_S = 900  # 15 minutes


async def sentiment_loop(redis_client, scorer: LLMSentimentScorer, news_client: NewsClient):
    """Periodically score sentiment for tracked symbols and write to Redis."""
    while True:
        try:
            for symbol in settings.TRADING_SYMBOLS:
                headlines = await news_client.get_headlines(symbol, limit=5)
                result = await scorer.score(symbol, headlines)

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
                logger.info(
                    "Sentiment score updated",
                    symbol=symbol,
                    score=result.score,
                    source=result.source,
                )

        except Exception as e:
            logger.error("Sentiment loop error", error=str(e))

        await asyncio.sleep(SCORE_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    news_client = NewsClient(api_key=settings.NEWS_API_KEY)
    scorer = LLMSentimentScorer(
        llm_key=settings.LLM_API_KEY,
        cache_client=redis_instance,
        cache_ttl=SCORE_TTL_S,
    )

    task = asyncio.create_task(sentiment_loop(redis_instance, scorer, news_client))
    logger.info("Sentiment Agent started")
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    logger.info("Sentiment Agent shutdown")


app = FastAPI(title="Sentiment Agent", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.sentiment.src.main:app", host="0.0.0.0", port=8092)
