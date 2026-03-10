import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient, OrderRepository, PositionRepository, AuditRepository
from libs.messaging import StreamConsumer, StreamPublisher
from libs.messaging.channels import ORDERS_STREAM
from libs.observability import get_logger

from .ledger import OptimisticLedger
from .executor import OrderExecutor
from .reconciler import BalanceReconciler

logger = get_logger("execution")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()
    
    # Initialize Dependencies
    publisher = StreamPublisher(redis_instance)
    consumer = StreamConsumer(redis_instance)
    
    order_repo = OrderRepository(timescale_client)
    position_repo = PositionRepository(timescale_client)
    audit_repo = AuditRepository(timescale_client)
    
    ledger = OptimisticLedger(order_repo)
    
    executor = OrderExecutor(
        publisher=publisher,
        consumer=consumer,
        order_repo=order_repo,
        position_repo=position_repo,
        audit_repo=audit_repo,
        ledger=ledger,
        orders_channel=ORDERS_STREAM
    )
    
    reconciler = BalanceReconciler(position_repo)

    # Background Tasks
    logger.info("Starting Execution Loop")
    exec_task = asyncio.create_task(executor.run())
    logger.info("Starting Reconciler Cron")
    recon_task = asyncio.create_task(reconciler.run_cron())
    
    yield
    
    # Teardown
    exec_task.cancel()
    recon_task.cancel()
    await asyncio.gather(exec_task, recon_task, return_exceptions=True)
    await timescale_client.close()
    logger.info("Execution Agent shutdown successfully")


app = FastAPI(title="Execution Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.execution.src.main:app", host="0.0.0.0", port=8080)
