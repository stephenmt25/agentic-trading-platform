"""Unit tests for PositionCloser closed_trades ledger write (PR1 Step 5).

Verifies:
  - _get_position_snapshot handles both new and legacy Redis payloads
  - _write_closed_trade_row delegates to the repo with correct params
  - close() invokes the ledger write before the tracker EWMA update
  - Failures in the closed_trade_repo write never disrupt the close path
  - Backward compat: closer still works when closed_trade_repo is None
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.core.enums import OrderSide, PositionStatus
from libs.core.models import Position
from services.pnl.src.closer import PositionCloser


def _make_position(decision_event_id=None, order_id=None):
    return Position(
        position_id=uuid.uuid4(),
        profile_id=str(uuid.uuid4()),
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        entry_price=Decimal("50000"),
        quantity=Decimal("0.5"),
        entry_fee=Decimal("25"),
        opened_at=datetime.now(timezone.utc) - timedelta(hours=1),
        status=PositionStatus.OPEN,
        order_id=order_id,
        decision_event_id=decision_event_id,
    )


def _make_closer(closed_trade_repo=None, snapshot_payload=None):
    position_repo = AsyncMock()
    position_repo.close_position = AsyncMock()

    redis_client = AsyncMock()
    if snapshot_payload is None:
        redis_client.get = AsyncMock(return_value=None)
    else:
        redis_client.get = AsyncMock(return_value=json.dumps(snapshot_payload).encode())
    redis_client.delete = AsyncMock(return_value=1)
    # Pre-seed hget so closer._bump_daily_realised_pnl reads today's date
    # (skipping the day-rollover branch that would call delete a second time).
    # Tests that want to exercise day-rollover should override this on the
    # specific redis_client instance.
    today_iso = datetime.now(timezone.utc).date().isoformat()
    redis_client.hget = AsyncMock(return_value=today_iso.encode())
    redis_client.hset = AsyncMock(return_value=1)
    redis_client.hincrby = AsyncMock(return_value=1)

    closer = PositionCloser(
        position_repo=position_repo,
        redis_client=redis_client,
        closed_trade_repo=closed_trade_repo,
    )
    return closer, position_repo, redis_client


# ---------------------------------------------------------------------------
# _get_position_snapshot
# ---------------------------------------------------------------------------

class TestGetPositionSnapshot:
    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self):
        closer, _, _ = _make_closer(snapshot_payload=None)
        agents, regime = await closer._get_position_snapshot("p1")
        assert agents is None
        assert regime is None

    @pytest.mark.asyncio
    async def test_new_format_extracts_agents_and_regime(self):
        payload = {
            "agents": {"ta": {"score": 0.7}, "debate": {"score": 0.55}},
            "regime": "TRENDING_UP",
        }
        closer, _, _ = _make_closer(snapshot_payload=payload)
        agents, regime = await closer._get_position_snapshot("p1")
        assert agents == {"ta": {"score": 0.7}, "debate": {"score": 0.55}}
        assert regime == "TRENDING_UP"

    @pytest.mark.asyncio
    async def test_legacy_flat_dict_payload_returns_no_regime(self):
        """Snapshots written before PR1 stored agents at the top level with no regime."""
        payload = {"ta": {"score": 0.6}, "sentiment": {"score": 0.2}}
        closer, _, _ = _make_closer(snapshot_payload=payload)
        agents, regime = await closer._get_position_snapshot("p1")
        assert agents == {"ta": {"score": 0.6}, "sentiment": {"score": 0.2}}
        assert regime is None

    @pytest.mark.asyncio
    async def test_redis_failure_returns_none_pair(self):
        closer, _, redis_client = _make_closer()
        redis_client.get = AsyncMock(side_effect=Exception("redis down"))
        agents, regime = await closer._get_position_snapshot("p1")
        assert agents is None
        assert regime is None


# ---------------------------------------------------------------------------
# close() — full flow
# ---------------------------------------------------------------------------

class TestCloseEndToEnd:
    @pytest.mark.asyncio
    async def test_writes_closed_trade_with_full_lineage(self):
        decision_event_id = uuid.uuid4()
        order_id = uuid.uuid4()
        position = _make_position(decision_event_id=decision_event_id, order_id=order_id)

        snapshot_payload = {
            "agents": {"ta": {"score": 0.8}, "debate": {"score": 0.6}},
            "regime": "TRENDING_UP",
        }
        ctr = AsyncMock()
        ctr.write_closed_trade = AsyncMock()

        closer, position_repo, _ = _make_closer(closed_trade_repo=ctr, snapshot_payload=snapshot_payload)
        # Stub tracker so it doesn't try to talk to Redis
        closer._tracker = AsyncMock()

        exit_price = Decimal("51000")  # +2% before fees
        taker_rate = Decimal("0.001")
        await closer.close(position, exit_price=exit_price, taker_rate=taker_rate, close_reason="take_profit")

        # 1. Position was closed in DB
        position_repo.close_position.assert_awaited_once_with(position.position_id, exit_price)

        # 2. closed_trades row was written with correct lineage
        ctr.write_closed_trade.assert_awaited_once()
        kwargs = ctr.write_closed_trade.call_args.kwargs
        assert kwargs["position_id"] == position.position_id
        assert kwargs["decision_event_id"] == decision_event_id
        assert kwargs["order_id"] == order_id
        assert kwargs["symbol"] == "BTC/USDT"
        assert kwargs["side"] == "BUY"
        assert kwargs["entry_price"] == Decimal("50000")
        assert kwargs["entry_quantity"] == Decimal("0.5")
        assert kwargs["entry_regime"] == "TRENDING_UP"
        assert kwargs["entry_agent_scores"] == snapshot_payload["agents"]
        assert kwargs["exit_price"] == exit_price
        assert kwargs["close_reason"] == "take_profit"
        assert kwargs["outcome"] == "win"
        # Sanity: holding duration is ~1 hour
        assert 3500 <= kwargs["holding_duration_s"] <= 3700
        # exit_fee = exit_price * qty * taker_rate = 51000 * 0.5 * 0.001 = 25.5
        assert kwargs["exit_fee"] == Decimal("25.5")

        # 3. Tracker received the outcome too (existing behavior preserved)
        closer._tracker.record_position_close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_outcome_loss_when_negative_pnl(self):
        position = _make_position()
        ctr = AsyncMock()
        closer, _, _ = _make_closer(
            closed_trade_repo=ctr,
            snapshot_payload={"agents": {"ta": {"score": 0.5}}, "regime": "RANGING"},
        )
        closer._tracker = AsyncMock()
        # Exit at 49000 → loss
        await closer.close(position, exit_price=Decimal("49000"), taker_rate=Decimal("0.001"), close_reason="stop_loss")
        kwargs = ctr.write_closed_trade.call_args.kwargs
        assert kwargs["outcome"] == "loss"
        assert kwargs["close_reason"] == "stop_loss"

    @pytest.mark.asyncio
    async def test_works_without_closed_trade_repo(self):
        """Backward compat: omitting the repo silently skips ledger write."""
        position = _make_position()
        closer, position_repo, _ = _make_closer(closed_trade_repo=None)
        closer._tracker = AsyncMock()
        # Should not raise
        await closer.close(position, exit_price=Decimal("50000"), taker_rate=Decimal("0.001"))
        position_repo.close_position.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_closed_trade_repo_failure_does_not_raise(self):
        """A DB failure on the audit write must not interrupt the rest of the close path."""
        position = _make_position()
        ctr = AsyncMock()
        ctr.write_closed_trade = AsyncMock(side_effect=Exception("db unavailable"))
        closer, position_repo, redis_client = _make_closer(
            closed_trade_repo=ctr,
            snapshot_payload={"agents": {"ta": {"score": 0.5}}, "regime": "RANGING"},
        )
        closer._tracker = AsyncMock()

        # Should complete without raising
        snapshot = await closer.close(position, exit_price=Decimal("51000"), taker_rate=Decimal("0.001"))
        assert snapshot is not None

        # Other steps still ran
        position_repo.close_position.assert_awaited_once()
        closer._tracker.record_position_close.assert_awaited_once()
        redis_client.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_with_no_snapshot_writes_null_agent_fields(self):
        """If Redis lost the snapshot (TTL expired, etc.), the closed_trade row still gets written."""
        position = _make_position(decision_event_id=uuid.uuid4(), order_id=uuid.uuid4())
        ctr = AsyncMock()
        closer, _, _ = _make_closer(closed_trade_repo=ctr, snapshot_payload=None)
        closer._tracker = AsyncMock()

        await closer.close(position, exit_price=Decimal("50000"), taker_rate=Decimal("0.001"))

        ctr.write_closed_trade.assert_awaited_once()
        kwargs = ctr.write_closed_trade.call_args.kwargs
        assert kwargs["entry_agent_scores"] is None
        assert kwargs["entry_regime"] is None
        # Tracker not called when no agent_scores (existing behavior)
        closer._tracker.record_position_close.assert_not_awaited()
