import asyncio
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

from libs.config import settings
from libs.exchange import get_adapter
from libs.messaging import StreamPublisher, PubSubBroadcaster, MARKET_DATA_STREAM, PUBSUB_PRICE_TICKS
from libs.storage import RedisClient, TimescaleClient, MarketDataRepository
from libs.core.schemas import MarketTickEvent
from libs.observability import get_logger, timer
from libs.observability.telemetry import TelemetryPublisher

from .ws_manager import WebSocketManager
from .health import create_health_app
from .data_router import DataRouter

logger = get_logger("ingestion")

redis_client = RedisClient.get_instance(settings.REDIS_URL).get_connection()
timescale_client = TimescaleClient(settings.DATABASE_URL)

stream_pub = StreamPublisher(redis_client)
pubsub_broadcaster = PubSubBroadcaster(redis_client)
telemetry = TelemetryPublisher(redis_client, "ingestion", "market_data")

market_repo = MarketDataRepository(timescale_client)
data_router = DataRouter(market_repo)

symbols_to_track = ["BTC/USDT", "ETH/USDT"]

adapters = [
    get_adapter("BINANCE", testnet=settings.BINANCE_TESTNET),
    # get_adapter("COINBASE", testnet=settings.COINBASE_SANDBOX) # Removed to avoid duplications in simple demo
]
ws_manager = WebSocketManager(adapters, symbols_to_track)

async def handle_tick(tick):
    await telemetry.emit("input_received", {"symbol": tick.symbol, "exchange": tick.exchange, "message_type": "exchange_tick"}, source_agent="external")

    # Hot-Path publish
    event = MarketTickEvent(
        symbol=tick.symbol,
        exchange=tick.exchange,
        price=tick.price,
        volume=tick.volume,
        timestamp_us=tick.timestamp,
        source_service="ingestion"
    )
    
    with timer("ingestion.publish"):
        # Publish to both Stream and Pub/Sub Concurrently
        await asyncio.gather(
            stream_pub.publish(MARKET_DATA_STREAM, event),
            pubsub_broadcaster.publish(PUBSUB_PRICE_TICKS, event)
        )
        
    await telemetry.emit(
        "output_emitted",
        {"symbol": tick.symbol, "price": str(tick.price), "exchange": tick.exchange},
        target_agent="hot_path",
    )

    # Async background map to router without blocking event loop tick path
    data_router.aggregate_tick(tick)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing TimescaleDB pool...")
    await timescale_client.init_pool()

    logger.info("Starting Ingestion Agent...")
    await ws_manager.start(handle_tick)
    await telemetry.start_health_loop()
    yield
    # Shutdown
    logger.info("Shutting down Ingestion Agent...")
    await telemetry.stop()
    await ws_manager.stop()
    await data_router.force_flush()
    await timescale_client.close()

app = create_health_app(ws_manager)
app.router.lifespan_context = lifespan

if __name__ == "__main__":
    uvicorn.run("services.ingestion.src.main:app", host="0.0.0.0", port=8080, log_level="error")
