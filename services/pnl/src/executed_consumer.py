"""ExecutedEventConsumer — the fill-confirmation half of the real exchange close.

PositionCloseRequester publishes a reduce-only order and CAS-marks the position
PENDING_CLOSE. The executor fills it and re-publishes an OrderExecutedEvent (or,
on failure, an OrderRejectedEvent) to stream:orders. This consumer reacts to
those CLOSE events:

  * on a confirmed fill  -> PositionCloser.finalize_close() using the REAL
    exchange fill price as the authoritative exit price (CAS PENDING_CLOSE ->
    CLOSED, exactly once);
  * on a rejection       -> PositionRepository.revert_close() (PENDING_CLOSE ->
    OPEN) so the position is monitored again — the 30s rehydrate re-adds it to
    the in-memory cache — and a SYSTEM_ALERT is raised.

It runs as its own consumer group (pnl_close_group) on stream:orders, independent
of execution's executor_group and the logger's audit group; every group receives
every message, so we filter cheaply on reduce_only first. A stale-event guard
mirrors the executor's MAX_ORDER_AGE_S so a close fill left over in the stream
from a previous session can't finalise a stale position at boot.
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal

from libs.core.enums import EventType
from libs.core.schemas import AlertEvent, OrderExecutedEvent, OrderRejectedEvent
from libs.messaging import StreamConsumer
from libs.messaging._pubsub import PubSubBroadcaster
from libs.messaging.channels import ORDERS_STREAM, PUBSUB_SYSTEM_ALERTS
from libs.observability import get_logger
from libs.storage.repositories import PositionRepository

from ._positions import record_to_position
from .closer import PositionCloser

logger = get_logger("pnl.close_consumer")

# Mirror the executor's stale-order guard. A reduce-only CLOSE event left in
# stream:orders from a previous session must not finalise a close for a position
# that has since been handled. Matches MAX_ORDER_AGE_S in execution/executor.py.
MAX_EVENT_AGE_S = 60.0

# Positions don't store their venue today (PR4/reconciler adds it). The existing
# tick-handler close path effectively always used the Binance/paper taker rate
# (0.001); keep that for parity until venue-aware fees land.
_DEFAULT_TAKER_RATE = Decimal("0.001")


class ExecutedEventConsumer:
    def __init__(
        self,
        consumer: StreamConsumer,
        position_repo: PositionRepository,
        closer: PositionCloser,
        pubsub: PubSubBroadcaster = None,
        group: str = "pnl_close_group",
        consumer_name: str = "pnl_close_1",
    ):
        self._consumer = consumer
        self._position_repo = position_repo
        self._closer = closer
        self._pubsub = pubsub
        self._group = group
        self._consumer_name = consumer_name

    async def run(self):
        """Supervisor loop — mirrors OrderExecutor.run(): keep consuming across
        transient Redis failures so a hiccup can't silently kill the close
        finaliser (which would strand positions in PENDING_CLOSE)."""
        logger.info("ExecutedEventConsumer starting", group=self._group)
        while True:
            try:
                await self._run_loop()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("close_consumer loop crashed — restarting", error=str(exc))
                await asyncio.sleep(1)

    async def _run_loop(self):
        while True:
            try:
                events = await self._consumer.consume(
                    ORDERS_STREAM, self._group, self._consumer_name, count=10
                )
            except Exception as exc:
                logger.error("close_consumer consume failed — retrying", error=str(exc))
                await asyncio.sleep(1)
                continue

            for _msg_id, ev in events:
                try:
                    await self._handle(ev)
                except Exception:
                    logger.exception("close_consumer handle failed")

            if events:
                await self._consumer.ack(
                    ORDERS_STREAM, self._group, [m for m, _ in events]
                )

    async def _handle(self, ev):
        # Cheap filter first: only reduce-only CLOSE events concern us. Open
        # orders and normal fills (the overwhelming majority on this stream) are
        # ignored without touching the DB.
        if isinstance(ev, OrderExecutedEvent):
            if ev.reduce_only and ev.close_position_id is not None:
                await self._on_fill(ev)
        elif isinstance(ev, OrderRejectedEvent):
            if ev.reduce_only and ev.close_position_id is not None:
                await self._on_reject(ev)

    def _is_stale(self, ev) -> bool:
        age_s = (time.time() * 1_000_000 - ev.timestamp_us) / 1_000_000
        if age_s > MAX_EVENT_AGE_S:
            logger.warning(
                "stale_close_event_skipped",
                age_s=round(age_s, 1),
                close_position_id=str(ev.close_position_id),
            )
            return True
        return False

    async def _on_fill(self, ev: OrderExecutedEvent):
        if self._is_stale(ev):
            return
        rec = await self._position_repo.get_by_id(ev.close_position_id)
        if rec is None:
            logger.warning(
                "close_fill_position_missing",
                close_position_id=str(ev.close_position_id),
            )
            return

        position = record_to_position(rec)
        close_reason = ev.close_reason or "exchange_close"
        snapshot = await self._closer.finalize_close(
            position=position,
            exit_price=ev.fill_price,  # authoritative exchange fill price
            taker_rate=_DEFAULT_TAKER_RATE,
            close_reason=close_reason,
        )
        if snapshot is None:
            return  # duplicate fill — already finalised by an earlier delivery
        logger.warning(
            "close_finalised",
            close_position_id=str(ev.close_position_id),
            fill_price=str(ev.fill_price),
            close_reason=close_reason,
        )

    async def _on_reject(self, ev: OrderRejectedEvent):
        reverted = await self._position_repo.revert_close(ev.close_position_id)
        logger.error(
            "close_order_rejected",
            close_position_id=str(ev.close_position_id),
            reason=ev.reason,
            reverted=reverted,
        )
        if self._pubsub is not None and reverted:
            try:
                alert = AlertEvent(
                    event_type=EventType.SYSTEM_ALERT,
                    message=(
                        f"Reduce-only close REJECTED for position {ev.close_position_id}: "
                        f"{ev.reason}. Position reverted to OPEN and will be re-monitored."
                    ),
                    level="RED",
                    profile_id=ev.profile_id,
                    timestamp_us=int(
                        datetime.now(timezone.utc).timestamp() * 1_000_000
                    ),
                    source_service="pnl",
                )
                await self._pubsub.publish(PUBSUB_SYSTEM_ALERTS, alert)
            except Exception:
                logger.exception("failed to publish close-reject alert")
