"""Unit tests for PR3 — tiered kill-switch + flatten authority.

Covers:
  - FlattenAuthority gate: trigger counting, the >=2 + dwell rule, dwell reset
  - KillSwitch tiered level: backward-compat parsing, level round-trip, fail-safes
  - HaltController: FLATTEN closes all open positions (idempotent via the requester)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from libs.core.enums import HaltLevel
from libs.core.flatten_authority import FlattenAuthority
from services.hot_path.src.kill_switch import KillSwitch, _parse_level

# ---------------------------------------------------------------------------
# FlattenAuthority
# ---------------------------------------------------------------------------


class TestFlattenAuthority:
    def test_no_triggers_recommends_none(self):
        a = FlattenAuthority(dwell_seconds=30)
        d = a.evaluate({"drawdown": False, "drift": False, "crisis": False}, now=100.0)
        assert d.recommended_level == HaltLevel.NONE
        assert not d.auto_flatten_authorized
        assert not d.needs_human_flatten

    def test_single_trigger_automates_de_risk_only(self):
        a = FlattenAuthority(dwell_seconds=30)
        d = a.evaluate({"drawdown": True, "drift": False, "crisis": False}, now=100.0)
        assert d.recommended_level == HaltLevel.DE_RISK
        assert not d.auto_flatten_authorized
        assert not d.needs_human_flatten

    def test_two_triggers_within_dwell_is_de_risk_plus_human(self):
        a = FlattenAuthority(dwell_seconds=30)
        d = a.evaluate({"drawdown": True, "drift": True, "crisis": False}, now=100.0)
        # First time the >=2 condition holds — dwell not yet satisfied.
        assert d.recommended_level == HaltLevel.DE_RISK
        assert not d.auto_flatten_authorized
        assert d.needs_human_flatten
        assert d.active_triggers == ["drawdown", "drift"]

    def test_two_triggers_past_dwell_authorizes_flatten(self):
        a = FlattenAuthority(dwell_seconds=30)
        a.evaluate({"drawdown": True, "drift": True}, now=100.0)  # start dwell
        d = a.evaluate({"drawdown": True, "drift": True}, now=131.0)  # +31s
        assert d.recommended_level == HaltLevel.FLATTEN
        assert d.auto_flatten_authorized
        assert not d.needs_human_flatten

    def test_dwell_resets_when_triggers_drop(self):
        a = FlattenAuthority(dwell_seconds=30)
        a.evaluate({"drawdown": True, "drift": True}, now=100.0)
        a.evaluate({"drawdown": True, "drift": False}, now=110.0)  # drop to 1 -> reset
        # Back to 2 triggers, but the dwell clock restarts now.
        d = a.evaluate({"drawdown": True, "drift": True}, now=115.0)
        assert d.recommended_level == HaltLevel.DE_RISK
        assert not d.auto_flatten_authorized
        # Only authorized once 30s elapse from the restart (115).
        d2 = a.evaluate({"drawdown": True, "drift": True}, now=146.0)
        assert d2.auto_flatten_authorized


# ---------------------------------------------------------------------------
# KillSwitch tiered level
# ---------------------------------------------------------------------------


class TestParseLevel:
    def test_legacy_binary_is_stop_opening(self):
        assert _parse_level("1") == HaltLevel.STOP_OPENING
        assert _parse_level(b"true") == HaltLevel.STOP_OPENING

    def test_none_and_zero_are_none(self):
        assert _parse_level(None) == HaltLevel.NONE
        assert _parse_level("0") == HaltLevel.NONE
        assert _parse_level("NONE") == HaltLevel.NONE

    def test_named_levels(self):
        assert _parse_level("FLATTEN") == HaltLevel.FLATTEN
        assert _parse_level(b"DE_RISK") == HaltLevel.DE_RISK

    def test_unknown_is_conservative_stop_opening(self):
        assert _parse_level("garbage") == HaltLevel.STOP_OPENING


class TestKillSwitchLevel:
    def _redis(self, get_return):
        r = AsyncMock()
        r.get = AsyncMock(return_value=get_return)
        r.set = AsyncMock()
        r.delete = AsyncMock()
        r.lpush = AsyncMock()
        r.ltrim = AsyncMock()
        return r

    @pytest.mark.asyncio
    async def test_is_active_true_for_flatten(self):
        assert await KillSwitch.is_active(self._redis(b"FLATTEN")) is True

    @pytest.mark.asyncio
    async def test_is_active_false_for_none(self):
        assert await KillSwitch.is_active(self._redis(None)) is False

    @pytest.mark.asyncio
    async def test_is_active_failsafe_blocks(self):
        r = AsyncMock()
        r.get = AsyncMock(side_effect=Exception("redis down"))
        assert await KillSwitch.is_active(r) is True

    @pytest.mark.asyncio
    async def test_get_level_failsafe_non_destructive(self):
        """A Redis error must NOT report FLATTEN — that would auto-close everything
        on a transient blip. It returns STOP_OPENING (halt, but non-destructive)."""
        r = AsyncMock()
        r.get = AsyncMock(side_effect=Exception("redis down"))
        assert await KillSwitch.get_level(r) == HaltLevel.STOP_OPENING

    @pytest.mark.asyncio
    async def test_set_level_flatten_writes_value(self):
        r = self._redis(None)
        await KillSwitch.set_level(r, HaltLevel.FLATTEN, reason="test", actor="t")
        r.set.assert_awaited_once()
        assert r.set.call_args.args[1] == "FLATTEN"

    @pytest.mark.asyncio
    async def test_set_level_none_clears(self):
        r = self._redis(None)
        await KillSwitch.set_level(r, HaltLevel.NONE)
        r.delete.assert_awaited_once()
        r.set.assert_not_awaited()


# ---------------------------------------------------------------------------
# HaltController flatten action
# ---------------------------------------------------------------------------


def _pos_row(side="BUY"):
    return {
        "position_id": uuid.uuid4(),
        "profile_id": str(uuid.uuid4()),
        "symbol": "BTC/USDT",
        "side": side,
        "entry_price": "50000",
        "quantity": "1.0",
        "entry_fee": "0",
        "opened_at": datetime.now(timezone.utc),
        "status": "OPEN",
    }


class TestHaltController:
    @pytest.mark.asyncio
    async def test_flatten_all_open_closes_every_position(self):
        from services.pnl.src.halt_controller import HaltController

        position_repo = AsyncMock()
        position_repo.get_open_positions = AsyncMock(
            return_value=[_pos_row(), _pos_row()]
        )
        requester = AsyncMock()
        requester.request_close = AsyncMock(return_value=uuid.uuid4())

        hc = HaltController(AsyncMock(), position_repo, requester)
        n = await hc.flatten_all_open()

        assert n == 2
        assert requester.request_close.await_count == 2
        # close reason is tagged for the audit row
        assert (
            requester.request_close.call_args.kwargs["close_reason"] == "halt_flatten"
        )

    @pytest.mark.asyncio
    async def test_flatten_skips_positions_that_lose_the_cas(self):
        from services.pnl.src.halt_controller import HaltController

        position_repo = AsyncMock()
        position_repo.get_open_positions = AsyncMock(
            return_value=[_pos_row(), _pos_row()]
        )
        requester = AsyncMock()
        # One already closing -> request_close returns None
        requester.request_close = AsyncMock(side_effect=[uuid.uuid4(), None])

        hc = HaltController(AsyncMock(), position_repo, requester)
        assert await hc.flatten_all_open() == 1

    @pytest.mark.asyncio
    async def test_tick_executes_flatten_when_level_is_flatten(self):
        from services.pnl.src.halt_controller import HaltController

        position_repo = AsyncMock()
        position_repo.get_open_positions = AsyncMock(return_value=[_pos_row()])
        requester = AsyncMock()
        requester.request_close = AsyncMock(return_value=uuid.uuid4())
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)  # no triggers
        redis.hget = AsyncMock(return_value=None)

        hc = HaltController(redis, position_repo, requester, pubsub=AsyncMock())
        with patch(
            "services.pnl.src.halt_controller.KillSwitch.get_level",
            AsyncMock(return_value=HaltLevel.FLATTEN),
        ):
            await hc.tick(now=100.0)

        requester.request_close.assert_awaited_once()  # the open position was flattened
