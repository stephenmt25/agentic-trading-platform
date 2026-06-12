"""Integration: stream:orders -> validation fast-gate -> execution contract.

Real Redis streams + real TimescaleDB, library-level service classes only
(no uvicorn processes). Mirrors the production wiring:

  hot_path  --ValidationRequestEvent--> stream:validation
  validation FastGateHandler           --ValidationResponseEvent-->
            stream:validation_response + LPUSH validation:resp:{event_id}
  hot_path  ValidationClient BLPOPs the RPC key
  gateway/hot_path --OrderApprovedEvent--> stream:orders
  execution OrderExecutor consumes stream:orders (group executor_group)

Ports the spirit of scripts/verify_pr1_close_e2e.py into a repeatable test.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest

from libs.core.enums import OrderSide, ValidationCheck, ValidationVerdict
from libs.core.schemas import (
    OrderApprovedEvent,
    OrderExecutedEvent,
    ValidationRequestEvent,
    ValidationResponseEvent,
)
from libs.messaging import StreamConsumer, StreamPublisher
from libs.messaging._serialisation import encode_event
from libs.messaging.channels import (
    ORDERS_STREAM,
    VALIDATION_RESPONSE_STREAM,
    VALIDATION_STREAM,
)
from services.hot_path.src.validation_client import ValidationClient
from services.validation.src.check_1_strategy import StrategyRecheck
from services.validation.src.check_6_risk_level import RiskLevelRecheck
from services.validation.src.fast_gate import FastGateHandler

from .conftest import utc_now_us, wait_for


def _validation_request(profile_id, symbol, quantity, price):
    return ValidationRequestEvent(
        timestamp_us=utc_now_us(),
        source_service="hot_path",
        profile_id=str(profile_id),
        symbol=symbol,
        check_type=ValidationCheck.CHECK_1_STRATEGY,
        payload={
            "quantity": str(quantity),
            "price": str(price),
            "inds": {"rsi": 55.0},
        },
    )


def _order_approved(profile_id, symbol="BTC/USDT", quantity="0.01", price="50000"):
    return OrderApprovedEvent(
        timestamp_us=utc_now_us(),
        source_service="api_gateway",
        profile_id=str(profile_id),
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=Decimal(quantity),
        price=Decimal(price),
        order_id=uuid.uuid4(),
    )


def _build_fast_gate(db, redis_client) -> FastGateHandler:
    """The exact wiring services/validation/src/main.py uses."""
    from libs.storage import MarketDataRepository
    from libs.storage.repositories import ProfileRepository

    check1 = StrategyRecheck(MarketDataRepository(db), redis_client)
    check6 = RiskLevelRecheck(ProfileRepository(db))
    return FastGateHandler(check1, check6)


async def _serve_fast_gate_once(redis_client, fast_gate) -> ValidationResponseEvent:
    """One iteration of validation main.py's fast_gate_loop: consume the
    request from stream:validation, run the real gate, publish the response
    to stream:validation_response AND LPUSH the per-request RPC key."""
    consumer = StreamConsumer(redis_client)
    publisher = StreamPublisher(redis_client)
    while True:
        events = await consumer.consume(
            VALIDATION_STREAM, "fastgate_group", "gate_1", count=10, block_ms=100
        )
        for msg_id, ev in events:
            assert ev is not None, "validation request failed to decode"
            resp = await fast_gate.handle(ev)
            await publisher.publish(VALIDATION_RESPONSE_STREAM, resp)
            resp_key = f"validation:resp:{ev.event_id}"
            await redis_client.lpush(resp_key, encode_event(resp))
            await redis_client.expire(resp_key, 5)
            await consumer.ack(VALIDATION_STREAM, "fastgate_group", [msg_id])
            return resp
        await asyncio.sleep(0.01)


class TestValidationFastGateContract:
    @pytest.mark.asyncio
    async def test_fast_gate_green_roundtrip(self, redis_client, db, seeded_profile):
        """Request via the real hot_path ValidationClient; real FastGateHandler
        (real profile row, real Redis) answers GREEN on both response paths."""
        fast_gate = _build_fast_gate(db, redis_client)
        client = ValidationClient(
            publisher=StreamPublisher(redis_client),
            consumer=StreamConsumer(redis_client),
            req_channel=VALIDATION_STREAM,
            resp_channel=VALIDATION_RESPONSE_STREAM,
            timeout_ms=5000,
        )
        # $500 order against $10k notional with max_allocation_pct=0.25 -> GREEN
        request = _validation_request(
            seeded_profile["profile_id"], "BTC/USDT", "0.01", "50000"
        )

        server = asyncio.create_task(_serve_fast_gate_once(redis_client, fast_gate))
        try:
            response = await client.fast_gate(request)
        finally:
            served = await asyncio.wait_for(server, timeout=5)

        assert response is not None, "BLPOP RPC response did not arrive"
        assert isinstance(response, ValidationResponseEvent)
        assert response.verdict == ValidationVerdict.GREEN
        assert response.event_id == request.event_id  # 1:1 RPC correlation
        assert served.verdict == ValidationVerdict.GREEN

        # The broadcast copy must land on stream:validation_response and decode.
        observer = StreamConsumer(redis_client)
        events = await observer.consume(
            VALIDATION_RESPONSE_STREAM, "test_observer", "obs_1", block_ms=500
        )
        assert len(events) == 1
        _, stream_ev = events[0]
        assert isinstance(stream_ev, ValidationResponseEvent)
        assert stream_ev.verdict == ValidationVerdict.GREEN
        assert stream_ev.event_id == request.event_id

    @pytest.mark.asyncio
    async def test_fast_gate_red_when_allocation_exceeded(
        self, redis_client, db, seeded_profile
    ):
        """A $100k order against $10k notional (max 25%) must come back RED
        from the real Check 6 against the real profile row."""
        fast_gate = _build_fast_gate(db, redis_client)
        client = ValidationClient(
            publisher=StreamPublisher(redis_client),
            consumer=StreamConsumer(redis_client),
            req_channel=VALIDATION_STREAM,
            resp_channel=VALIDATION_RESPONSE_STREAM,
            timeout_ms=5000,
        )
        request = _validation_request(
            seeded_profile["profile_id"], "ETH/USDT", "2", "50000"
        )

        server = asyncio.create_task(_serve_fast_gate_once(redis_client, fast_gate))
        try:
            response = await client.fast_gate(request)
        finally:
            await asyncio.wait_for(server, timeout=5)

        assert response is not None
        assert response.verdict == ValidationVerdict.RED
        assert "max allocation" in (response.reason or "")


class TestExecutionConsumerContract:
    @pytest.mark.asyncio
    async def test_order_approved_event_parses_through_executor_consumer(
        self, redis_client, seeded_profile
    ):
        """Publish OrderApprovedEvent the way the gateway does; the executor's
        StreamConsumer identity (executor_group/executor_1) must decode it with
        Decimal fields intact."""
        publisher = StreamPublisher(redis_client)
        event = _order_approved(seeded_profile["profile_id"])
        await publisher.publish(ORDERS_STREAM, event, maxlen=10_000)

        consumer = StreamConsumer(redis_client)
        events = await consumer.consume(
            ORDERS_STREAM, "executor_group", "executor_1", count=10, block_ms=500
        )
        assert len(events) == 1
        msg_id, decoded = events[0]
        assert isinstance(decoded, OrderApprovedEvent)
        assert decoded.event_id == event.event_id
        assert decoded.order_id == event.order_id
        assert isinstance(decoded.quantity, Decimal)
        assert isinstance(decoded.price, Decimal)
        assert decoded.quantity == Decimal("0.01")
        assert decoded.price == Decimal("50000")
        assert decoded.reduce_only is False

        await consumer.ack(ORDERS_STREAM, "executor_group", [msg_id])
        pending = await redis_client.xpending(ORDERS_STREAM, "executor_group")
        assert pending["pending"] == 0

    @pytest.mark.asyncio
    async def test_executor_paper_fill_end_to_end(
        self, redis_client, db, seeded_profile, monkeypatch
    ):
        """Drive the REAL OrderExecutor (paper adapter) off stream:orders:
        order row -> CONFIRMED with fill, position row OPEN, OrderExecutedEvent
        published back onto stream:orders."""
        from unittest.mock import MagicMock

        from libs.config import settings
        from libs.storage import AuditRepository, OrderRepository, PositionRepository
        from services.execution.src.executor import OrderExecutor
        from services.execution.src.ledger import OptimisticLedger

        monkeypatch.setattr(settings, "PAPER_TRADING_MODE", True)
        monkeypatch.setattr(settings, "TRADING_ENABLED", True)
        monkeypatch.setattr(settings, "PROTECTIVE_STOP_ENABLED", False)

        order_repo = OrderRepository(db)
        executor = OrderExecutor(
            publisher=StreamPublisher(redis_client),
            consumer=StreamConsumer(redis_client),
            order_repo=order_repo,
            position_repo=PositionRepository(db),
            audit_repo=AuditRepository(db),
            ledger=OptimisticLedger(order_repo),
            orders_channel=ORDERS_STREAM,
            secret_manager=MagicMock(),
            redis_client=redis_client,
        )

        event = _order_approved(
            seeded_profile["profile_id"], symbol="ETH/USDT", quantity="0.02"
        )
        await StreamPublisher(redis_client).publish(ORDERS_STREAM, event, maxlen=10_000)

        task = asyncio.create_task(executor.run())
        try:
            order_row = await wait_for(
                lambda: db.fetchrow(
                    "SELECT * FROM orders WHERE order_id = $1 AND status = 'CONFIRMED'",
                    event.order_id,
                ),
                timeout_s=15,
            )
            position_row = await wait_for(
                lambda: db.fetchrow(
                    "SELECT * FROM positions WHERE order_id = $1", event.order_id
                ),
                timeout_s=15,
            )
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        # Order persisted and confirmed at a paper fill (BUY fills above quote).
        assert order_row["exchange"] == "PAPER"
        assert isinstance(order_row["fill_price"], Decimal)
        assert order_row["fill_price"] > Decimal("50000")

        # Position opened with the exact fill as Decimal entry price.
        assert position_row["status"] == "OPEN"
        assert position_row["entry_price"] == order_row["fill_price"]
        assert position_row["quantity"] == Decimal("0.02")
        assert isinstance(position_row["entry_fee"], Decimal)

        # OrderExecutedEvent published back onto stream:orders and decodable.
        observer = StreamConsumer(redis_client)
        executed = None
        for _ in range(10):
            events = await observer.consume(
                ORDERS_STREAM, "test_observer", "obs_1", count=10, block_ms=300
            )
            for _msg_id, ev in events:
                if isinstance(ev, OrderExecutedEvent):
                    executed = ev
            if executed:
                break
        assert executed is not None, "OrderExecutedEvent never landed on stream:orders"
        assert executed.order_id == event.order_id
        assert executed.fill_price == order_row["fill_price"]
        assert executed.reduce_only is False

    @pytest.mark.asyncio
    async def test_executor_skips_stale_orders(
        self, redis_client, db, seeded_profile, monkeypatch
    ):
        """Stream replay safety: an order older than MAX_ORDER_AGE_S left in
        stream:orders must be dropped, not executed (stale-message guard)."""
        from unittest.mock import MagicMock

        from libs.config import settings
        from libs.storage import AuditRepository, OrderRepository, PositionRepository
        from services.execution.src.executor import MAX_ORDER_AGE_S, OrderExecutor
        from services.execution.src.ledger import OptimisticLedger

        monkeypatch.setattr(settings, "PAPER_TRADING_MODE", True)
        monkeypatch.setattr(settings, "TRADING_ENABLED", True)

        stale = OrderApprovedEvent(
            timestamp_us=utc_now_us() - int((MAX_ORDER_AGE_S + 30) * 1_000_000),
            source_service="api_gateway",
            profile_id=str(seeded_profile["profile_id"]),
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            price=Decimal("50000"),
            order_id=uuid.uuid4(),
        )
        await StreamPublisher(redis_client).publish(ORDERS_STREAM, stale, maxlen=10_000)

        order_repo = OrderRepository(db)
        executor = OrderExecutor(
            publisher=StreamPublisher(redis_client),
            consumer=StreamConsumer(redis_client),
            order_repo=order_repo,
            position_repo=PositionRepository(db),
            audit_repo=AuditRepository(db),
            ledger=OptimisticLedger(order_repo),
            orders_channel=ORDERS_STREAM,
            secret_manager=MagicMock(),
            redis_client=redis_client,
        )
        task = asyncio.create_task(executor.run())
        try:
            # The guard acks silently; once pending drains the order was seen.
            await wait_for(
                lambda: _acked(redis_client),
                timeout_s=15,
            )
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        row = await db.fetchrow(
            "SELECT * FROM orders WHERE order_id = $1", stale.order_id
        )
        assert row is None, "stale order must never reach the orders table"


async def _acked(redis_client) -> bool:
    """True once executor_group has consumed past the message and acked it."""
    try:
        info = await redis_client.xpending(ORDERS_STREAM, "executor_group")
        groups = await redis_client.xinfo_groups(ORDERS_STREAM)
    except Exception:
        return False  # group not created yet
    delivered = False
    for g in groups:
        name = g.get("name", g.get(b"name"))
        if isinstance(name, bytes):
            name = name.decode()
        last_id = g.get("last-delivered-id", g.get(b"last-delivered-id"))
        if isinstance(last_id, bytes):
            last_id = last_id.decode()
        if name == "executor_group" and last_id not in (None, "0-0"):
            delivered = True
    return delivered and info["pending"] == 0
