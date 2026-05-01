"""A.3 partial: per-regime confidence multipliers in RegimeDampener.

The previous behavior collapsed every non-CRISIS, non-HIGH_VOLATILITY regime
to multiplier=1.0 and used 0.7 for HIGH_VOLATILITY. The brief calls for an
asymmetric mapping that down-sizes counter-trend (TRENDING_DOWN) and ranging
regimes more than trending-up regimes.
"""

import json

import pytest
from unittest.mock import AsyncMock

from libs.core.enums import Regime, SignalDirection
from libs.core.models import NormalisedTick, RiskLimits
from libs.indicators import create_indicator_set
from services.hot_path.src.regime_dampener import (
    RegimeDampener,
    _REGIME_CONFIDENCE_MULTIPLIER,
)
from services.hot_path.src.state import ProfileState
from services.hot_path.src.strategy_eval import EvaluatedIndicators, SignalResult
from services.strategy.src.compiler import RuleCompiler
from decimal import Decimal


def _make_state() -> ProfileState:
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
    return ProfileState(
        profile_id="t",
        compiled_rules=rules,
        risk_limits=limits,
        blacklist=frozenset(),
        indicators=create_indicator_set(),
    )


def _signal() -> SignalResult:
    return SignalResult(direction=SignalDirection.BUY, confidence=0.85, rule_matched=True)


def _tick() -> NormalisedTick:
    return NormalisedTick(symbol="BTC/USDT", exchange="binance", timestamp=1, price=50000.0, volume=1.0)


def _inds() -> EvaluatedIndicators:
    return EvaluatedIndicators(rsi=28.0, macd_line=0.5, signal_line=0.3, histogram=0.2, atr=100.0)


@pytest.mark.parametrize("regime,expected", [
    (Regime.TRENDING_UP, 1.0),
    (Regime.TRENDING_DOWN, 0.5),
    (Regime.RANGE_BOUND, 0.8),
    (Regime.HIGH_VOLATILITY, 0.6),
])
def test_multiplier_table_matches_brief(regime, expected):
    assert _REGIME_CONFIDENCE_MULTIPLIER[regime] == expected


@pytest.mark.parametrize("hmm_regime,expected_multiplier", [
    ("TRENDING_UP", 1.0),
    ("TRENDING_DOWN", 0.5),
    ("RANGE_BOUND", 0.8),
    ("HIGH_VOLATILITY", 0.6),
])
@pytest.mark.asyncio
async def test_dampener_uses_per_regime_multiplier(hmm_regime, expected_multiplier):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=json.dumps({"regime": hmm_regime, "state_index": 0}))
    dampener = RegimeDampener(redis_client=redis, pubsub=AsyncMock())
    state = _make_state()

    # Suppress rule-based regime so HMM wins the resolve. SimpleRegimeClassifier
    # uses __slots__ so we replace the whole calculator with a Mock instead of
    # patching its update method in place.
    from unittest.mock import MagicMock
    state.indicators.regime = MagicMock(update=MagicMock(return_value=None))

    result = await dampener.check(state, _signal(), _tick(), _inds())
    assert result.proceed is True
    assert result.confidence_multiplier == expected_multiplier


@pytest.mark.asyncio
async def test_crisis_still_blocks():
    from unittest.mock import MagicMock

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=json.dumps({"regime": "CRISIS", "state_index": 4}))
    dampener = RegimeDampener(redis_client=redis, pubsub=AsyncMock())
    state = _make_state()
    state.indicators.regime = MagicMock(update=MagicMock(return_value=None))
    result = await dampener.check(state, _signal(), _tick(), _inds())
    assert result.proceed is False
    assert result.confidence_multiplier == 0.0
