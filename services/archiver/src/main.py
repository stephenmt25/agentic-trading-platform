import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient
from libs.observability import get_logger

from .migrator import DataMigrator

logger = get_logger("archiver")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()
    
    migrator = DataMigrator(redis_instance, timescale_client, gcs_bucket=settings.GCS_BUCKET_NAME)

    async def daily_cron():
        # In a real system you would use a scheduler like APScheduler or celery
        # Here we loop with a daily interval roughly simulating the logic 
        # or execute immediately for testing
        while True:
            await migrator.run_migration()
            await asyncio.sleep(86400) # 24h
            
    # Loop
    logger.info("Starting Archiver Daily Task")
    cron_task = asyncio.create_task(daily_cron())
    
    yield
    
    # Teardown
    cron_task.cancel()
    await asyncio.gather(cron_task, return_exceptions=True)
    await timescale_client.close()
    logger.info("Archiver Agent shutdown")


app = FastAPI(title="Archiver Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.archiver.src.main:app", host="0.0.0.0", port=8080)
