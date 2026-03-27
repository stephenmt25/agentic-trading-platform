import asyncio
from decimal import Decimal
from fastapi import FastAPI
import uvicorn
import httpx
from datetime import datetime
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient, PositionRepository, PnlRepository
from libs.storage.repositories import ProfileRepository
from libs.messaging import PubSubBroadcaster
from libs.messaging.channels import PUBSUB_PRICE_TICKS
from libs.observability import get_logger

from .calculator import PnLCalculator
from .publisher import PnLPublisher
from .closer import PositionCloser
from .stop_loss_monitor import StopLossMonitor
from services.tax.src.us_tax import TaxEstimate, USTaxCalculator

logger = get_logger("pnl")

# Cached map in memory for active positions to avoid constant db roundtrips
# Mapping {symbol: [Positions]}
active_positions_cache = {}

async def hydrate_positions(position_repo: PositionRepository):
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
    profile_repo = ProfileRepository(timescale_client)
    publisher = PnLPublisher(redis_instance, pubsub, pnl_repo)
    closer = PositionCloser(position_repo, redis_instance)
    stop_loss = StopLossMonitor(closer, profile_repo)

    await hydrate_positions(position_repo)

    TAKER_RATES = {
        "BINANCE": Decimal("0.001"),
        "COINBASE": Decimal("0.006"),
    }
    DEFAULT_TAKER_RATE = Decimal("0.002")

    async def pnl_tick_processor():
        async for channel, tick_data in pubsub.subscribe(PUBSUB_PRICE_TICKS):
            sym = tick_data.get("symbol")
            cp = Decimal(str(tick_data.get("price", "0")))

            positions = active_positions_cache.get(sym, [])
            positions_to_remove = []

            for pos in positions:
                diff_days = (datetime.utcnow() - pos.opened_at).days

                # Preliminary gross PnL for tax estimation (Decimal)
                if pos.side.value == "BUY":
                    prelim_gross = (cp - pos.entry_price) * pos.quantity
                else:
                    prelim_gross = (pos.entry_price - cp) * pos.quantity

                tax = USTaxCalculator.calculate(
                    holding_duration_days=diff_days,
                    net_pnl=prelim_gross,
                )

                exchange_name = getattr(pos, 'exchange', 'BINANCE') if hasattr(pos, 'exchange') else 'BINANCE'
                taker_rate = TAKER_RATES.get(str(exchange_name).upper(), DEFAULT_TAKER_RATE)

                snapshot = PnLCalculator.calculate(
                    position=pos,
                    current_price=cp,
                    taker_rate=taker_rate,
                    tax_result=tax
                )
                await publisher.publish_update(pos.profile_id, snapshot)

                # Stop-loss enforcement (D-9)
                closed = await stop_loss.check(pos, snapshot, cp, taker_rate)
                if closed:
                    positions_to_remove.append(pos)

            # Remove closed positions from cache
            for pos in positions_to_remove:
                positions.remove(pos)

    # Loop
    logger.info("Starting PNL PubSub listener loop (stop-loss enforcement enabled)")
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
