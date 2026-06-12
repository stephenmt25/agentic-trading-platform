"""Tests for the HITL Execution Gate (non-blocking park/sweep model, row 44).

Covers trigger conditions, the PRAXIS_HITL_ENABLED=false bypass, parking
(check returns immediately, never awaits a human), the sweep's
approve/deny/timeout/parse-error resolutions, fail-safe semantics, and the
duplicate-request dedup for sustained signals.
"""

import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from libs.core.enums import Regime, SignalDirection
from libs.core.models import NormalisedTick, RiskLimits
from libs.indicators import create_indicator_set
from services.hot_path.src.hitl_gate import HITLGate
from services.hot_path.src.risk_gate import RiskGateResult
from services.hot_path.src.state import ProfileState
from services.hot_path.src.strategy_eval import EvaluatedIndicators, SignalResult
from services.strategy.src.compiler import CompiledRuleSet

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_tick(symbol="BTC/USDT", price=50000.0):
    return NormalisedTick(
        symbol=symbol,
        exchange="BINANCE",
        timestamp=1000000,
        price=Decimal(str(price)),
        volume=Decimal("1.0"),
    )


def _make_signal(direction=SignalDirection.BUY, confidence=0.85):
    return SignalResult(direction=direction, confidence=confidence, rule_matched=True)


def _make_indicators():
    return EvaluatedIndicators(
        rsi=45.0, macd_line=0.5, signal_line=0.3, histogram=0.2, atr=500.0
    )


def _make_risk_result(quantity=0.5):
    return RiskGateResult(blocked=False, suggested_quantity=quantity)


def _make_state(regime=None, allocation_pct=0.1, drawdown_pct=0.0):
    rules = CompiledRuleSet(
        logic="AND",
        direction=SignalDirection.BUY,
        base_confidence=0.85,
        conditions=[{"indicator": "rsi", "operator": "LT", "value": 30}],
    )
    limits = RiskLimits(
        max_drawdown_pct=Decimal("0.05"),
        stop_loss_pct=Decimal("0.02"),
        circuit_breaker_daily_loss_pct=Decimal("0.02"),
        max_allocation_pct=Decimal("10.0"),
    )
    state = ProfileState(
        profile_id="test-profile",
        compiled_rules=rules,
        risk_limits=limits,
        blacklist=frozenset(),
        indicators=create_indicator_set(),
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

    async def lpop(self, key):
        if key in self._lists and self._lists[key]:
            return self._lists[key].pop(0)
        return None

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


def _configure(mock_settings, enabled=True, conf=0.5, size_pct=5.0, timeout_s=60):
    mock_settings.HITL_ENABLED = enabled
    mock_settings.HITL_CONFIDENCE_THRESHOLD = conf
    mock_settings.HITL_SIZE_THRESHOLD_PCT = size_pct
    mock_settings.HITL_TIMEOUT_S = timeout_s


async def _park_low_confidence(gate, **check_kwargs):
    """Trigger HITL via low confidence; return the gate result."""
    return await gate.check(
        _make_state(),
        _make_signal(confidence=0.3),
        _make_tick(),
        _make_indicators(),
        _make_risk_result(),
        **check_kwargs,
    )


# ---------------------------------------------------------------------------
# Trigger + bypass tests
# ---------------------------------------------------------------------------


class TestHITLGateTriggers:

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_disabled_passes_through(self, mock_settings):
        """When HITL_ENABLED=False, gate is a no-op pass-through."""
        mock_settings.HITL_ENABLED = False
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        result = await gate.check(
            _make_state(),
            _make_signal(),
            _make_tick(),
            _make_indicators(),
            _make_risk_result(),
        )
        assert not result.blocked
        assert not result.hitl_triggered
        assert not result.parked
        assert len(pubsub.published) == 0
        assert gate.pending_count == 0

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_no_trigger_passes_through(self, mock_settings):
        """High confidence + normal regime + small trade → no trigger."""
        _configure(mock_settings)
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
        assert not result.parked

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_low_confidence_parks_immediately(self, mock_settings):
        """Low confidence triggers HITL: request emitted, signal PARKED,
        check returns instantly (no blocking wait)."""
        _configure(mock_settings)
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        result = await _park_low_confidence(gate)
        assert result.parked
        assert result.hitl_triggered
        assert not result.blocked
        assert len(pubsub.published) == 1  # Request was published
        assert gate.pending_count == 1
        # Both Redis records exist: frontend pending payload + parked record
        request = pubsub.published[0][1]
        assert redis._store.get(f"hitl:pending:{request.event_id}") is not None
        parked_raw = redis._store.get(f"hitl:parked:{request.event_id}")
        assert parked_raw is not None
        parked_doc = json.loads(parked_raw)
        assert parked_doc["profile_id"] == "test-profile"
        assert parked_doc["symbol"] == "BTC/USDT"
        assert "deadline_epoch" in parked_doc

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_high_volatility_triggers(self, mock_settings):
        """HIGH_VOLATILITY regime should trigger HITL (park)."""
        _configure(mock_settings, conf=0.3, size_pct=50.0)
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
        assert result.parked
        assert result.hitl_triggered
        assert len(pubsub.published) == 1

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_duplicate_signal_blocked_while_parked(self, mock_settings):
        """A sustained signal re-fires every tick — while one approval is
        pending for a (profile, symbol), duplicates are fail-safe blocked
        WITHOUT emitting another approval request."""
        _configure(mock_settings)
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        first = await _park_low_confidence(gate)
        assert first.parked

        second = await _park_low_confidence(gate)
        assert second.blocked
        assert second.hitl_triggered
        assert not second.parked
        assert second.reason == "hitl_pending_existing"
        assert len(pubsub.published) == 1  # no duplicate request
        assert gate.pending_count == 1

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_large_trade_triggers(self, mock_settings):
        """Trade size exceeding threshold should trigger HITL (park)."""
        _configure(mock_settings, conf=0.3, timeout_s=60)
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
        assert result.parked
        assert result.hitl_triggered

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_size_check_uses_dollar_math(self, mock_settings):
        """A trade well under the dollar threshold must not trigger.

        Regression for the unit-mixing bug: the old `qty / max_alloc * 100`
        formula would have read this as 100% (10.0 ETH / 0.1 max_alloc) and
        triggered. The corrected dollar-based formula evaluates this trade
        at $5 / $1000 = 0.5% of allocation — well below the 5% threshold.
        """
        _configure(mock_settings, conf=0.3)
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        # State: $10k notional, 10% max allocation cap → $1000 allocation cap.
        rules = CompiledRuleSet(
            logic="AND",
            direction=SignalDirection.BUY,
            base_confidence=0.85,
            conditions=[{"indicator": "rsi", "operator": "LT", "value": 30}],
        )
        limits = RiskLimits(
            max_drawdown_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
            circuit_breaker_daily_loss_pct=Decimal("0.02"),
            max_allocation_pct=Decimal("0.10"),
        )
        state = ProfileState(
            profile_id="test-profile",
            compiled_rules=rules,
            risk_limits=limits,
            blacklist=frozenset(),
            indicators=create_indicator_set(),
        )
        state.regime = Regime.TRENDING_UP

        # Tick at $0.50/asset, qty=10 → $5 trade. 0.5% of $1000 cap.
        tick = NormalisedTick(
            symbol="BTC/USDT",
            exchange="BINANCE",
            timestamp=1000000,
            price=Decimal("0.5"),
            volume=Decimal("1.0"),
        )
        result = await gate.check(
            state,
            _make_signal(confidence=0.9),
            tick,
            _make_indicators(),
            _make_risk_result(quantity=Decimal("10.0")),
        )
        assert not result.blocked
        assert not result.hitl_triggered
        assert not result.parked

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_size_check_triggers_on_real_dollar_excess(self, mock_settings):
        """A trade above the dollar threshold should trigger (park).

        Mirrors a realistic profile (10% max allocation, $10k notional →
        $1000 allocation cap). Risk gate sized this trade at $700 — that's
        70% of the cap, well above the 5% threshold, so HITL must trigger.
        """
        _configure(mock_settings, conf=0.3)
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        rules = CompiledRuleSet(
            logic="AND",
            direction=SignalDirection.BUY,
            base_confidence=0.85,
            conditions=[{"indicator": "rsi", "operator": "LT", "value": 30}],
        )
        limits = RiskLimits(
            max_drawdown_pct=Decimal("0.05"),
            stop_loss_pct=Decimal("0.02"),
            circuit_breaker_daily_loss_pct=Decimal("0.02"),
            max_allocation_pct=Decimal("0.10"),
        )
        state = ProfileState(
            profile_id="test-profile",
            compiled_rules=rules,
            risk_limits=limits,
            blacklist=frozenset(),
            indicators=create_indicator_set(),
        )
        state.regime = Regime.TRENDING_UP

        tick = NormalisedTick(
            symbol="ETH/USDT",
            exchange="BINANCE",
            timestamp=1000000,
            price=Decimal("3500"),
            volume=Decimal("1.0"),
        )
        result = await gate.check(
            state,
            _make_signal(confidence=0.9),
            tick,
            _make_indicators(),
            _make_risk_result(quantity=Decimal("0.2")),  # $700 trade
        )
        assert result.parked
        assert result.hitl_triggered
        # The published event carries the upstream trigger reason.
        assert len(pubsub.published) == 1
        _, published = pubsub.published[0]
        assert "large_trade" in published.trigger_reason


# ---------------------------------------------------------------------------
# Sweep resolution tests
# ---------------------------------------------------------------------------


class TestHITLSweep:

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_sweep_noop_when_nothing_parked(self, mock_settings):
        _configure(mock_settings)
        gate = HITLGate(FakeRedis(), FakePubSub())
        assert await gate.sweep() == []

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_sweep_keeps_pending_before_deadline(self, mock_settings):
        """No response and deadline not reached → stays parked, no resolution."""
        _configure(mock_settings, timeout_s=60)
        redis = FakeRedis()
        gate = HITLGate(redis, FakePubSub())

        result = await _park_low_confidence(gate)
        assert result.parked
        assert await gate.sweep() == []
        assert gate.pending_count == 1

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_approval_resolves_approved(self, mock_settings):
        """When human approves, sweep yields an approved resolution carrying
        the parked context, and all keys are cleaned up."""
        _configure(mock_settings, timeout_s=60)
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        await _park_low_confidence(gate)
        request = pubsub.published[0][1]
        await redis.lpush(
            f"hitl:response:{request.event_id}",
            json.dumps({"status": "APPROVED", "reviewer": "test"}).encode(),
        )

        resolutions = await gate.sweep()
        assert len(resolutions) == 1
        res = resolutions[0]
        assert res.approved
        assert res.reason is None
        assert res.parked.symbol == "BTC/USDT"
        assert res.parked.profile_id == "test-profile"
        assert gate.pending_count == 0
        assert redis._store.get(f"hitl:pending:{request.event_id}") is None
        assert redis._store.get(f"hitl:parked:{request.event_id}") is None

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_rejection_resolves_blocked(self, mock_settings):
        """When human rejects, sweep yields a fail-safe reject resolution."""
        _configure(mock_settings, timeout_s=60)
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        await _park_low_confidence(gate)
        request = pubsub.published[0][1]
        await redis.lpush(
            f"hitl:response:{request.event_id}",
            json.dumps({"status": "REJECTED", "reason": "Too risky"}).encode(),
        )

        resolutions = await gate.sweep()
        assert len(resolutions) == 1
        assert not resolutions[0].approved
        assert resolutions[0].reason == "hitl_rejected"
        assert gate.pending_count == 0

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_timeout_rejects_failsafe(self, mock_settings):
        """No response by the deadline → fail-safe reject, same reason string
        as the old blocking implementation."""
        _configure(mock_settings, timeout_s=0)  # deadline = park time
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        await _park_low_confidence(gate)
        resolutions = await gate.sweep()
        assert len(resolutions) == 1
        assert not resolutions[0].approved
        assert "timeout" in resolutions[0].reason
        assert resolutions[0].reason == "hitl_timeout_0s"
        assert gate.pending_count == 0
        # Cleanup happened
        request = pubsub.published[0][1]
        assert redis._store.get(f"hitl:pending:{request.event_id}") is None

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_malformed_response_rejects_failsafe(self, mock_settings):
        """Unparseable response → fail-safe reject (hitl_parse_error)."""
        _configure(mock_settings, timeout_s=60)
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        await _park_low_confidence(gate)
        request = pubsub.published[0][1]
        await redis.lpush(f"hitl:response:{request.event_id}", b"not-json{{{")

        resolutions = await gate.sweep()
        assert len(resolutions) == 1
        assert not resolutions[0].approved
        assert resolutions[0].reason == "hitl_parse_error"

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_sweep_survives_redis_error_then_times_out(self, mock_settings):
        """A degraded Redis connection can't hang resolution: lpop failures
        leave the signal parked, and the monotonic deadline still fires the
        fail-safe timeout (row 44 failure mode 2)."""
        _configure(mock_settings, timeout_s=60)
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        await _park_low_confidence(gate)

        async def broken_lpop(key):
            raise ConnectionError("redis degraded")

        redis.lpop = broken_lpop

        # Before deadline: error tolerated, still parked.
        assert await gate.sweep() == []
        assert gate.pending_count == 1

        # Force the deadline into the past — timeout fires even though lpop
        # is still failing.
        parked = next(iter(gate._parked.values()))
        parked.deadline_mono = 0.0
        resolutions = await gate.sweep()
        assert len(resolutions) == 1
        assert not resolutions[0].approved
        assert "timeout" in resolutions[0].reason
        assert gate.pending_count == 0

    @pytest.mark.asyncio
    @patch("services.hot_path.src.hitl_gate.settings")
    async def test_pair_freed_after_resolution(self, mock_settings):
        """After a resolution the (profile, symbol) pair can trigger again."""
        _configure(mock_settings, timeout_s=0)
        redis = FakeRedis()
        pubsub = FakePubSub()
        gate = HITLGate(redis, pubsub)

        first = await _park_low_confidence(gate)
        assert first.parked
        await gate.sweep()  # timeout-rejects
        assert gate.pending_count == 0

        again = await _park_low_confidence(gate)
        assert again.parked
        assert len(pubsub.published) == 2
