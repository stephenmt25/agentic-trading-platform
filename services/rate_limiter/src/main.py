import asyncio
from libs.config import settings
from libs.storage._redis_client import RedisClient
from libs.observability import get_logger, MetricsCollector

logger = get_logger("rate-limiter")

async def main():
    logger.info("Starting Rate Limiter Service")
    redis_client = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    
    try:
        while True:
            # Emits metrics logic
            logger.info("Publishing quota metrics...")
            MetricsCollector.increment_counter("system.heartbeat", tags={"service": "rate-limiter"})
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        logger.info("Shutting down Rate Limiter Service")

if __name__ == "__main__":
    asyncio.run(main())
