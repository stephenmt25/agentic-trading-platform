import asyncio
from decimal import Decimal
from fastapi import FastAPI
import uvicorn
import httpx
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from libs.config import settings
from libs.storage import RedisClient, TimescaleClient, PositionRepository, PnlRepository
from libs.storage.repositories import ProfileRepository
from libs.messaging import PubSubBroadcaster
from libs.messaging._pubsub import PubSubSubscriber
from libs.messaging.channels import PUBSUB_PRICE_TICKS
from libs.observability import get_logger
from libs.observability.telemetry import TelemetryPublisher

from .calculator import PnLCalculator
from .publisher import PnLPublisher
from .closer import PositionCloser
from .exit_monitor import ExitMonitor
from services.tax.src.us_tax import TaxEstimate, USTaxCalculator
from libs.core.models import Position
from libs.core.enums import OrderSide, PositionStatus

logger = get_logger("pnl")

# Cached map in memory for active positions to avoid constant db roundtrips
# Mapping {symbol: [Positions]}
active_positions_cache = {}

def _record_to_position(rec) -> Position:
    """Convert an asyncpg Record to a Position dataclass."""
    return Position(
        position_id=rec["position_id"],
        profile_id=str(rec["profile_id"]),
        symbol=rec["symbol"],
        side=OrderSide(rec["side"]),
        entry_price=Decimal(str(rec["entry_price"])),
        quantity=Decimal(str(rec["quantity"])),
        entry_fee=Decimal(str(rec["entry_fee"])),
        opened_at=rec["opened_at"],
        status=PositionStatus(rec["status"]) if rec.get("status") else PositionStatus.OPEN,
        closed_at=rec.get("closed_at"),
        exit_price=Decimal(str(rec["exit_price"])) if rec.get("exit_price") else None,
    )


async def hydrate_positions(position_repo: PositionRepository):
    """Rebuild active_positions_cache from DB. Atomic swap — safe to call while
    tick handler is iterating: in-flight iterations keep their list reference."""
    all_open = await position_repo.get_open_positions()
    new_cache: dict[str, list[Position]] = {}
    for rec in all_open:
        pos = _record_to_position(rec)
        new_cache.setdefault(pos.symbol, []).append(pos)
    active_positions_cache.clear()
    active_positions_cache.update(new_cache)


async def rehydrate_loop(position_repo: PositionRepository, interval_s: float = 30.0):
    """Periodically refresh the cache so positions opened after startup are monitored."""
    while True:
        try:
            await asyncio.sleep(interval_s)
            before = sum(len(v) for v in active_positions_cache.values())
            await hydrate_positions(position_repo)
            after = sum(len(v) for v in active_positions_cache.values())
            logger.info(
                "position_cache_rehydrated",
                symbols=len(active_positions_cache),
                positions=after,
                delta=after - before,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("position_cache_rehydrate_failed")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connections
    redis_instance = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale_client = TimescaleClient(settings.DATABASE_URL)
    await timescale_client.init_pool()

    # Dependencies
    pubsub = PubSubBroadcaster(redis_instance)
    subscriber = PubSubSubscriber(redis_instance)
    position_repo = PositionRepository(timescale_client)
    pnl_repo = PnlRepository(timescale_client)
    profile_repo = ProfileRepository(timescale_client)
    publisher = PnLPublisher(redis_instance, pubsub, pnl_repo)
    closer = PositionCloser(position_repo, redis_instance)
    exit_monitor = ExitMonitor(closer, profile_repo)

    telemetry = TelemetryPublisher(redis_instance, "pnl", "portfolio")
    await telemetry.start_health_loop()

    await hydrate_positions(position_repo)

    TAKER_RATES = {
        "BINANCE": Decimal("0.001"),
        "COINBASE": Decimal("0.006"),
    }
    DEFAULT_TAKER_RATE = Decimal("0.002")

    async def handle_tick(raw_message):
        """Callback for PubSubSubscriber — processes a single price tick."""
        import msgpack
        try:
            if isinstance(raw_message, bytes):
                tick_data = msgpack.unpackb(raw_message, raw=False)
            else:
                tick_data = raw_message
        except Exception:
            logger.warning("Failed to decode tick message, skipping")
            return

        logger.info("tick_received", symbol=tick_data.get("symbol"), price=str(tick_data.get("price", "?")), positions_cached=len(active_positions_cache))

        try:
            await _process_tick(tick_data)
        except Exception:
            logger.exception("Error processing tick", symbol=tick_data.get("symbol"))

    async def _process_tick(tick_data):
        sym = tick_data.get("symbol")
        cp = Decimal(str(tick_data.get("price", "0")))

        await telemetry.emit("input_received", {"symbol": sym, "price": str(cp), "message_type": "price_tick"}, source_agent="ingestion")

        positions = active_positions_cache.get(sym, [])
        positions_to_remove = []

        for pos in positions:
            diff_days = (datetime.now(timezone.utc) - pos.opened_at).days if pos.opened_at else 0

            # Preliminary gross PnL for tax estimation (Decimal)
            if pos.side == OrderSide.BUY:
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
            await publisher.publish_update(str(pos.profile_id), snapshot)

            await telemetry.emit(
                "output_emitted",
                {
                    "position_id": str(pos.position_id),
                    "symbol": sym,
                    "net_pnl": str(snapshot.net_pre_tax),
                },
            )

            # Exit policy enforcement (stop-loss + take-profit + time-exit)
            closed, reason = await exit_monitor.check(pos, snapshot, cp, taker_rate)
            if closed:
                await telemetry.emit(
                    "output_emitted",
                    {
                        "event": f"exit_{reason}",
                        "position_id": str(pos.position_id),
                        "symbol": sym,
                    },
                )
                positions_to_remove.append(pos)

        # Remove closed positions from cache
        for pos in positions_to_remove:
            positions.remove(pos)

    # Loop
    logger.info(
        "Starting PNL PubSub listener loop (exit policies: stop-loss=%.1f%%, take-profit=%.1f%%, max-hold=%dh)",
        float(settings.DEFAULT_STOP_LOSS_PCT) * 100,
        float(settings.DEFAULT_TAKE_PROFIT_PCT) * 100,
        int(settings.DEFAULT_MAX_HOLDING_HOURS),
    )
    listener_task = asyncio.create_task(subscriber.subscribe(PUBSUB_PRICE_TICKS, handle_tick))
    rehydrate_task = asyncio.create_task(rehydrate_loop(position_repo))

    yield

    # Teardown
    listener_task.cancel()
    rehydrate_task.cancel()
    await asyncio.gather(listener_task, rehydrate_task, return_exceptions=True)
    await telemetry.stop()
    await timescale_client.close()
    logger.info("PnL Agent shutdown")

app = FastAPI(title="PnL Service", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("services.pnl.src.main:app", host="0.0.0.0", port=8084)
