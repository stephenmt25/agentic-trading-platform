import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
import time

from libs.config import settings
from libs.storage import RedisClient
from libs.messaging import PubSubBroadcaster
from libs.messaging.channels import PUBSUB_THRESHOLD_PROXIMITY
from libs.observability import get_logger

from .cache import SentimentCache
from .news_scraper import NewsScraper
from .sentiment_scorer import SentimentScorer

logger = get_logger("analyst")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    pubsub = PubSubBroadcaster(redis_instance)
    
    # Dependencies
    cache = SentimentCache(redis_instance, ttl_s=900) # 15 min TTL
    scraper = NewsScraper(api_key=settings.NEWS_API_KEY)
    scorer = SentimentScorer(cache, scraper, llm_key=settings.LLM_API_KEY)

    async def proximity_listener():
        logger.info(f"Analyst Agent listening to {PUBSUB_THRESHOLD_PROXIMITY}")
        async for channel, message in pubsub.subscribe(PUBSUB_THRESHOLD_PROXIMITY):
            sym = message.get("symbol")
            if not sym:
                continue
                
            # Score
            logger.info(f"Threshold proximity triggered sentiment check for {sym}")
            result = await scorer.score(sym)
            
            # Publish event
            out_event = {
                "symbol": sym,
                "score": result.score,
                "confidence": result.confidence,
                "source": result.source,
                "timestamp_us": int(time.time() * 1000000)
            }
            await pubsub.publish("pubsub:market_sentiment", out_event)
            
    # Loop
    logger.info("Starting Analyst Agent proximity listener loop")
    listener_task = asyncio.create_task(proximity_listener())
    
    yield
    
    # Teardown
    listener_task.cancel()
    await asyncio.gather(listener_task, return_exceptions=True)
    logger.info("Analyst Agent shutdown")


app = FastAPI(title="Analyst Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.analyst.src.main:app", host="0.0.0.0", port=8080)
