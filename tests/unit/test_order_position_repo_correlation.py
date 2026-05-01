"""Unit tests for the decision_event_id correlation fields added in PR1 Step 2.

Verifies OrderRepository.create_order and PositionRepository.create_position
correctly pass the new correlation columns through to SQL.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from libs.core.enums import OrderSide, OrderStatus, PositionStatus
from libs.core.models import Order, Position
from libs.storage.repositories.order_repo import OrderRepository
from libs.storage.repositories.position_repo import PositionRepository


def _make_order_repo():
    db = AsyncMock()
    db.execute = AsyncMock()
    return OrderRepository(db), db


def _make_position_repo():
    db = AsyncMock()
    db.execute = AsyncMock()
    return PositionRepository(db), db


def _make_order(decision_event_id=None):
    return Order(
        order_id=uuid.uuid4(),
        profile_id="test-profile-001",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.5"),
        price=Decimal("50000"),
        status=OrderStatus.PENDING,
        exchange="BINANCE",
        created_at=datetime.now(timezone.utc),
        decision_event_id=decision_event_id,
    )


def _make_position(order_id=None, decision_event_id=None):
    return Position(
        position_id=uuid.uuid4(),
        profile_id="test-profile-001",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        entry_price=Decimal("50000"),
        quantity=Decimal("0.5"),
        entry_fee=Decimal("25"),
        opened_at=datetime.now(timezone.utc),
        status=PositionStatus.OPEN,
        order_id=order_id,
        decision_event_id=decision_event_id,
    )


class TestOrderRepoDecisionLink:
    @pytest.mark.asyncio
    async def test_decision_event_id_is_inserted(self):
        repo, db = _make_order_repo()
        eid = uuid.uuid4()
        await repo.create_order(_make_order(decision_event_id=eid))

        sql, *args = db.execute.call_args.args
        assert "decision_event_id" in sql
        # Last positional arg should be the decision_event_id (10th value)
        assert args[-1] == eid

    @pytest.mark.asyncio
    async def test_null_decision_event_id_is_passed_through(self):
        repo, db = _make_order_repo()
        await repo.create_order(_make_order(decision_event_id=None))
        _, *args = db.execute.call_args.args
        assert args[-1] is None

    @pytest.mark.asyncio
    async def test_default_order_has_null_decision_event_id(self):
        """Order constructed without the new field should default to None."""
        order = Order(
            order_id=uuid.uuid4(),
            profile_id="p",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("100"),
            status=OrderStatus.PENDING,
            exchange="BINANCE",
            created_at=datetime.now(timezone.utc),
        )
        assert order.decision_event_id is None


class TestPositionRepoCorrelation:
    @pytest.mark.asyncio
    async def test_order_id_and_decision_event_id_inserted(self):
        repo, db = _make_position_repo()
        oid = uuid.uuid4()
        eid = uuid.uuid4()
        await repo.create_position(_make_position(order_id=oid, decision_event_id=eid))

        sql, *args = db.execute.call_args.args
        assert "order_id" in sql
        assert "decision_event_id" in sql
        # Order of args matches the INSERT: ..., status, order_id, decision_event_id
        assert args[-2] == oid
        assert args[-1] == eid

    @pytest.mark.asyncio
    async def test_nulls_pass_through(self):
        repo, db = _make_position_repo()
        await repo.create_position(_make_position(order_id=None, decision_event_id=None))
        _, *args = db.execute.call_args.args
        assert args[-2] is None
        assert args[-1] is None

    @pytest.mark.asyncio
    async def test_default_position_has_null_correlation_fields(self):
        """Position constructed without the new fields should default to None for both."""
        pos = Position(
            position_id=uuid.uuid4(),
            profile_id="p",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_price=Decimal("100"),
            quantity=Decimal("1"),
            entry_fee=Decimal("0"),
            opened_at=datetime.now(timezone.utc),
        )
        assert pos.order_id is None
        assert pos.decision_event_id is None
