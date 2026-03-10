import asyncio
import uuid
from datetime import datetime
from libs.core.schemas import OrderApprovedEvent, OrderExecutedEvent, OrderRejectedEvent, BaseEvent
from libs.core.models import Order, Position
from libs.core.enums import OrderStatus, PositionStatus
from libs.exchange import get_adapter
from libs.messaging import StreamPublisher, StreamConsumer
from libs.storage.repositories import OrderRepository, PositionRepository, AuditRepository
from libs.core.types import ProfileId

from .ledger import OptimisticLedger
from libs.observability import get_logger

logger = get_logger("execution.executor")

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
    ):
        self._publisher = publisher
        self._consumer = consumer
        self._order_repo = order_repo
        self._position_repo = position_repo
        self._audit_repo = audit_repo
        self._ledger = ledger
        self._channel = orders_channel

    async def run(self):
        logger.info("OrderExecutor starting loop")
        # In memory tracking for demo
        adapter = get_adapter("BINANCE", testnet=True) # Usually retrieved from profile key reference
        
        while True:
            events = await self._consumer.consume(self._channel, "executor_group", "executor_1", count=10)
            
            for msg_id, ev in events:
                if not ev or not isinstance(ev, OrderApprovedEvent):
                    continue
                    
                order_id = uuid.uuid4()
                
                # 1. RateLimiter bypass for now, covered in network adapter directly initially
                
                # 2. Get API key - (hardcoded fallback to test adapter)
                
                # 3-5. Write to orders table optimisticly
                order = Order(
                    order_id=order_id,
                    profile_id=ev.profile_id,
                    symbol=ev.symbol,
                    side=ev.side,
                    quantity=ev.quantity,
                    price=ev.price,
                    status=OrderStatus.PENDING,
                    exchange="BINANCE",
                    created_at=datetime.utcnow()
                )
                
                await self._order_repo.create_order(order)
                await self._ledger.submit(order_id)
                await self._audit_repo.write_audit_event(ev, {"action": "Optimistic SUBMITTED", "order_id": str(order_id)})
                
                try:
                    # Execute
                    res = await adapter.place_order(ev.profile_id, ev.symbol, ev.side, ev.quantity, ev.price)
                    
                    if res.status == OrderStatus.SUBMITTED or res.status == OrderStatus.CONFIRMED:
                        await self._ledger.confirm(order_id, fill_price=ev.price) # Approximating fill price for demo limit
                        
                        # 6. Create Position immediately after Confirmation
                        pos_id = uuid.uuid4()
                        pos = Position(
                            position_id=pos_id,
                            profile_id=ev.profile_id,
                            symbol=ev.symbol,
                            side=ev.side,
                            entry_price=ev.price,
                            quantity=ev.quantity,
                            entry_fee=0.001 * float(ev.quantity), # mock fee 0.1%
                            opened_at=datetime.utcnow(),
                            status=PositionStatus.OPEN
                        )
                        await self._position_repo.create_position(pos)
                        
                        # Emit executed
                        executed_ev = OrderExecutedEvent(
                            order_id=order_id,
                            profile_id=ev.profile_id,
                            symbol=ev.symbol,
                            side=ev.side,
                            fill_price=ev.price,
                            quantity=ev.quantity,
                            timestamp_us=int(datetime.utcnow().timestamp() * 1000000),
                            source_service="execution"
                        )
                        await self._publisher.publish(self._channel, executed_ev)
                        
                    else:
                        raise ValueError(f"Exchange returns bad status: {res.status}")

                except Exception as e:
                    await self._ledger.rollback(order_id, reason=str(e))
                    await self._audit_repo.write_audit_event(ev, {"action": "ROLLED_BACK", "reason": str(e), "order_id": str(order_id)})
                    
                    fail_ev = OrderRejectedEvent(
                        profile_id=ev.profile_id,
                        symbol=ev.symbol,
                        reason=f"Execution Failed: {e}",
                        timestamp_us=int(datetime.utcnow().timestamp() * 1000000),
                        source_service="execution"
                    )
                    await self._publisher.publish(self._channel, fail_ev)
                    
            if events:
                await self._consumer.ack(self._channel, "executor_group", [m for m, _ in events])
