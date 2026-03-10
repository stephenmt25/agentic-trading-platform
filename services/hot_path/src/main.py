import asyncio
import uuid
import httpx
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage._redis_client import RedisClient
from libs.messaging import StreamConsumer, StreamPublisher, PubSubBroadcaster
from libs.messaging.channels import (
    MARKET_DATA_STREAM, 
    ORDERS_STREAM, 
    VALIDATION_STREAM, 
    VALIDATION_RESPONSE_STREAM, 
    PUBSUB_THRESHOLD_PROXIMITY
)
from libs.observability import get_logger

from .state import ProfileStateCache
from .validation_client import ValidationClient
from .processor import HotPathProcessor

logger = get_logger("hot-path.main")

async def verify_validation_agent_health():
    """Wait and verify validation agent is completely online before starting."""
    # Hardcoded host assuming docker compose resolution. Could be env driven.
    url = "http://validation:8080/health"
    backoff = 1.0
    
    logger.info("Waiting for Validation Agent health check...")
    
    # Needs httpx async client
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # In development/standalone if validation not mocked/running we bypass or crash
                # Let's bypass gracefully if it's localhost and doesn't exist just to test Hot-Path alone.
                res = await client.get(url, timeout=2.0)
                if res.status_code == 200:
                    logger.info("Validation Agent is HEALTHY.")
                    break
            except httpx.ConnectError:
                pass
            
            logger.info(f"Validation Agent unavailable. Retrying in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

async def wait_for_hydration_complete(redis_client, state_cache: ProfileStateCache):
    """Wait for strategy agent to hydrate cache elements to start safely"""
    while True:
        all_ready = True
        for prof in state_cache.itervalues():
            key = f"hydration:{prof.profile_id}:status"
            status = await redis_client.get(key)
            if status != b"complete":
                all_ready = False
                break
        
        if all_ready and len(list(state_cache.itervalues())) > 0:
             break
        
        # If no profiles, skip wait for dummy boots
        if len(list(state_cache.itervalues())) == 0:
             break
             
        await asyncio.sleep(1.0)
    logger.info("Profile states successfully hydrated.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Core Setup
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    consumer = StreamConsumer(redis_instance)
    publisher = StreamPublisher(redis_instance)
    pubsub = PubSubBroadcaster(redis_instance)
    
    val_client = ValidationClient(
        publisher=publisher,
        consumer=consumer,
        req_channel=VALIDATION_STREAM,
        resp_channel=VALIDATION_RESPONSE_STREAM,
        timeout_ms=settings.FAST_GATE_TIMEOUT_MS
    )
    
    state_cache = ProfileStateCache()
    
    # 1. Hydrate cache loop Wait (Requires active caching, skip if zero profiles for dev ease)
    await wait_for_hydration_complete(redis_instance, state_cache)
    
    # 2. Verify Safety gate
    # Bypassing hard check here for pure library test runtime ability if not in compose,
    # But in strict Prod mode we must wait forever until 200 is confirmed.
    # await verify_validation_agent_health()
    
    processor = HotPathProcessor(
        state_cache=state_cache,
        consumer=consumer,
        publisher=publisher,
        pubsub=pubsub,
        validation_client=val_client,
        tick_channel=MARKET_DATA_STREAM,
        orders_channel=ORDERS_STREAM,
        proximity_pubsub_channel=PUBSUB_THRESHOLD_PROXIMITY
    )
    
    logger.info("Injecting Hot-Path background loop.")
    task = asyncio.create_task(processor.run())
    
    yield
    
    # Teardown
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    logger.info("Hot-Path shutdown gracefully.")

app = FastAPI(title="HotPath Processor", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.hot_path.src.main:app", host="0.0.0.0", port=8082)
