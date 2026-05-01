"""Tests for Phase 3: HITL Execution Gate.

Tests trigger conditions, pass-through when disabled, timeout rejection,
and approval flow.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch
from decimal import Decimal

from services.hot_path.src.hitl_gate import HITLGate, HITLGateResult
from services.hot_path.src.strategy_eval import SignalResult, EvaluatedIndicators
from services.hot_path.src.risk_gate import RiskGateResult
from services.hot_path.src.state import ProfileState
from services.strategy.src.compiler import CompiledRuleSet
from libs.core.enums import SignalDirection, Regime, HITLStatus
from libs.core.models import NormalisedTick, RiskLimits
from libs.indicators import create_indicator_set


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_tick(symbol="BTC/USDT", price=50000.0):
    return NormalisedTick(
        symbol=symbol, exchange="BINANCE", timestamp=1000000,
        price=Decimal(str(price)), volume=Decimal("1.0"),
    )

def _make_signal(direction=SignalDirection.BUY, confidence=0.85):
    return SignalResult(direction=direction, confidence=confidence, rule_matched=True)

def _make_indicators():
    return EvaluatedIndicators(rsi=45.0, macd_line=0.5, signal_line=0.3, histogram=0.2, atr=500.0)

def _make_risk_result(quantity=0.5):
    return RiskGateResult(blocked=False, suggested_quantity=quantity)

def _make_state(regime=None, allocation_pct=0.1, drawdown_pct=0.0):
    rules = CompiledRuleSet(
        logic="AND", direction=SignalDirection.BUY,
        base_confidence=0.85, conditions=[{"indicator": "rsi", "operator": "LT", "value": 30}],
    )
    limits = RiskLimits(
        max_drawdown_pct=Decimal("0.05"), stop_loss_pct=Decimal("0.02"),
        circuit_breaker_daily_loss_pct=Decimal("0.02"), max_allocation_pct=Decimal("10.0"),
    )
    state = ProfileState(
        profile_id="test-profile", compiled_rules=rules,
        risk_limits=limits, blacklist=frozenset(), indicators=create_indicator_set(),
    )
    state.regime = regime
    state.current_allocation_pct = allocation_pct
    state.current_drawdown_pct = drawdown_pct
    return state


class FakeRedis:
    def __init__(self):
        self._store = {}
        self._lists = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ex=None):
        self._store[key] = value

    async def delete(self, key):
        self._store.pop(key, None)

    async def blpop(self, key, timeout=0):
        if key in self._lists and self._lists[key]:
            return (key, self._lists[key].pop(0))
        return None  # Simulate timeout

    async def lpush(self, key, value):
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].insert(0, value)

    def pipeline(self, transaction=False):
        return FakePipeline(self._store)


class FakePipeline:
    def __init__(self, store):
        self._store = store
        self._commands = []

    def get(self, key):
        self._commands.append(("get", key))
        return self

    async def execute(self):
        results = []
        for cmd, key in self._commands:
            results.append(self._store.get(key))
        self._commands = []
        return results


class FakePubSub:
    def __init__(self):
        self.published = []

    async def publish(self, channel, event):
        self.published.append((channel, event))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHITLGate:

    @pytest.mark.asyncio
    @patch('services.hot_path.src.hitl_gate.settings')
    async def test_disabled_passes_through(self, mock_settings):
        """When HITL_ENABLED=False, gate is a no-op pass-through."""
        mock_settings.HITL_ENABLED = False
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        result = await gate.check(
            _make_state(), _make_signal(), _make_tick(),
            _make_indicators(), _make_risk_result(),
        )
        assert not result.blocked
        assert not result.hitl_triggered
        assert len(pubsub.published) == 0

    @pytest.mark.asyncio
    @patch('services.hot_path.src.hitl_gate.settings')
    async def test_no_trigger_passes_through(self, mock_settings):
        """High confidence + normal regime + small trade → no trigger."""
        mock_settings.HITL_ENABLED = True
        mock_settings.HITL_CONFIDENCE_THRESHOLD = 0.5
        mock_settings.HITL_SIZE_THRESHOLD_PCT = 5.0
        mock_settings.HITL_TIMEOUT_S = 5

        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        result = await gate.check(
            _make_state(regime=Regime.TRENDING_UP),
            _make_signal(confidence=0.9),
            _make_tick(),
            _make_indicators(),
            _make_risk_result(quantity=0.01),  # Small relative to max_alloc=10.0
        )
        assert not result.blocked
        assert not result.hitl_triggered

    @pytest.mark.asyncio
    @patch('services.hot_path.src.hitl_gate.settings')
    async def test_low_confidence_triggers(self, mock_settings):
        """Low confidence should trigger HITL."""
        mock_settings.HITL_ENABLED = True
        mock_settings.HITL_CONFIDENCE_THRESHOLD = 0.5
        mock_settings.HITL_SIZE_THRESHOLD_PCT = 5.0
        mock_settings.HITL_TIMEOUT_S = 1

        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        # Low confidence, no pre-set response → timeout → reject
        result = await gate.check(
            _make_state(),
            _make_signal(confidence=0.3),
            _make_tick(),
            _make_indicators(),
            _make_risk_result(),
        )
        assert result.blocked
        assert result.hitl_triggered
        assert "timeout" in result.reason
        assert len(pubsub.published) == 1  # Request was published

    @pytest.mark.asyncio
    @patch('services.hot_path.src.hitl_gate.settings')
    async def test_high_volatility_triggers(self, mock_settings):
        """HIGH_VOLATILITY regime should trigger HITL."""
        mock_settings.HITL_ENABLED = True
        mock_settings.HITL_CONFIDENCE_THRESHOLD = 0.3
        mock_settings.HITL_SIZE_THRESHOLD_PCT = 50.0
        mock_settings.HITL_TIMEOUT_S = 1

        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        result = await gate.check(
            _make_state(regime=Regime.HIGH_VOLATILITY),
            _make_signal(confidence=0.9),
            _make_tick(),
            _make_indicators(),
            _make_risk_result(),
        )
        assert result.blocked  # Timeout → reject
        assert result.hitl_triggered
        assert len(pubsub.published) == 1

    @pytest.mark.asyncio
    @patch('services.hot_path.src.hitl_gate.settings')
    async def test_approval_unblocks(self, mock_settings):
        """When human approves, trade should pass through."""
        mock_settings.HITL_ENABLED = True
        mock_settings.HITL_CONFIDENCE_THRESHOLD = 0.5
        mock_settings.HITL_SIZE_THRESHOLD_PCT = 5.0
        mock_settings.HITL_TIMEOUT_S = 5

        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        # We need to pre-populate the response before the gate reads it.
        # The gate uses blpop on `hitl:response:{event_id}` but we don't know
        # the event_id ahead of time. Instead, override blpop to always return approved.
        async def mock_blpop(key, timeout=0):
            return (key, json.dumps({"status": "APPROVED", "reviewer": "test"}).encode())

        redis.blpop = mock_blpop

        result = await gate.check(
            _make_state(),
            _make_signal(confidence=0.3),  # Low confidence triggers
            _make_tick(),
            _make_indicators(),
            _make_risk_result(),
        )
        assert not result.blocked
        assert result.hitl_triggered

    @pytest.mark.asyncio
    @patch('services.hot_path.src.hitl_gate.settings')
    async def test_rejection_blocks(self, mock_settings):
        """When human rejects, trade should be blocked."""
        mock_settings.HITL_ENABLED = True
        mock_settings.HITL_CONFIDENCE_THRESHOLD = 0.5
        mock_settings.HITL_SIZE_THRESHOLD_PCT = 5.0
        mock_settings.HITL_TIMEOUT_S = 5

        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        async def mock_blpop(key, timeout=0):
            return (key, json.dumps({"status": "REJECTED", "reason": "Too risky"}).encode())

        redis.blpop = mock_blpop

        result = await gate.check(
            _make_state(),
            _make_signal(confidence=0.3),
            _make_tick(),
            _make_indicators(),
            _make_risk_result(),
        )
        assert result.blocked
        assert result.hitl_triggered
        assert "rejected" in result.reason

    @pytest.mark.asyncio
    @patch('services.hot_path.src.hitl_gate.settings')
    async def test_timeout_rejects_failsafe(self, mock_settings):
        """Timeout should result in rejection (fail-safe)."""
        mock_settings.HITL_ENABLED = True
        mock_settings.HITL_CONFIDENCE_THRESHOLD = 0.5
        mock_settings.HITL_SIZE_THRESHOLD_PCT = 5.0
        mock_settings.HITL_TIMEOUT_S = 1

        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        result = await gate.check(
            _make_state(),
            _make_signal(confidence=0.3),
            _make_tick(),
            _make_indicators(),
            _make_risk_result(),
        )
        assert result.blocked
        assert "timeout" in result.reason

    @pytest.mark.asyncio
    @patch('services.hot_path.src.hitl_gate.settings')
    async def test_large_trade_triggers(self, mock_settings):
        """Trade size exceeding threshold should trigger HITL."""
        mock_settings.HITL_ENABLED = True
        mock_settings.HITL_CONFIDENCE_THRESHOLD = 0.3
        mock_settings.HITL_SIZE_THRESHOLD_PCT = 5.0
        mock_settings.HITL_TIMEOUT_S = 1

        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        # quantity=5.0 out of max_alloc=10.0 → 50% → > 5% threshold
        result = await gate.check(
            _make_state(regime=Regime.TRENDING_UP),
            _make_signal(confidence=0.9),
            _make_tick(),
            _make_indicators(),
            _make_risk_result(quantity=5.0),
        )
        assert result.blocked  # Timeout → reject
        assert result.hitl_triggered

    @pytest.mark.asyncio
    @patch('services.hot_path.src.hitl_gate.settings')
    async def test_size_check_uses_dollar_math(self, mock_settings):
        """A trade well under the dollar threshold must not trigger.

        Regression for the unit-mixing bug: the old `qty / max_alloc * 100`
        formula would have read this as 100% (10.0 ETH / 0.1 max_alloc) and
        triggered. The corrected dollar-based formula evaluates this trade
        at $5 / $1000 = 0.5% of allocation — well below the 5% threshold.
        """
        mock_settings.HITL_ENABLED = True
        mock_settings.HITL_CONFIDENCE_THRESHOLD = 0.3
        mock_settings.HITL_SIZE_THRESHOLD_PCT = 5.0
        mock_settings.HITL_TIMEOUT_S = 1

        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        # State: $10k notional, 10% max allocation cap → $1000 allocation cap.
        rules = CompiledRuleSet(
            logic="AND", direction=SignalDirection.BUY,
            base_confidence=0.85, conditions=[{"indicator": "rsi", "operator": "LT", "value": 30}],
        )
        limits = RiskLimits(
            max_drawdown_pct=Decimal("0.05"), stop_loss_pct=Decimal("0.02"),
            circuit_breaker_daily_loss_pct=Decimal("0.02"),
            max_allocation_pct=Decimal("0.10"),
        )
        state = ProfileState(
            profile_id="test-profile", compiled_rules=rules,
            risk_limits=limits, blacklist=frozenset(), indicators=create_indicator_set(),
        )
        state.regime = Regime.TRENDING_UP

        # Tick at $0.50/asset, qty=10 → $5 trade. 0.5% of $1000 cap.
        tick = NormalisedTick(
            symbol="BTC/USDT", exchange="BINANCE", timestamp=1000000,
            price=Decimal("0.5"), volume=Decimal("1.0"),
        )
        result = await gate.check(
            state, _make_signal(confidence=0.9), tick,
            _make_indicators(), _make_risk_result(quantity=Decimal("10.0")),
        )
        assert not result.blocked
        assert not result.hitl_triggered

    @pytest.mark.asyncio
    @patch('services.hot_path.src.hitl_gate.settings')
    async def test_size_check_triggers_on_real_dollar_excess(self, mock_settings):
        """A trade above the dollar threshold should trigger.

        Mirrors a realistic profile (10% max allocation, $10k notional →
        $1000 allocation cap). Risk gate sized this trade at $700 — that's
        70% of the cap, well above the 5% threshold, so HITL must trigger.
        """
        mock_settings.HITL_ENABLED = True
        mock_settings.HITL_CONFIDENCE_THRESHOLD = 0.3
        mock_settings.HITL_SIZE_THRESHOLD_PCT = 5.0
        mock_settings.HITL_TIMEOUT_S = 1

        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        rules = CompiledRuleSet(
            logic="AND", direction=SignalDirection.BUY,
            base_confidence=0.85, conditions=[{"indicator": "rsi", "operator": "LT", "value": 30}],
        )
        limits = RiskLimits(
            max_drawdown_pct=Decimal("0.05"), stop_loss_pct=Decimal("0.02"),
            circuit_breaker_daily_loss_pct=Decimal("0.02"),
            max_allocation_pct=Decimal("0.10"),
        )
        state = ProfileState(
            profile_id="test-profile", compiled_rules=rules,
            risk_limits=limits, blacklist=frozenset(), indicators=create_indicator_set(),
        )
        state.regime = Regime.TRENDING_UP

        tick = NormalisedTick(
            symbol="ETH/USDT", exchange="BINANCE", timestamp=1000000,
            price=Decimal("3500"), volume=Decimal("1.0"),
        )
        result = await gate.check(
            state, _make_signal(confidence=0.9), tick,
            _make_indicators(), _make_risk_result(quantity=Decimal("0.2")),  # $700 trade
        )
        assert result.blocked  # Timeout → reject
        assert result.hitl_triggered
        # The post-timeout result.reason is "hitl_timeout_*", but the published
        # event carries the upstream trigger reason — assert against that.
        assert len(pubsub.published) == 1
        _, published = pubsub.published[0]
        assert "large_trade" in published.trigger_reason
