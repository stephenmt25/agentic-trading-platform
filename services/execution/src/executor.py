import asyncio
import json
import uuid
from decimal import Decimal
from datetime import datetime
from libs.core.schemas import OrderApprovedEvent, OrderExecutedEvent, OrderRejectedEvent, BaseEvent
from libs.core.models import Order, Position
from libs.core.enums import OrderStatus, PositionStatus
from libs.core.secrets import SecretManager
from libs.exchange import get_adapter
from libs.messaging import StreamPublisher, StreamConsumer
from libs.storage.repositories import OrderRepository, PositionRepository, AuditRepository, ProfileRepository
from libs.core.types import ProfileId
from libs.config import settings

from .ledger import OptimisticLedger
from libs.observability import get_logger
from libs.core.agent_registry import AgentPerformanceTracker

logger = get_logger("execution.executor")

# Exchange-specific taker fee rates
EXCHANGE_FEE_RATES = {
    "BINANCE": Decimal("0.001"),    # 0.10%
    "COINBASE": Decimal("0.006"),   # 0.60%
}
DEFAULT_FEE_RATE = Decimal("0.002")  # 0.20% conservative fallback


class OrderExecutor:
    def __init__(
        self,
        publisher: StreamPublisher,
        consumer: StreamConsumer,
        order_repo: OrderRepository,
        position_repo: PositionRepository,
        audit_repo: AuditRepository,
        ledger: OptimisticLedger,
        orders_channel: str,
        profile_repo: ProfileRepository = None,
        secret_manager: SecretManager = None,
        redis_client=None,
    ):
        self._publisher = publisher
        self._consumer = consumer
        self._order_repo = order_repo
        self._position_repo = position_repo
        self._audit_repo = audit_repo
        self._ledger = ledger
        self._channel = orders_channel
        self._profile_repo = profile_repo
        self._secret_manager = secret_manager or SecretManager(gcp_project_id=settings.GCP_PROJECT_ID)
        self._redis_client = redis_client

    async def _resolve_adapter(self, profile_id: str):
        """Load the user's exchange keys from SecretManager and return the correct adapter."""
        exchange_name = "BINANCE"  # default
        api_key = ""
        api_secret = ""
        testnet = settings.BINANCE_TESTNET

        if self._profile_repo:
            try:
                profile = await self._profile_repo.get_profile(profile_id)
                if profile:
                    key_ref = profile.get("exchange_key_ref", "paper")
                    if key_ref and key_ref != "paper":
                        # Derive exchange name from the key_ref convention: usr-{uid}-{exchange}-keys
                        parts = key_ref.split("-")
                        if len(parts) >= 3:
                            exchange_name = parts[-2].upper()
                        try:
                            creds_json = await self._secret_manager.get_secret(key_ref)
                            creds = json.loads(creds_json)
                            api_key = creds.get("apiKey", "")
                            api_secret = creds.get("secret", "")
                        except FileNotFoundError:
                            logger.warning("Exchange keys not found, falling back to testnet", profile_id=profile_id)
                        except Exception as e:
                            logger.error("Failed to load exchange keys", error=str(e), profile_id=profile_id)
            except Exception as e:
                logger.error("Failed to load profile for adapter resolution", error=str(e))

        if exchange_name == "COINBASE":
            testnet = settings.COINBASE_SANDBOX

        return get_adapter(exchange_name, api_key=api_key, secret=api_secret, testnet=testnet), exchange_name

    async def _record_agent_scores(self, symbol: str, position_id: str, side: str):
        """Snapshot current agent scores from Redis and record for weight feedback."""
        try:
            pipe = self._redis_client.pipeline(transaction=False)
            pipe.get(f"agent:ta_score:{symbol}")
            pipe.get(f"agent:sentiment:{symbol}")
            pipe.get(f"agent:debate:{symbol}")
            ta_raw, sent_raw, debate_raw = await pipe.execute()

            agents = {}
            direction = side if isinstance(side, str) else side.value

            if ta_raw:
                data = json.loads(ta_raw)
                agents["ta"] = {"direction": direction, "score": float(data.get("score", 0))}
            if sent_raw:
                data = json.loads(sent_raw)
                agents["sentiment"] = {"direction": direction, "score": float(data.get("score", 0))}
            if debate_raw:
                data = json.loads(debate_raw)
                agents["debate"] = {"direction": direction, "score": float(data.get("score", 0))}

            if agents:
                tracker = AgentPerformanceTracker(self._redis_client)
                await tracker.record_agent_scores(symbol, agents)

                # Also cache agent snapshot for this position (used on close)
                await self._redis_client.set(
                    f"agent:position_scores:{position_id}",
                    json.dumps(agents),
                    ex=86400 * 7,  # 7 day TTL
                )
        except Exception as e:
            logger.warning("Failed to record agent scores", error=str(e), symbol=symbol)

    async def run(self):
        logger.info("OrderExecutor starting loop")

        while True:
            events = await self._consumer.consume(self._channel, "executor_group", "executor_1", count=10)

            for msg_id, ev in events:
                if not ev or not isinstance(ev, OrderApprovedEvent):
                    continue

                order_id = uuid.uuid4()

                # 1. Resolve exchange adapter using profile's stored keys
                adapter, exchange_name = await self._resolve_adapter(str(ev.profile_id))
                fee_rate = EXCHANGE_FEE_RATES.get(exchange_name, DEFAULT_FEE_RATE)

                # 2. Write to orders table optimistically
                order = Order(
                    order_id=order_id,
                    profile_id=ev.profile_id,
                    symbol=ev.symbol,
                    side=ev.side,
                    quantity=ev.quantity,
                    price=ev.price,
                    status=OrderStatus.PENDING,
                    exchange=exchange_name,
                    created_at=datetime.utcnow()
                )

                await self._order_repo.create_order(order)

                # 3. Optimistic ledger submit — check result
                submitted = await self._ledger.submit(order_id)
                if not submitted:
                    logger.error("Ledger submit failed, skipping order", order_id=str(order_id))
                    await self._audit_repo.write_audit_event(ev, {"action": "SUBMIT_FAILED", "order_id": str(order_id)})
                    continue

                await self._audit_repo.write_audit_event(ev, {"action": "Optimistic SUBMITTED", "order_id": str(order_id)})

                try:
                    # 4. Execute on exchange
                    res = await adapter.place_order(ev.profile_id, ev.symbol, ev.side, ev.quantity, ev.price)

                    if res.status == OrderStatus.SUBMITTED or res.status == OrderStatus.CONFIRMED:
                        fill_price = res.fill_price if res.fill_price else ev.price

                        # 5. Confirm in ledger — check result
                        confirmed = await self._ledger.confirm(
                            order_id, fill_price=fill_price,
                            profile_id=str(ev.profile_id), quantity=ev.quantity
                        )
                        if not confirmed:
                            logger.error("Ledger confirm failed after exchange success", order_id=str(order_id))
                            await self._ledger.rollback(order_id, reason="Ledger confirm failed post-exchange")
                            raise ValueError("Ledger confirmation failed after exchange accepted order")

                        # 6. Create Position immediately after Confirmation
                        pos_id = uuid.uuid4()
                        entry_fee = fee_rate * ev.quantity * fill_price
                        pos = Position(
                            position_id=pos_id,
                            profile_id=ev.profile_id,
                            symbol=ev.symbol,
                            side=ev.side,
                            entry_price=fill_price,
                            quantity=ev.quantity,
                            entry_fee=entry_fee,
                            opened_at=datetime.utcnow(),
                            status=PositionStatus.OPEN
                        )
                        await self._position_repo.create_position(pos)

                        # 6b. Snapshot agent scores at time of execution for weight feedback
                        if self._redis_client:
                            await self._record_agent_scores(ev.symbol, str(pos_id), ev.side)

                        # 7. Emit executed event
                        executed_ev = OrderExecutedEvent(
                            order_id=order_id,
                            profile_id=ev.profile_id,
                            symbol=ev.symbol,
                            side=ev.side,
                            fill_price=fill_price,
                            quantity=ev.quantity,
                            timestamp_us=int(datetime.utcnow().timestamp() * 1000000),
                            source_service="execution"
                        )
                        await self._publisher.publish(self._channel, executed_ev)

                    else:
                        raise ValueError(f"Exchange returned unexpected status: {res.status}")

                except Exception as e:
                    rolled_back = await self._ledger.rollback(order_id, reason=str(e))
                    if not rolled_back:
                        logger.critical("Ledger rollback ALSO failed — manual intervention required",
                                        order_id=str(order_id), error=str(e))
                    await self._audit_repo.write_audit_event(ev, {"action": "ROLLED_BACK", "reason": str(e), "order_id": str(order_id)})

                    fail_ev = OrderRejectedEvent(
                        profile_id=ev.profile_id,
                        symbol=ev.symbol,
                        reason=f"Execution Failed: {e}",
                        timestamp_us=int(datetime.utcnow().timestamp() * 1000000),
                        source_service="execution"
                    )
                    await self._publisher.publish(self._channel, fail_ev)
                finally:
                    # Close adapter to free resources (each order gets its own adapter)
                    try:
                        await adapter.close()
                    except Exception:
                        pass

            if events:
                await self._consumer.ack(self._channel, "executor_group", [m for m, _ in events])
