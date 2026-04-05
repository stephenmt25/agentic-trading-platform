"""Unit tests for hot_path signal processing pipeline.

Tests abstention logic, kill switch gate, and regime dampener
integration with strategy evaluation.
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from libs.core.enums import Regime, SignalDirection
from libs.core.models import NormalisedTick
from services.hot_path.src.abstention import AbstentionChecker
from services.hot_path.src.kill_switch import KillSwitch, KILL_SWITCH_KEY
from services.hot_path.src.strategy_eval import SignalResult, EvaluatedIndicators


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_tick(symbol="BTC/USDT", price=50000.0, volume=1.0):
    return NormalisedTick(
        symbol=symbol, exchange="binance", timestamp=1000000,
        price=price, volume=volume,
    )


def _make_signal(direction=SignalDirection.BUY, confidence=0.85):
    return SignalResult(direction=direction, confidence=confidence, rule_matched=True)


def _make_indicators(rsi=28.0, atr=100.0):
    return EvaluatedIndicators(
        rsi=rsi, macd_line=0.5, signal_line=0.3, histogram=0.2, atr=atr,
    )


def _make_state(regime=None):
    state = MagicMock()
    state.regime = regime
    state.profile_id = "test-profile-001"
    return state


# ---------------------------------------------------------------------------
# AbstentionChecker tests
# ---------------------------------------------------------------------------

class TestAbstentionChecker:
    def test_abstain_on_low_atr(self):
        """Whipsaw protection: abstain when ATR < 0.3% of price."""
        state = _make_state()
        tick = _make_tick(price=50000.0)
        signal = _make_signal()
        # ATR = 100, price = 50000, 0.3% of price = 150 → ATR < threshold → abstain
        inds = _make_indicators(atr=100.0)
        assert AbstentionChecker.check(state, signal, tick, inds) is True

    def test_no_abstain_on_high_atr(self):
        """Normal volatility: proceed when ATR > 0.3% of price."""
        state = _make_state()
        tick = _make_tick(price=50000.0)
        signal = _make_signal()
        # ATR = 200, 0.3% of 50000 = 150 → ATR > threshold → no abstain
        inds = _make_indicators(atr=200.0)
        assert AbstentionChecker.check(state, signal, tick, inds) is False

    def test_abstain_on_crisis_regime(self):
        """Always abstain in CRISIS regime."""
        state = _make_state(regime=Regime.CRISIS)
        tick = _make_tick()
        signal = _make_signal()
        inds = _make_indicators(atr=200.0)
        assert AbstentionChecker.check(state, signal, tick, inds) is True

    def test_abstain_on_abstain_signal(self):
        """Abstain when signal direction is ABSTAIN."""
        state = _make_state()
        tick = _make_tick()
        signal = _make_signal(direction=SignalDirection.ABSTAIN)
        inds = _make_indicators(atr=200.0)
        assert AbstentionChecker.check(state, signal, tick, inds) is True


# ---------------------------------------------------------------------------
# KillSwitch tests
# ---------------------------------------------------------------------------

class TestKillSwitch:
    @pytest.mark.asyncio
    async def test_is_active_returns_true_when_set(self):
        """Kill switch should be active when Redis key is '1'."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="1")
        assert await KillSwitch.is_active(redis) is True

    @pytest.mark.asyncio
    async def test_is_active_returns_false_when_not_set(self):
        """Kill switch should be inactive when Redis key is None."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        assert await KillSwitch.is_active(redis) is False

    @pytest.mark.asyncio
    async def test_is_active_fails_safe_on_redis_error(self):
        """If Redis is unreachable, kill switch should default to ACTIVE (safe)."""
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=Exception("Redis down"))
        assert await KillSwitch.is_active(redis) is True

    @pytest.mark.asyncio
    async def test_activate_sets_key_and_logs(self):
        """activate() should set the Redis key and write to the log list."""
        redis = AsyncMock()
        await KillSwitch.activate(redis, reason="test", activated_by="unit-test")
        redis.set.assert_awaited_once_with(KILL_SWITCH_KEY, "1")
        redis.lpush.assert_awaited_once()
        redis.ltrim.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deactivate_deletes_key_and_logs(self):
        """deactivate() should delete the Redis key and write to the log list."""
        redis = AsyncMock()
        await KillSwitch.deactivate(redis, reason="test")
        redis.delete.assert_awaited_once_with(KILL_SWITCH_KEY)
        redis.lpush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_status_returns_active_and_log(self):
        """status() should return current state and recent log entries."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="1")
        redis.lrange = AsyncMock(return_value=[
            json.dumps({"action": "ACTIVATED", "reason": "test", "timestamp": 1000.0}),
        ])
        result = await KillSwitch.status(redis)
        assert result["active"] is True
        assert len(result["recent_log"]) == 1
        assert result["recent_log"][0]["action"] == "ACTIVATED"
