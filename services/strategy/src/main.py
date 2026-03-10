import asyncio
import json
from libs.config import settings
from libs.storage import ProfileRepository, MarketDataRepository, RedisClient, TimescaleClient
from libs.observability import get_logger

from .hydrator import IndicatorHydrator
from .rule_validator import RuleValidator
from .compiler import RuleCompiler

logger = get_logger("strategy")

redis_client = RedisClient.get_instance(settings.REDIS_URL).get_connection()
timescale_client = TimescaleClient(settings.DATABASE_URL)

profile_repo = ProfileRepository(timescale_client)
market_repo = MarketDataRepository(timescale_client)

hydrator = IndicatorHydrator(profile_repo, market_repo, redis_client)

async def hydration_task():
    logger.info("Initializing DB connections for hydrator")
    await timescale_client.init_pool()
    await hydrator.hydrate_all_profiles()

async def main():
    logger.info("Starting Strategy Agent Service")
    await hydration_task()
    
    # Normally this service would also listen to profile updates from the API gateway or database 
    # and trigger validations and compilations continuously, pushing compiled logic to Redis cache
    # For Phase 1, we start hydrating and we enter a loop tracking profiles or checking updates
    
    try:
        while True:
            # e.g., consume "profile_updates" stream 
            # In simple version, wait on some signal or loop
            await asyncio.sleep(60)
            
    except asyncio.CancelledError:
        logger.info("Shutting down Strategy Agent")
    finally:
        await timescale_client.close()

if __name__ == "__main__":
    asyncio.run(main())
