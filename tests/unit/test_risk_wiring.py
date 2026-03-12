"""Sprint 10.4: Portfolio risk wiring verification tests."""
import json
import pytest
from unittest.mock import AsyncMock
from decimal import Decimal

from services.hot_path.src.risk_gate import RiskGate, RiskGateResult
from services.hot_path.src.circuit_breaker import CircuitBreaker
from services.hot_path.src.strategy_eval import SignalResult
from services.hot_path.src.state import ProfileState
from services.strategy.src.compiler import RuleCompiler
from libs.indicators import create_indicator_set
from libs.core.enums import Regime, SignalDirection
from libs.core.models import NormalisedTick, RiskLimits


def _make_state(profile_id="test-profile", daily_pnl=0.0, drawdown=0.0, allocation=0.0):
    rules = RuleCompiler.compile({
        "conditions": [{"indicator": "rsi", "operator": "LT", "value": 30}],
        "logic": "AND",
        "direction": "BUY",
        "base_confidence": 0.85,
    })
    limits = RiskLimits(
        max_drawdown_pct=Decimal("0.10"),
        stop_loss_pct=Decimal("0.05"),
        circuit_breaker_daily_loss_pct=Decimal("0.02"),
        max_allocation_pct=Decimal("0.25"),
    )
    state = ProfileState(
        profile_id=profile_id,
        compiled_rules=rules,
        risk_limits=limits,
        blacklist=frozenset(),
        indicators=create_indicator_set(),
    )
    state.daily_realised_pnl_pct = daily_pnl
    state.current_drawdown_pct = drawdown
    state.current_allocation_pct = allocation
    return state


def _make_tick():
    return NormalisedTick(
        symbol="BTC/USDT", exchange="binance", timestamp=1000000, price=50000.0, volume=1.0
    )


def _make_signal(confidence=0.85):
    return SignalResult(direction=SignalDirection.BUY, confidence=confidence, rule_matched=True)


class TestCircuitBreaker:
    def test_trips_when_daily_loss_exceeds_threshold(self):
        """Set daily PnL to -3%, verify CircuitBreaker trips when threshold is 2%."""
        state = _make_state(daily_pnl=-0.03)  # -3% loss
        assert CircuitBreaker.check(state) is True

    def test_does_not_trip_within_threshold(self):
        """Daily PnL within limits should not trip."""
        state = _make_state(daily_pnl=-0.01)  # -1% loss, threshold is 2%
        assert CircuitBreaker.check(state) is False

    def test_does_not_trip_with_no_data(self):
        """Fresh start with 0.0 PnL should not trip."""
        state = _make_state(daily_pnl=0.0)
        assert CircuitBreaker.check(state) is False

    def test_does_not_trip_with_positive_pnl(self):
        """Positive PnL should never trip."""
        state = _make_state(daily_pnl=0.05)
        assert CircuitBreaker.check(state) is False


class TestRiskGate:
    def test_blocks_when_allocation_at_limit(self):
        """Allocation at max should block."""
        state = _make_state(allocation=0.25)
        result = RiskGate.check(state, _make_signal(), _make_tick())
        assert result.blocked is True

    def test_blocks_when_drawdown_exceeds_limit(self):
        """Drawdown above max should block."""
        state = _make_state(drawdown=0.15)
        result = RiskGate.check(state, _make_signal(), _make_tick())
        assert result.blocked is True

    def test_reduces_quantity_when_drawdown_approaches_limit(self):
        """Drawdown > half of limit should reduce quantity by 50%."""
        state_normal = _make_state(drawdown=0.0)
        state_stressed = _make_state(drawdown=0.06)  # > 0.05 (half of 0.10)

        signal = _make_signal(confidence=1.0)
        tick = _make_tick()

        result_normal = RiskGate.check(state_normal, signal, tick)
        result_stressed = RiskGate.check(state_stressed, signal, tick)

        assert not result_normal.blocked
        assert not result_stressed.blocked
        assert result_stressed.suggested_quantity < result_normal.suggested_quantity

    def test_reduces_quantity_in_high_volatility(self):
        """HIGH_VOLATILITY regime should reduce quantity by 30%."""
        state = _make_state()
        state.regime = Regime.HIGH_VOLATILITY

        signal = _make_signal(confidence=1.0)
        tick = _make_tick()

        result = RiskGate.check(state, signal, tick)
        assert not result.blocked
        # 0.25 * 1.0 * 0.7 = 0.175
        assert result.suggested_quantity == pytest.approx(0.175)

    def test_dynamic_sizing_uses_confidence(self):
        """Position size should scale with signal confidence."""
        state = _make_state()
        tick = _make_tick()

        result_high = RiskGate.check(state, _make_signal(confidence=1.0), tick)
        result_low = RiskGate.check(state, _make_signal(confidence=0.5), tick)

        assert result_high.suggested_quantity > result_low.suggested_quantity

    def test_no_false_trips_with_defaults(self):
        """Fresh start with all defaults should not block."""
        state = _make_state()
        result = RiskGate.check(state, _make_signal(), _make_tick())
        assert result.blocked is False
        assert result.suggested_quantity > 0
