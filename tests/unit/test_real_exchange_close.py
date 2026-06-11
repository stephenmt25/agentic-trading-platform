"""Unit tests for the real-exchange-close path (PR1 — kill the phantom close).

Covers the new pieces end to end at the unit level:
  - event schema round-trips reduce_only / close_position_id / close_reason, and
    legacy messages without them decode with safe defaults;
  - PositionCloseRequester: opposite side, single reduce-only publish, CAS-guarded
    idempotency (no publish when begin_close loses);
  - PositionRepository CAS wrappers return True/False on RETURNING row/None;
  - PositionCloser.finalize_close: uses the fill price, runs the ledger writes
    once, and is a no-op (no daily bump / EWMA) when the CAS already finalised;
  - PaperTradingAdapter simulates a directional reduce-only fill;
  - ExecutedEventConsumer: finalise on fill, revert+alert on reject, ignore
    non-close events, skip stale events;
  - ExitMonitor routes exits through the requester when enabled.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import msgpack
import pytest

from libs.core.enums import OrderSide, PositionStatus
from libs.core.models import Position
from libs.core.schemas import OrderApprovedEvent, OrderExecutedEvent, OrderRejectedEvent
from libs.messaging._serialisation import decode_event, encode_event
from libs.messaging.channels import ORDERS_STREAM
from services.pnl.src.close_requester import PositionCloseRequester
from services.pnl.src.closer import PositionCloser
from services.pnl.src.executed_consumer import MAX_EVENT_AGE_S, ExecutedEventConsumer
from services.pnl.src.exit_monitor import ExitMonitor


def _now_us() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1_000_000)


def _position(side=OrderSide.BUY, quantity=Decimal("0.5")):
    return Position(
        position_id=uuid.uuid4(),
        profile_id=str(uuid.uuid4()),
        symbol="BTC/USDT",
        side=side,
        entry_price=Decimal("50000"),
        quantity=quantity,
        entry_fee=Decimal("25"),
        opened_at=datetime.now(timezone.utc) - timedelta(hours=1),
        status=PositionStatus.OPEN,
        order_id=uuid.uuid4(),
        decision_event_id=uuid.uuid4(),
    )


# ---------------------------------------------------------------------------
# Event schema round-trip
# ---------------------------------------------------------------------------


class TestEventRoundTrip:
    def test_order_approved_close_fields_round_trip(self):
        pos_id = uuid.uuid4()
        ev = OrderApprovedEvent(
            timestamp_us=_now_us(),
            source_service="pnl",
            profile_id="p-1",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            quantity=Decimal("0.5"),
            price=Decimal("50000"),
            order_id=uuid.uuid4(),
            reduce_only=True,
            close_position_id=pos_id,
            close_reason="stop_loss",
        )
        decoded = decode_event(encode_event(ev))
        assert decoded.reduce_only is True
        assert decoded.close_position_id == pos_id
        assert decoded.close_reason == "stop_loss"

    def test_executed_close_fields_round_trip(self):
        pos_id = uuid.uuid4()
        ev = OrderExecutedEvent(
            timestamp_us=_now_us(),
            source_service="execution",
            order_id=uuid.uuid4(),
            profile_id="p-1",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            fill_price=Decimal("49950"),
            quantity=Decimal("0.5"),
            reduce_only=True,
            close_position_id=pos_id,
            close_reason="take_profit",
        )
        decoded = decode_event(encode_event(ev))
        assert decoded.reduce_only is True
        assert decoded.close_position_id == pos_id
        assert decoded.close_reason == "take_profit"

    def test_legacy_message_without_close_fields_defaults(self):
        """A pre-PR1 OrderApprovedEvent (no reduce_only/close_*) must decode with
        safe defaults so a rolling restart / stream backlog stays compatible."""
        raw = {
            "__type__": "OrderApprovedEvent",
            "event_type": "ORDER_APPROVED",
            "timestamp_us": _now_us(),
            "source_service": "hot_path",
            "profile_id": "p-1",
            "symbol": "BTC/USDT",
            "side": "BUY",
            "quantity": "0.5",
            "price": "50000",
        }
        decoded = decode_event(msgpack.packb(raw, use_bin_type=True, default=str))
        assert decoded.reduce_only is False
        assert decoded.close_position_id is None
        assert decoded.close_reason is None


# ---------------------------------------------------------------------------
# PositionCloseRequester
# ---------------------------------------------------------------------------


class TestPositionCloseRequester:
    @pytest.mark.asyncio
    async def test_publishes_one_reduce_only_order_opposite_side(self):
        position = _position(side=OrderSide.BUY)
        repo = AsyncMock()
        repo.begin_close = AsyncMock(return_value=True)
        publisher = AsyncMock()
        publisher.publish = AsyncMock()

        requester = PositionCloseRequester(repo, publisher)
        close_order_id = await requester.request_close(
            position, Decimal("50500"), close_reason="stop_loss"
        )

        assert close_order_id is not None
        repo.begin_close.assert_awaited_once_with(position.position_id, close_order_id)
        publisher.publish.assert_awaited_once()
        channel, event = (
            publisher.publish.call_args.args[0],
            publisher.publish.call_args.args[1],
        )
        assert channel == ORDERS_STREAM
        assert event.reduce_only is True
        assert event.side == OrderSide.SELL  # closing a long
        assert event.close_position_id == position.position_id
        assert event.order_id == close_order_id
        assert event.quantity == position.quantity
        assert event.close_reason == "stop_loss"

    @pytest.mark.asyncio
    async def test_short_position_closes_with_buy(self):
        position = _position(side=OrderSide.SELL)
        repo = AsyncMock()
        repo.begin_close = AsyncMock(return_value=True)
        publisher = AsyncMock()
        requester = PositionCloseRequester(repo, publisher)
        await requester.request_close(position, Decimal("50500"))
        event = publisher.publish.call_args.args[1]
        assert event.side == OrderSide.BUY  # closing a short

    @pytest.mark.asyncio
    async def test_lost_cas_publishes_nothing(self):
        """If begin_close loses the CAS (already closing/closed), no order is
        published and None is returned — idempotency guard."""
        position = _position()
        repo = AsyncMock()
        repo.begin_close = AsyncMock(return_value=False)
        publisher = AsyncMock()
        requester = PositionCloseRequester(repo, publisher)
        result = await requester.request_close(position, Decimal("50500"))
        assert result is None
        publisher.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# PositionRepository CAS wrappers
# ---------------------------------------------------------------------------


class TestPositionRepoCAS:
    def _repo(self, fetchrow_return):
        from libs.storage.repositories.position_repo import PositionRepository

        db = MagicMock()
        db.fetchrow = AsyncMock(return_value=fetchrow_return)
        return PositionRepository(db), db

    @pytest.mark.asyncio
    async def test_begin_close_true_when_row_returned(self):
        repo, _ = self._repo({"position_id": uuid.uuid4()})
        assert await repo.begin_close(uuid.uuid4(), uuid.uuid4()) is True

    @pytest.mark.asyncio
    async def test_begin_close_false_when_no_row(self):
        repo, _ = self._repo(None)
        assert await repo.begin_close(uuid.uuid4(), uuid.uuid4()) is False

    @pytest.mark.asyncio
    async def test_finalize_close_true_false(self):
        repo, _ = self._repo({"position_id": uuid.uuid4()})
        assert await repo.finalize_close(uuid.uuid4(), Decimal("100")) is True
        repo2, _ = self._repo(None)
        assert await repo2.finalize_close(uuid.uuid4(), Decimal("100")) is False

    @pytest.mark.asyncio
    async def test_revert_close_true_false(self):
        repo, _ = self._repo({"position_id": uuid.uuid4()})
        assert await repo.revert_close(uuid.uuid4()) is True
        repo2, _ = self._repo(None)
        assert await repo2.revert_close(uuid.uuid4()) is False


# ---------------------------------------------------------------------------
# PositionCloser.finalize_close
# ---------------------------------------------------------------------------


def _make_finalize_closer(finalize_returns: bool):
    position_repo = AsyncMock()
    position_repo.finalize_close = AsyncMock(return_value=finalize_returns)

    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=None)
    redis_client.delete = AsyncMock(return_value=1)
    today = datetime.now(timezone.utc).date().isoformat()
    redis_client.hget = AsyncMock(return_value=today.encode())
    redis_client.hset = AsyncMock(return_value=1)
    redis_client.hincrby = AsyncMock(return_value=1)

    ctr = AsyncMock()
    ctr.write_closed_trade = AsyncMock()

    closer = PositionCloser(
        position_repo=position_repo,
        redis_client=redis_client,
        closed_trade_repo=ctr,
        profile_repo=None,
    )
    closer._tracker = AsyncMock()
    return closer, position_repo, redis_client, ctr


class TestFinalizeClose:
    @pytest.mark.asyncio
    async def test_uses_fill_price_and_records_once(self):
        closer, position_repo, redis_client, ctr = _make_finalize_closer(True)
        position = _position(side=OrderSide.BUY)

        snapshot = await closer.finalize_close(
            position,
            exit_price=Decimal("51000"),
            taker_rate=Decimal("0.001"),
            close_reason="exchange_close",
        )

        assert snapshot is not None
        position_repo.finalize_close.assert_awaited_once_with(
            position.position_id, Decimal("51000")
        )
        # closed_trades written with the fill price as exit_price
        ctr.write_closed_trade.assert_awaited_once()
        assert ctr.write_closed_trade.call_args.kwargs["exit_price"] == Decimal("51000")
        # daily-PnL bumped exactly once; agent EWMA tagged
        redis_client.hincrby.assert_awaited_once()
        closer._tracker.record_position_close.assert_not_called()  # no snapshot agents

    @pytest.mark.asyncio
    async def test_noop_when_cas_already_finalised(self):
        """A duplicate fill delivery must not double-write the ledger or
        double-bump the daily counter."""
        closer, position_repo, redis_client, ctr = _make_finalize_closer(False)
        position = _position()

        snapshot = await closer.finalize_close(
            position,
            exit_price=Decimal("51000"),
            taker_rate=Decimal("0.001"),
        )

        assert snapshot is None
        ctr.write_closed_trade.assert_not_awaited()
        redis_client.hincrby.assert_not_awaited()
        closer._tracker.record_position_close.assert_not_called()


# ---------------------------------------------------------------------------
# PaperTradingAdapter reduce-only fill
# ---------------------------------------------------------------------------


class TestPaperReduceOnly:
    @pytest.mark.asyncio
    async def test_sell_close_fills_below_mark(self):
        from libs.exchange._paper import PaperTradingAdapter

        adapter = PaperTradingAdapter()
        res = await adapter.place_order(
            "p-1",
            "BTC/USDT",
            OrderSide.SELL,
            Decimal("0.5"),
            Decimal("50000"),
            reduce_only=True,
        )
        from libs.core.enums import OrderStatus

        assert res.status == OrderStatus.CONFIRMED
        assert res.fill_price < Decimal("50000")  # SELL slips down

    @pytest.mark.asyncio
    async def test_buy_close_fills_above_mark(self):
        from libs.exchange._paper import PaperTradingAdapter

        adapter = PaperTradingAdapter()
        res = await adapter.place_order(
            "p-1",
            "BTC/USDT",
            OrderSide.BUY,
            Decimal("0.5"),
            Decimal("50000"),
            reduce_only=True,
        )
        assert res.fill_price > Decimal("50000")  # BUY slips up

    @pytest.mark.asyncio
    async def test_protective_order_is_noop(self):
        from libs.exchange._paper import PaperTradingAdapter

        adapter = PaperTradingAdapter()
        res = await adapter.place_protective_order(
            "p-1",
            "BTC/USDT",
            OrderSide.SELL,
            Decimal("0.5"),
            Decimal("47500"),
        )
        assert res is None


# ---------------------------------------------------------------------------
# ExecutedEventConsumer
# ---------------------------------------------------------------------------


def _rec_for(position: Position) -> dict:
    return {
        "position_id": position.position_id,
        "profile_id": str(position.profile_id),
        "symbol": position.symbol,
        "side": position.side.value,
        "entry_price": str(position.entry_price),
        "quantity": str(position.quantity),
        "entry_fee": str(position.entry_fee),
        "opened_at": position.opened_at,
        "status": "PENDING_CLOSE",
        "order_id": position.order_id,
        "decision_event_id": position.decision_event_id,
    }


class TestExecutedEventConsumer:
    def _consumer(self):
        position_repo = AsyncMock()
        closer = AsyncMock()
        closer.finalize_close = AsyncMock(
            return_value=SimpleNamespace(net_pre_tax=Decimal("100"))
        )
        pubsub = AsyncMock()
        consumer = ExecutedEventConsumer(
            AsyncMock(), position_repo, closer, pubsub=pubsub
        )
        return consumer, position_repo, closer, pubsub

    @pytest.mark.asyncio
    async def test_fill_finalises_with_fill_price(self):
        consumer, position_repo, closer, _ = self._consumer()
        position = _position()
        position_repo.get_by_id = AsyncMock(return_value=_rec_for(position))

        ev = OrderExecutedEvent(
            timestamp_us=_now_us(),
            source_service="execution",
            order_id=uuid.uuid4(),
            profile_id=str(position.profile_id),
            symbol=position.symbol,
            side=OrderSide.SELL,
            fill_price=Decimal("49950"),
            quantity=position.quantity,
            reduce_only=True,
            close_position_id=position.position_id,
            close_reason="stop_loss",
        )
        await consumer._handle(ev)

        position_repo.get_by_id.assert_awaited_once_with(position.position_id)
        closer.finalize_close.assert_awaited_once()
        kwargs = closer.finalize_close.call_args.kwargs
        assert kwargs["exit_price"] == Decimal("49950")
        assert kwargs["close_reason"] == "stop_loss"

    @pytest.mark.asyncio
    async def test_non_reduce_only_executed_ignored(self):
        consumer, position_repo, closer, _ = self._consumer()
        position_repo.get_by_id = AsyncMock()
        ev = OrderExecutedEvent(
            timestamp_us=_now_us(),
            source_service="execution",
            order_id=uuid.uuid4(),
            profile_id="p-1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            fill_price=Decimal("50000"),
            quantity=Decimal("0.5"),
        )
        await consumer._handle(ev)
        position_repo.get_by_id.assert_not_awaited()
        closer.finalize_close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_fill_skipped(self):
        consumer, position_repo, closer, _ = self._consumer()
        position_repo.get_by_id = AsyncMock()
        old_us = int(
            (
                datetime.now(timezone.utc) - timedelta(seconds=MAX_EVENT_AGE_S + 30)
            ).timestamp()
            * 1_000_000
        )
        ev = OrderExecutedEvent(
            timestamp_us=old_us,
            source_service="execution",
            order_id=uuid.uuid4(),
            profile_id="p-1",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            fill_price=Decimal("49950"),
            quantity=Decimal("0.5"),
            reduce_only=True,
            close_position_id=uuid.uuid4(),
        )
        await consumer._handle(ev)
        position_repo.get_by_id.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reject_reverts_and_alerts(self):
        consumer, position_repo, _, pubsub = self._consumer()
        position_repo.revert_close = AsyncMock(return_value=True)
        pos_id = uuid.uuid4()
        ev = OrderRejectedEvent(
            timestamp_us=_now_us(),
            source_service="execution",
            profile_id="p-1",
            symbol="BTC/USDT",
            reason="insufficient balance",
            order_id=uuid.uuid4(),
            reduce_only=True,
            close_position_id=pos_id,
        )
        await consumer._handle(ev)
        position_repo.revert_close.assert_awaited_once_with(pos_id)
        pubsub.publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# ExitMonitor routes through the requester
# ---------------------------------------------------------------------------


class TestExitMonitorRouting:
    @pytest.mark.asyncio
    async def test_stop_loss_routes_through_requester(self, monkeypatch):
        # Profile with a 5% stop-loss; a 10% loss should trip it.
        profile_repo = AsyncMock()
        profile_repo.get_profile = AsyncMock(
            return_value={
                "risk_limits": '{"stop_loss_pct": 0.05}',
            }
        )
        closer = AsyncMock()
        requester = AsyncMock()
        requester.request_close = AsyncMock(return_value=uuid.uuid4())

        # EXCHANGE_CLOSE_ENABLED defaults True; assert explicitly for clarity.
        from libs.config import settings as _settings

        monkeypatch.setattr(_settings, "EXCHANGE_CLOSE_ENABLED", True)

        monitor = ExitMonitor(closer, profile_repo, close_requester=requester)
        position = _position(side=OrderSide.BUY)
        snapshot = SimpleNamespace(pct_return=Decimal("-0.10"))

        closed, reason = await monitor.check(
            position, snapshot, Decimal("45000"), Decimal("0.001")
        )

        assert closed is True
        assert reason == "stop_loss"
        requester.request_close.assert_awaited_once()
        closer.close.assert_not_awaited()  # real-close path, not legacy
