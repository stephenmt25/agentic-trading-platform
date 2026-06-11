"""PositionCloseRequester — routes a position close through the execution OMS.

Before PR1 a close only updated the DB (the "phantom close"): the real exchange
position stayed open. This requester instead:

  1. CAS-transitions the position OPEN -> PENDING_CLOSE. This is the idempotency
     guard — the exit monitor runs every tick and the manual endpoint is
     concurrent, so only the call that wins the CAS publishes a close order. One
     reduce-only order per position, ever.
  2. Publishes a reduce-only OrderApprovedEvent straight to stream:orders so the
     executor places the real close order. Publishing directly (not via hot_path)
     is deliberate: a same-symbol order routed through hot_path would be blocked
     by ReentryGate, and a close must never be gated by the kill switch /
     TRADING_ENABLED — a close reduces risk.

The DB close itself (positions -> CLOSED, closed_trades, daily-PnL, agent EWMA)
is finalised later by ExecutedEventConsumer when the reduce-only fill confirms,
using the real exchange fill price as the authoritative exit price.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from libs.core.enums import OrderSide
from libs.core.models import Position
from libs.core.schemas import OrderApprovedEvent
from libs.messaging import StreamPublisher
from libs.messaging.channels import ORDERS_STREAM, ORDERS_STREAM_MAXLEN
from libs.observability import get_logger
from libs.storage.repositories import PositionRepository

logger = get_logger("pnl.close_requester")


def _opposite(side: OrderSide) -> OrderSide:
    return OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY


class PositionCloseRequester:
    def __init__(self, position_repo: PositionRepository, publisher: StreamPublisher):
        self._position_repo = position_repo
        self._publisher = publisher

    async def request_close(
        self,
        position: Position,
        current_price: Decimal,
        close_reason: str = "stop_loss",
    ) -> Optional[UUID]:
        """Begin an asynchronous exchange close.

        Returns the published close order's id iff this call won the
        OPEN->PENDING_CLOSE CAS. Returns None when another path already owns the
        close (already PENDING_CLOSE/CLOSED) — the caller should stop monitoring
        the position either way.
        """
        close_order_id = uuid4()

        won = await self._position_repo.begin_close(
            position.position_id, close_order_id
        )
        if not won:
            logger.info(
                "close_already_in_flight",
                position_id=str(position.position_id),
                symbol=position.symbol,
            )
            return None

        approved = OrderApprovedEvent(
            profile_id=position.profile_id,
            symbol=position.symbol,
            side=_opposite(position.side),
            quantity=position.quantity,
            price=current_price,
            order_id=close_order_id,
            reduce_only=True,
            close_position_id=position.position_id,
            close_reason=close_reason,
            timestamp_us=int(datetime.now(timezone.utc).timestamp() * 1_000_000),
            source_service="pnl",
        )
        await self._publisher.publish(
            ORDERS_STREAM, approved, maxlen=ORDERS_STREAM_MAXLEN
        )

        logger.warning(
            "close_order_published",
            position_id=str(position.position_id),
            close_order_id=str(close_order_id),
            symbol=position.symbol,
            close_side=_opposite(position.side).value,
            quantity=str(position.quantity),
            reason=close_reason,
        )
        return close_order_id
