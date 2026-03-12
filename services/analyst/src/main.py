import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient
from libs.observability import get_logger

logger = get_logger("analyst")

# NOTE: Sentiment scoring responsibility has been moved to services/sentiment/
# (Sprint 9.3). The proximity listener that previously triggered sentiment checks
# is now handled by the dedicated Sentiment Agent service.
# This service retains its FastAPI shell for any remaining analyst duties
# (e.g. future research features).

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Analyst Agent started (sentiment delegated to services/sentiment/)")
    yield
    logger.info("Analyst Agent shutdown")


app = FastAPI(title="Analyst Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.analyst.src.main:app", host="0.0.0.0", port=8080)
