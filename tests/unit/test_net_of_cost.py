"""Unit tests for PR5 — net-of-cost accounting (slippage attribution + funding placeholder).

Covers:
  - realized_slippage sign logic (adverse SELL/BUY, favorable, zero)
  - OrderExecutedEvent.slippage_cost round-trips through serialisation
  - PositionCloser.finalize_close threads slippage_cost into the closed_trades
    write, with funding_cost = 0 (spot)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from libs.core.enums import OrderSide, PositionStatus
from libs.core.models import Position
from libs.core.portfolio import realized_slippage
from libs.core.schemas import OrderExecutedEvent
from libs.messaging._serialisation import decode_event, encode_event
from services.pnl.src.closer import PositionCloser


class TestRealizedSlippage:
    def test_sell_below_intended_is_adverse_cost(self):
        # Sold at 49,975 vs intended 50,000 -> 25 * 1 = 25 cost
        assert realized_slippage(
            OrderSide.SELL, Decimal("50000"), Decimal("49975"), Decimal("1")
        ) == Decimal("25")

    def test_sell_above_intended_is_favorable(self):
        assert realized_slippage(
            OrderSide.SELL, Decimal("50000"), Decimal("50010"), Decimal("1")
        ) == Decimal("-10")

    def test_buy_above_intended_is_adverse_cost(self):
        assert realized_slippage(
            OrderSide.BUY, Decimal("50000"), Decimal("50025"), Decimal("2")
        ) == Decimal("50")

    def test_buy_below_intended_is_favorable(self):
        assert realized_slippage(
            OrderSide.BUY, Decimal("50000"), Decimal("49990"), Decimal("1")
        ) == Decimal("-10")

    def test_accepts_string_side(self):
        assert realized_slippage(
            "SELL", Decimal("100"), Decimal("99"), Decimal("1")
        ) == Decimal("1")


class TestExecutedEventSlippageRoundTrip:
    def test_slippage_cost_round_trips(self):
        ev = OrderExecutedEvent(
            timestamp_us=1,
            source_service="execution",
            order_id=uuid4(),
            profile_id="p-1",
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            fill_price=Decimal("49975"),
            quantity=Decimal("1"),
            reduce_only=True,
            close_position_id=uuid4(),
            slippage_cost=Decimal("25"),
        )
        decoded = decode_event(encode_event(ev))
        assert decoded.slippage_cost == Decimal("25")

    def test_legacy_executed_event_defaults_slippage_none(self):
        ev = OrderExecutedEvent(
            timestamp_us=1,
            source_service="execution",
            order_id=uuid4(),
            profile_id="p-1",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            fill_price=Decimal("50000"),
            quantity=Decimal("1"),
        )
        assert decode_event(encode_event(ev)).slippage_cost is None


class TestCloserThreadsSlippage:
    @pytest.mark.asyncio
    async def test_finalize_close_writes_slippage_and_zero_funding(self):
        position_repo = AsyncMock()
        position_repo.finalize_close = AsyncMock(return_value=True)
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        redis.hget = AsyncMock(
            return_value=datetime.now(timezone.utc).date().isoformat().encode()
        )
        redis.hset = AsyncMock(return_value=1)
        redis.hincrby = AsyncMock(return_value=1)
        ctr = AsyncMock()
        ctr.write_closed_trade = AsyncMock()

        closer = PositionCloser(
            position_repo, redis, closed_trade_repo=ctr, profile_repo=None
        )
        closer._tracker = AsyncMock()

        position = Position(
            position_id=uuid4(),
            profile_id=str(uuid4()),
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_price=Decimal("50000"),
            quantity=Decimal("1"),
            entry_fee=Decimal("50"),
            opened_at=datetime.now(timezone.utc) - timedelta(hours=1),
            status=PositionStatus.OPEN,
        )
        await closer.finalize_close(
            position,
            exit_price=Decimal("49975"),
            taker_rate=Decimal("0.001"),
            close_reason="exchange_close",
            slippage_cost=Decimal("25"),
        )

        ctr.write_closed_trade.assert_awaited_once()
        kwargs = ctr.write_closed_trade.call_args.kwargs
        assert kwargs["slippage_cost"] == Decimal("25")
        assert kwargs["funding_cost"] == Decimal("0")  # spot — no funding
