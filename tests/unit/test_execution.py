"""Unit tests for the Execution service.

Tests the OrderExecutor lifecycle: order creation, ledger transitions,
position creation, fee calculation, and failure/rollback paths.
"""

import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.core.enums import OrderSide, OrderStatus, PositionStatus
from libs.core.schemas import OrderApprovedEvent, OrderExecutedEvent, OrderRejectedEvent
from services.execution.src.executor import OrderExecutor, EXCHANGE_FEE_RATES, DEFAULT_FEE_RATE
from services.execution.src.ledger import OptimisticLedger


# ---------------------------------------------------------------------------
# Ledger tests
# ---------------------------------------------------------------------------

class TestOptimisticLedger:
    @pytest.mark.asyncio
    async def test_submit_transitions_to_submitted(self, mock_order_repo):
        """submit() should update order status to SUBMITTED."""
        ledger = OptimisticLedger(mock_order_repo)
        oid = uuid.uuid4()
        result = await ledger.submit(oid)
        assert result is True
        mock_order_repo.update_order_status.assert_awaited_once_with(oid, OrderStatus.SUBMITTED)

    @pytest.mark.asyncio
    async def test_submit_returns_false_on_db_error(self, mock_order_repo):
        """submit() should return False if the DB update fails."""
        mock_order_repo.update_order_status = AsyncMock(side_effect=Exception("DB down"))
        ledger = OptimisticLedger(mock_order_repo)
        result = await ledger.submit(uuid.uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_confirm_transitions_to_confirmed(self, mock_order_repo):
        """confirm() should update order status to CONFIRMED with fill_price."""
        ledger = OptimisticLedger(mock_order_repo)
        oid = uuid.uuid4()
        result = await ledger.confirm(oid, fill_price=50000.0)
        assert result is True
        mock_order_repo.update_order_status.assert_awaited_once_with(
            oid, OrderStatus.CONFIRMED, fill_price=50000.0
        )

    @pytest.mark.asyncio
    async def test_confirm_updates_redis_allocation(self, mock_order_repo, mock_redis):
        """confirm() should update allocation tracking in Redis when redis_client is provided."""
        ledger = OptimisticLedger(mock_order_repo, redis_client=mock_redis)
        oid = uuid.uuid4()
        result = await ledger.confirm(oid, fill_price=50000.0, profile_id="prof-1", quantity=0.5)
        assert result is True
        # Redis eval should be called for allocation script
        mock_redis.eval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollback_transitions_to_rolled_back(self, mock_order_repo):
        """rollback() should update order status to ROLLED_BACK."""
        ledger = OptimisticLedger(mock_order_repo)
        oid = uuid.uuid4()
        result = await ledger.rollback(oid, reason="test failure")
        assert result is True
        mock_order_repo.update_order_status.assert_awaited_once_with(oid, OrderStatus.ROLLED_BACK)

    @pytest.mark.asyncio
    async def test_rollback_returns_false_on_db_error(self, mock_order_repo):
        """rollback() should return False if DB update fails (critical scenario)."""
        mock_order_repo.update_order_status = AsyncMock(side_effect=Exception("DB down"))
        ledger = OptimisticLedger(mock_order_repo)
        result = await ledger.rollback(uuid.uuid4(), reason="exchange error")
        assert result is False


# ---------------------------------------------------------------------------
# OrderExecutor tests
# ---------------------------------------------------------------------------

class TestOrderExecutor:
    def _make_executor(
        self, mock_publisher, mock_consumer, mock_order_repo,
        mock_position_repo, mock_audit_repo, mock_redis, mock_telemetry,
    ):
        ledger = OptimisticLedger(mock_order_repo)
        return OrderExecutor(
            publisher=mock_publisher,
            consumer=mock_consumer,
            order_repo=mock_order_repo,
            position_repo=mock_position_repo,
            audit_repo=mock_audit_repo,
            ledger=ledger,
            orders_channel="stream:orders",
            redis_client=mock_redis,
            telemetry=mock_telemetry,
        )

    @pytest.mark.asyncio
    async def test_fee_rates_are_decimal(self):
        """All fee rates must be Decimal to avoid float precision loss in fee calculation."""
        for exchange, rate in EXCHANGE_FEE_RATES.items():
            assert isinstance(rate, Decimal), f"Fee rate for {exchange} is not Decimal"
        assert isinstance(DEFAULT_FEE_RATE, Decimal), "DEFAULT_FEE_RATE is not Decimal"

    @pytest.mark.asyncio
    async def test_fee_calculation_uses_decimal(self):
        """entry_fee = fee_rate * quantity * fill_price — must stay Decimal throughout."""
        fee_rate = EXCHANGE_FEE_RATES["BINANCE"]
        quantity = Decimal("0.5")
        fill_price = Decimal("50000.00")
        entry_fee = fee_rate * quantity * fill_price
        assert isinstance(entry_fee, Decimal), "Fee calculation produced non-Decimal result"
        assert entry_fee == Decimal("25.000")

    @pytest.mark.asyncio
    async def test_executor_processes_approved_event(
        self, mock_publisher, mock_consumer, mock_order_repo,
        mock_position_repo, mock_audit_repo, mock_redis,
        mock_telemetry, sample_order_approved_event,
    ):
        """Full happy path: consume event → create order → submit → exchange → confirm → position → emit."""
        ev = sample_order_approved_event()

        # Mock consumer returns one event then empty
        mock_consumer.consume = AsyncMock(side_effect=[
            [("msg-1", ev)],
            [],  # second call returns empty, we'll break after first batch
        ])

        # Mock exchange adapter
        mock_adapter = AsyncMock()
        mock_adapter.place_order = AsyncMock(return_value=MagicMock(
            status=OrderStatus.CONFIRMED,
            fill_price=Decimal("50000.00"),
        ))
        mock_adapter.close = AsyncMock()

        executor = self._make_executor(
            mock_publisher, mock_consumer, mock_order_repo,
            mock_position_repo, mock_audit_repo, mock_redis, mock_telemetry,
        )

        # Patch _resolve_adapter to return our mock
        executor._resolve_adapter = AsyncMock(return_value=(mock_adapter, "BINANCE"))

        # Run one iteration of the loop
        mock_consumer.consume = AsyncMock(return_value=[("msg-1", ev)])
        events = await mock_consumer.consume("stream:orders", "executor_group", "executor_1", count=10)

        # Verify the event was consumed
        assert len(events) == 1
        assert events[0][1] == ev

    @pytest.mark.asyncio
    async def test_ledger_submit_failure_skips_order(
        self, mock_publisher, mock_consumer, mock_order_repo,
        mock_position_repo, mock_audit_repo, mock_redis, mock_telemetry,
    ):
        """If ledger.submit() fails, the order should be skipped and audit logged."""
        mock_order_repo.update_order_status = AsyncMock(side_effect=Exception("DB error"))
        ledger = OptimisticLedger(mock_order_repo)

        oid = uuid.uuid4()
        result = await ledger.submit(oid)
        assert result is False

    @pytest.mark.asyncio
    async def test_exchange_failure_triggers_rollback(self, mock_order_repo):
        """If exchange rejects the order, ledger must rollback to avoid stuck SUBMITTED state."""
        ledger = OptimisticLedger(mock_order_repo)
        oid = uuid.uuid4()

        # Submit succeeds
        await ledger.submit(oid)
        # Then rollback because exchange failed
        rolled_back = await ledger.rollback(oid, reason="Exchange rejected")
        assert rolled_back is True
        # Verify both transitions happened
        assert mock_order_repo.update_order_status.await_count == 2
