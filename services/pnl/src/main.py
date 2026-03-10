import asyncio
from fastapi import FastAPI
import uvicorn
import httpx
from datetime import datetime
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient, PositionRepository, PnlRepository
from libs.messaging import PubSubBroadcaster
from libs.messaging.channels import PUBSUB_PRICE_TICKS
from libs.observability import get_logger

from .calculator import PnLCalculator
from .publisher import PnLPublisher
from services.tax.src.us_tax import TaxEstimate

logger = get_logger("pnl")

# Cached map in memory for active positions to avoid constant db roundtrips
# In reality you would reload this or track position creation events
# Mapping {symbol: [Positions]}
active_positions_cache = {}

async def hydrate_positions(position_repo: PositionRepository):
    # Simplified query
    all_open = await position_repo.get_open_positions()
    active_positions_cache.clear()
    for pos in all_open:
        sym = pos.symbol
        if sym not in active_positions_cache:
            active_positions_cache[sym] = []
        active_positions_cache[sym].append(pos)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()
    
    # Dependencies
    pubsub = PubSubBroadcaster(redis_instance)
    position_repo = PositionRepository(timescale_client)
    pnl_repo = PnlRepository(timescale_client)
    publisher = PnLPublisher(redis_instance, pubsub, pnl_repo)
    
    await hydrate_positions(position_repo)

    async def pnl_tick_processor():
        async for channel, tick_data in pubsub.subscribe(PUBSUB_PRICE_TICKS):
            sym = tick_data.get("symbol")
            cp = float(tick_data.get("price", 0.0))
            
            # Find open positions for symbol
            positions = active_positions_cache.get(sym, [])
            for pos in positions:
                # Precalculate Tax: Holding duration
                diff_days = (datetime.utcnow() - pos.opened_at).days
                tax = TaxEstimate(0.0, 0.0, "short-term")
                
                # We can call the local Tax calculator explicitly without network overhead since we loaded it
                snapshot = PnLCalculator.calculate(
                    position=pos,
                    current_price=cp,
                    taker_rate=0.001, # 0.1% hardcoded for binance taker
                    tax_result=tax
                )
                await publisher.publish_update(pos.profile_id, snapshot)
                
    # Loop
    logger.info("Starting PNL PubSub listener loop")
    listener_task = asyncio.create_task(pnl_tick_processor())
    
    yield
    
    # Teardown
    listener_task.cancel()
    await asyncio.gather(listener_task, return_exceptions=True)
    await timescale_client.close()
    logger.info("PnL Agent shutdown")

app = FastAPI(title="PnL Service", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.pnl.src.main:app", host="0.0.0.0", port=8084)
