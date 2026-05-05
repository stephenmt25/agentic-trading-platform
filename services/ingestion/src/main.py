import asyncio
from contextlib import asynccontextmanager

import ccxt
import uvicorn
from fastapi import FastAPI

from libs.config import settings
from libs.core.schemas import MarketTickEvent
from libs.exchange import get_adapter
from libs.exchange.backfill import fill_gaps
from libs.messaging import (
    MARKET_DATA_STREAM,
    PUBSUB_PRICE_TICKS,
    PubSubBroadcaster,
    StreamPublisher,
)
from libs.observability import get_logger, timer
from libs.observability.telemetry import TelemetryPublisher
from libs.storage import MarketDataRepository, RedisClient, TimescaleClient

from .candle_aggregator import CandleAggregator
from .health import create_health_app
from .ws_manager import WebSocketManager

logger = get_logger("ingestion")

redis_client = RedisClient.get_instance(settings.REDIS_URL).get_connection()
timescale_client = TimescaleClient(settings.DATABASE_URL)

stream_pub = StreamPublisher(redis_client)
pubsub_broadcaster = PubSubBroadcaster(redis_client)
telemetry = TelemetryPublisher(redis_client, "ingestion", "market_data")

market_repo = MarketDataRepository(timescale_client)

# Shared sync ccxt REST client — used by both startup backfill and
# CandleAggregator's rollover fetches. Binance public klines don't need auth.
# Always mainnet: testnet mirrors mainnet prices but has ~10% of mainnet volume,
# which corrupts every volume-derived feature downstream. Ingestion never
# places orders, so the testnet flag does not apply here. Order routing in
# services/execution still respects PRAXIS_BINANCE_TESTNET.
rest_client = ccxt.binance({"enableRateLimit": True})

candle_aggregator = CandleAggregator(market_repo, rest_client)

symbols_to_track = ["BTC/USDT", "ETH/USDT"]

adapters = [
    get_adapter("BINANCE", testnet=False),
    # get_adapter("COINBASE", testnet=settings.COINBASE_SANDBOX) # Removed to avoid duplications in simple demo
]
ws_manager = WebSocketManager(adapters, symbols_to_track)


async def handle_tick(tick):
    """Live pricing path — publishes per-tick to Redis. Unchanged behaviour."""
    await telemetry.emit(
        "input_received",
        {"symbol": tick.symbol, "exchange": tick.exchange, "message_type": "exchange_tick"},
        source_agent="external",
    )

    event = MarketTickEvent(
        symbol=tick.symbol,
        exchange=tick.exchange,
        price=tick.price,
        volume=tick.volume,
        timestamp_us=tick.timestamp,
        source_service="ingestion",
    )

    with timer("ingestion.publish"):
        await asyncio.gather(
            stream_pub.publish(MARKET_DATA_STREAM, event),
            pubsub_broadcaster.publish(PUBSUB_PRICE_TICKS, event),
        )

    await telemetry.emit(
        "output_emitted",
        {"symbol": tick.symbol, "price": str(tick.price), "exchange": tick.exchange},
        target_agent="hot_path",
    )


async def handle_candle(candle):
    """Authoritative candle path — persists 1m bars and derives 5m/15m/1h."""
    await candle_aggregator.handle_candle(candle)


async def _backfill_on_startup():
    """Fill the gap between max(bucket) in DB and now, for every tracked pair.

    Uses Binance's public REST API (no auth required for klines). Safe to run
    against a fresh DB — `fill_gap` cold-starts with a bounded history.
    """
    try:
        total = await fill_gaps(market_repo, rest_client, symbols_to_track)
        logger.info("startup_backfill_complete", bars=total)
    except Exception as e:  # noqa: BLE001 — best effort; never block startup
        logger.warning("startup_backfill_failed", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing TimescaleDB pool...")
    await timescale_client.init_pool()

    logger.info("Running startup gap-fill...")
    await _backfill_on_startup()

    logger.info("Starting Ingestion Agent...")
    await ws_manager.start(handle_tick, handle_candle)
    await telemetry.start_health_loop()
    yield

    logger.info("Shutting down Ingestion Agent...")
    await telemetry.stop()
    await ws_manager.stop()
    await candle_aggregator.force_flush()
    await timescale_client.close()


app = create_health_app(ws_manager)
app.router.lifespan_context = lifespan

if __name__ == "__main__":
    uvicorn.run("services.ingestion.src.main:app", host="0.0.0.0", port=8080, log_level="error")
