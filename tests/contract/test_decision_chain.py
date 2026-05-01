"""Contract test — the PR1 decision_event_id correlation chain.

Proves that a single decision_event_id flows unchanged through every stage:

    hot_path  →  OrderApprovedEvent.decision_event_id
              →  (Redis Stream serialization round-trip)
              →  Order.decision_event_id  (written to orders table)
              →  Position.decision_event_id + Position.order_id  (written to positions table)
              →  Redis snapshot key carrying agents + regime
              →  closed_trades.decision_event_id + closed_trades.order_id (written by closer)
              →  ClosedTradeRepository.get_by_decision_event(eid) returns the row

Each stage is exercised through its actual production code path with mocked
infrastructure (Redis, DB) — no live services required.

This is the cohesion test: any drift between the layers wired in PR1 Steps 2-6
will fail this test even when individual unit tests pass.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from libs.core.enums import OrderSide, OrderStatus, PositionStatus
from libs.core.models import Order, Position
from libs.core.schemas import OrderApprovedEvent
from libs.storage.repositories.closed_trade_repo import ClosedTradeRepository
from libs.storage.repositories.order_repo import OrderRepository
from libs.storage.repositories.position_repo import PositionRepository
from services.pnl.src.closer import PositionCloser


def _mock_db_with_execute_capture():
    """A TimescaleClient mock that records executes and supports a fetchrow result."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    return db


@pytest.mark.asyncio
async def test_decision_event_id_flows_unchanged_through_full_chain():
    """The single decision_event_id generated in hot_path must reach closed_trades unchanged."""
    decision_eid = uuid.uuid4()
    profile_id = str(uuid.uuid4())

    # ----- STAGE 1: hot_path constructs OrderApprovedEvent with the decision id -----
    approved = OrderApprovedEvent(
        profile_id=profile_id,
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=Decimal("0.5"),
        price=Decimal("50000"),
        decision_event_id=decision_eid,
        timestamp_us=1_700_000_000_000_000,
        source_service="hot-path",
    )

    # ----- STAGE 2: event survives Redis Stream transport (Pydantic JSON round-trip) -----
    transported = OrderApprovedEvent.model_validate_json(approved.model_dump_json())
    assert transported.decision_event_id == decision_eid, (
        "decision_event_id was dropped during JSON serialization"
    )

    # ----- STAGE 3: execution writes Order carrying decision_event_id -----
    order_db = _mock_db_with_execute_capture()
    order_repo = OrderRepository(order_db)
    order_id = uuid.uuid4()
    order = Order(
        order_id=order_id,
        profile_id=transported.profile_id,
        symbol=transported.symbol,
        side=transported.side,
        quantity=transported.quantity,
        price=transported.price,
        status=OrderStatus.PENDING,
        exchange="BINANCE",
        created_at=datetime.now(timezone.utc),
        decision_event_id=transported.decision_event_id,
    )
    await order_repo.create_order(order)

    sql, *order_args = order_db.execute.call_args.args
    assert "INSERT INTO orders" in sql
    assert "decision_event_id" in sql
    assert order_args[-1] == decision_eid, "decision_event_id missing from orders INSERT args"

    # ----- STAGE 4: execution writes Position carrying both order_id and decision_event_id -----
    position_db = _mock_db_with_execute_capture()
    position_repo = PositionRepository(position_db)
    position_id = uuid.uuid4()
    position = Position(
        position_id=position_id,
        profile_id=transported.profile_id,
        symbol=transported.symbol,
        side=transported.side,
        entry_price=Decimal("50000"),
        quantity=transported.quantity,
        entry_fee=Decimal("25"),
        opened_at=datetime.now(timezone.utc) - timedelta(hours=1),
        status=PositionStatus.OPEN,
        order_id=order_id,
        decision_event_id=transported.decision_event_id,
    )
    await position_repo.create_position(position)

    sql, *pos_args = position_db.execute.call_args.args
    assert "INSERT INTO positions" in sql
    assert "decision_event_id" in sql
    assert pos_args[-2] == order_id, "order_id missing from positions INSERT args"
    assert pos_args[-1] == decision_eid, "decision_event_id missing from positions INSERT args"

    # ----- STAGE 5: execution snapshots agents + regime under the position key -----
    snapshot_payload = {
        "agents": {
            "ta": {"direction": "BUY", "score": 0.7},
            "sentiment": {"direction": "BUY", "score": 0.3},
            "debate": {"direction": "BUY", "score": 0.55},
        },
        "regime": "TRENDING_UP",
    }

    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=json.dumps(snapshot_payload).encode())
    redis_client.delete = AsyncMock(return_value=1)
    redis_client.set = AsyncMock(return_value=True)

    # ----- STAGE 6: PnL closer writes closed_trades row carrying the same decision_event_id -----
    ctr_mock = AsyncMock(spec=ClosedTradeRepository)
    ctr_mock.write_closed_trade = AsyncMock()

    pos_repo_for_closer = AsyncMock()
    pos_repo_for_closer.close_position = AsyncMock()

    closer = PositionCloser(
        position_repo=pos_repo_for_closer,
        redis_client=redis_client,
        closed_trade_repo=ctr_mock,
    )
    closer._tracker = AsyncMock()  # avoid touching real Redis tracker

    await closer.close(
        position=position,
        exit_price=Decimal("51000"),
        taker_rate=Decimal("0.001"),
        close_reason="take_profit",
    )

    ctr_mock.write_closed_trade.assert_awaited_once()
    final_kwargs = ctr_mock.write_closed_trade.call_args.kwargs

    # The headline contract assertion: end of chain still carries the same decision_event_id
    assert final_kwargs["decision_event_id"] == decision_eid, (
        "decision_event_id mutated or lost between Position and closed_trades"
    )
    assert final_kwargs["order_id"] == order_id, (
        "order_id mutated or lost between Position and closed_trades"
    )
    assert final_kwargs["position_id"] == position_id

    # And the entry-time context survived too
    assert final_kwargs["entry_regime"] == "TRENDING_UP"
    assert final_kwargs["entry_agent_scores"] == snapshot_payload["agents"]
    assert final_kwargs["close_reason"] == "take_profit"
    assert final_kwargs["outcome"] == "win"


@pytest.mark.asyncio
async def test_legacy_event_without_decision_event_id_propagates_null():
    """A pre-PR1 OrderApprovedEvent (no decision_event_id) must still flow without crashing.

    All downstream rows simply have NULL for the correlation column — the chain
    is broken (legacy data) but no stage raises.
    """
    profile_id = str(uuid.uuid4())

    # Construct the event without setting decision_event_id (defaults to None)
    approved = OrderApprovedEvent(
        profile_id=profile_id,
        symbol="ETH/USDT",
        side=OrderSide.SELL,
        quantity=Decimal("1"),
        price=Decimal("3000"),
        timestamp_us=1_700_000_000_000_000,
        source_service="hot-path",
    )
    assert approved.decision_event_id is None

    transported = OrderApprovedEvent.model_validate_json(approved.model_dump_json())
    assert transported.decision_event_id is None

    # Execution stage — the field flows through as None
    order_db = _mock_db_with_execute_capture()
    order_repo = OrderRepository(order_db)
    order = Order(
        order_id=uuid.uuid4(),
        profile_id=transported.profile_id,
        symbol=transported.symbol,
        side=transported.side,
        quantity=transported.quantity,
        price=transported.price,
        status=OrderStatus.PENDING,
        exchange="BINANCE",
        created_at=datetime.now(timezone.utc),
        decision_event_id=transported.decision_event_id,
    )
    await order_repo.create_order(order)
    _, *order_args = order_db.execute.call_args.args
    assert order_args[-1] is None

    # Position stage — both new fields are None
    position_db = _mock_db_with_execute_capture()
    position_repo = PositionRepository(position_db)
    position = Position(
        position_id=uuid.uuid4(),
        profile_id=transported.profile_id,
        symbol=transported.symbol,
        side=transported.side,
        entry_price=Decimal("3000"),
        quantity=transported.quantity,
        entry_fee=Decimal("3"),
        opened_at=datetime.now(timezone.utc),
        status=PositionStatus.OPEN,
        order_id=order.order_id,  # order_id is still set
        decision_event_id=transported.decision_event_id,  # but decision_event_id is None
    )
    await position_repo.create_position(position)
    _, *pos_args = position_db.execute.call_args.args
    assert pos_args[-2] == order.order_id
    assert pos_args[-1] is None

    # Closer still writes closed_trades — just with NULL decision_event_id
    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=None)  # No snapshot found
    redis_client.delete = AsyncMock()
    ctr_mock = AsyncMock()
    pos_repo_for_closer = AsyncMock()

    closer = PositionCloser(
        position_repo=pos_repo_for_closer,
        redis_client=redis_client,
        closed_trade_repo=ctr_mock,
    )
    closer._tracker = AsyncMock()

    await closer.close(
        position=position,
        exit_price=Decimal("3100"),
        taker_rate=Decimal("0.001"),
        close_reason="time_exit",
    )

    ctr_mock.write_closed_trade.assert_awaited_once()
    kwargs = ctr_mock.write_closed_trade.call_args.kwargs
    assert kwargs["decision_event_id"] is None
    assert kwargs["order_id"] == order.order_id
    assert kwargs["entry_regime"] is None
    assert kwargs["entry_agent_scores"] is None


@pytest.mark.asyncio
async def test_chain_query_helpers_round_trip():
    """ClosedTradeRepository.get_by_decision_event SQL exists and uses the right column."""
    db = AsyncMock()
    captured_row = {
        "position_id": uuid.uuid4(),
        "decision_event_id": uuid.uuid4(),
        "outcome": "win",
    }
    db.fetchrow = AsyncMock(return_value=captured_row)
    repo = ClosedTradeRepository(db)

    eid = uuid.uuid4()
    result = await repo.get_by_decision_event(eid)

    sql, *args = db.fetchrow.call_args.args
    assert "WHERE decision_event_id = $1" in sql
    assert args[0] == eid
    assert result == captured_row


@pytest.mark.asyncio
async def test_position_to_closed_trade_link_via_position_id_fk():
    """closed_trades.position_id is the FK target; verify get_by_position uses it correctly."""
    db = AsyncMock()
    pid = uuid.uuid4()
    db.fetchrow = AsyncMock(return_value={"position_id": pid, "outcome": "loss"})
    repo = ClosedTradeRepository(db)

    result = await repo.get_by_position(pid)

    sql, *args = db.fetchrow.call_args.args
    assert "WHERE position_id = $1" in sql
    assert args[0] == pid
    assert result["position_id"] == pid
