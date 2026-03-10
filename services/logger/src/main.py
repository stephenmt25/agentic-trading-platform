import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient, AuditRepository
from libs.messaging import StreamConsumer, PubSubBroadcaster
from libs.observability import get_logger

from .alerter import Alerter
from .event_subscriber import EventSubscriber

logger = get_logger("logger")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()
    
    # Initialize Dependencies
    consumer = StreamConsumer(redis_instance)
    pubsub = PubSubBroadcaster(redis_instance)
    audit_repo = AuditRepository(timescale_client)
    
    alerter = Alerter(pagerduty_key=None, slack_webhook=None)
    subscriber = EventSubscriber(consumer, pubsub, audit_repo, alerter)

    # Background Tasks
    logger.info("Starting Event Subscriber Loops")
    stream_task = asyncio.create_task(subscriber.run_streams())
    pubsub_task = asyncio.create_task(subscriber.run_pubsub())
    
    yield
    
    # Teardown
    stream_task.cancel()
    pubsub_task.cancel()
    await asyncio.gather(stream_task, pubsub_task, return_exceptions=True)
    await timescale_client.close()
    logger.info("Logger Agent shutdown safely")

app = FastAPI(title="Logger Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.logger.src.main:app", host="0.0.0.0", port=8085)
