import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient, MarketDataRepository, ProfileRepository, ValidationRepository, PnlRepository
from libs.messaging import StreamConsumer, StreamPublisher, PubSubBroadcaster
from libs.messaging.channels import VALIDATION_STREAM
from libs.observability import get_logger

from .check_1_strategy import StrategyRecheck
from .check_6_risk_level import RiskLevelRecheck
from .fast_gate import FastGateHandler

from .check_2_hallucination import HallucinationCheck
from .check_3_bias import BiasCheck
from .check_4_drift import DriftCheck
from .check_5_escalation import EscalationCheck
from .async_audit import AsyncAuditHandler
from .learning_loop import LearningLoop

logger = get_logger("validation")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()
    
    # Initialize Dependencies
    publisher = StreamPublisher(redis_instance)
    consumer = StreamConsumer(redis_instance)
    pubsub = PubSubBroadcaster(redis_instance)
    
    market_repo = MarketDataRepository(timescale_client)
    profile_repo = ProfileRepository(timescale_client)
    validation_repo = ValidationRepository(timescale_client)
    pnl_repo = PnlRepository(timescale_client)
    
    # Fast Gate
    check1 = StrategyRecheck(market_repo, redis_instance)
    check6 = RiskLevelRecheck(profile_repo)
    fast_gate = FastGateHandler(check1, check6)
    
    # Async Audit
    check2 = HallucinationCheck(validation_repo, market_repo)
    check3 = BiasCheck()
    check4 = DriftCheck(pnl_repo)
    check5 = EscalationCheck(validation_repo, pubsub)
    async_auditor = AsyncAuditHandler(consumer, validation_repo, check2, check3, check4, check5, VALIDATION_STREAM)
    
    learning_loop = LearningLoop(validation_repo, publisher)

    # Note: FastGate typically responds via streams matching request IDs, handled inside hot_path request block 
    # To implement exactly, FastGate would consume VALIDATION_STREAM in a loop natively here and publish 
    # to VALIDATION_RESPONSE_STREAM. In this mockup, we only start the async auditor loop.
    # In production, FastGate is a separate high-priority loop. Let's add it basic:
    
    async def fast_gate_loop():
        # High priority loop
        g_name = "fastgate_group"
        while True:
            events = await consumer.consume(VALIDATION_STREAM, g_name, "gate_1", count=100, block_ms=5)
            for msg_id, ev in events:
                if ev:
                    resp = await fast_gate.handle(ev)
                    await publisher.publish("stream:validation_responses", resp)
                await consumer.ack(VALIDATION_STREAM, g_name, [msg_id])

    # Start Tasks
    logger.info("Starting FastGate & Auditor Loops")
    gate_task = asyncio.create_task(fast_gate_loop())
    audit_task = asyncio.create_task(async_auditor.run())
    learn_task = asyncio.create_task(learning_loop.run_hourly_scan())
    
    yield
    
    # Teardown
    gate_task.cancel()
    audit_task.cancel()
    learn_task.cancel()
    await asyncio.gather(gate_task, audit_task, learn_task, return_exceptions=True)
    await timescale_client.close()
    logger.info("Validation Agent shutdown gracefully")

app = FastAPI(title="Validation Agent", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.validation.src.main:app", host="0.0.0.0", port=8080)
