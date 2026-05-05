"""Synthetic-trade scenario matrix.

Each scenario describes a (regime, signal, expected_decision) tuple. The
harness drives a tick built to satisfy the scenario through `run_pipeline`
and asserts the decision matches.

Scenarios live here (not inline in the test) so future additions don't churn
the test file and CI logs read as a flat list of `[regime-direction-outcome]`
ids.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock

from libs.core.enums import Regime, SignalDirection
from libs.core.models import NormalisedTick, RiskLimits

from services.hot_path.src.strategy_eval import EvaluatedIndicators, SignalResult


@dataclass(frozen=True)
class Scenario:
    name: str
    regime: Optional[Regime]
    signal_direction: SignalDirection
    signal_confidence: float
    atr: float
    price: float
    expected_decision: str          # one of: APPROVED, BLOCKED_<GATE>
    expected_reason_substring: Optional[str] = None
    daily_realised_pnl_pct: Decimal = Decimal("0")
    open_exposure_dollars: Decimal = Decimal("0")
    blacklist: tuple = ()


def make_state(scenario: Scenario):
    """Build a ProfileState-like MagicMock pre-loaded for the scenario."""
    state = MagicMock()
    state.profile_id = "test-profile-001"
    state.regime = scenario.regime
    state.preferred_regimes = frozenset()
    state.is_active = True
    state.notional = Decimal("10000")
    state.open_exposure_dollars = scenario.open_exposure_dollars
    state.current_drawdown_pct = Decimal("0")
    state.daily_realised_pnl_pct = scenario.daily_realised_pnl_pct
    state.blacklist = frozenset(scenario.blacklist)
    state.risk_limits = RiskLimits(
        max_drawdown_pct=Decimal("0.10"),
        stop_loss_pct=Decimal("0.05"),
        circuit_breaker_daily_loss_pct=Decimal("0.02"),
        max_allocation_pct=Decimal("0.25"),
    )
    return state


def make_tick(scenario: Scenario) -> NormalisedTick:
    return NormalisedTick(
        symbol="BTC/USDT",
        exchange="binance",
        timestamp=1_000_000,
        price=Decimal(str(scenario.price)),
        volume=Decimal("1"),
    )


def make_signal(scenario: Scenario) -> SignalResult:
    return SignalResult(
        direction=scenario.signal_direction,
        confidence=scenario.signal_confidence,
        rule_matched=True,
    )


def make_indicators(scenario: Scenario) -> EvaluatedIndicators:
    return EvaluatedIndicators(
        rsi=28.0, macd_line=0.5, signal_line=0.3, histogram=0.2,
        atr=scenario.atr,
    )


# --- Matrix --------------------------------------------------------------

# Healthy ATR for a $50,000 BTC tick is > 0.3% × 50,000 = $150 of ATR.
_OK_ATR = 200.0
_LOW_ATR = 100.0  # Below 0.3% threshold → triggers AbstentionChecker low-ATR

SCENARIOS = [
    # The CRISIS regression test for a08d576. AbstentionChecker MUST short-
    # circuit on Regime.CRISIS regardless of signal direction or strength.
    Scenario(
        name="crisis-buy-abstain",
        regime=Regime.CRISIS,
        signal_direction=SignalDirection.BUY,
        signal_confidence=0.85,
        atr=_OK_ATR,
        price=50000.0,
        expected_decision="BLOCKED_ABSTENTION",
        expected_reason_substring="crisis_regime",
    ),
    Scenario(
        name="crisis-sell-abstain",
        regime=Regime.CRISIS,
        signal_direction=SignalDirection.SELL,
        signal_confidence=0.85,
        atr=_OK_ATR,
        price=50000.0,
        expected_decision="BLOCKED_ABSTENTION",
        expected_reason_substring="crisis_regime",
    ),

    # Whipsaw protection: low ATR triggers abstention before regime checks.
    Scenario(
        name="low-atr-abstain",
        regime=Regime.RANGE_BOUND,
        signal_direction=SignalDirection.BUY,
        signal_confidence=0.85,
        atr=_LOW_ATR,
        price=50000.0,
        expected_decision="BLOCKED_ABSTENTION",
        expected_reason_substring="low_atr",
    ),

    # ABSTAIN signal direction — even with healthy regime/ATR.
    Scenario(
        name="signal-abstain-direction",
        regime=Regime.RANGE_BOUND,
        signal_direction=SignalDirection.ABSTAIN,
        signal_confidence=0.85,
        atr=_OK_ATR,
        price=50000.0,
        expected_decision="BLOCKED_ABSTENTION",
        expected_reason_substring="signal_abstain",
    ),

    # Daily loss past circuit-breaker threshold (-2% configured) → block.
    Scenario(
        name="circuit-breaker-trip",
        regime=Regime.RANGE_BOUND,
        signal_direction=SignalDirection.BUY,
        signal_confidence=0.85,
        atr=_OK_ATR,
        price=50000.0,
        daily_realised_pnl_pct=Decimal("-0.03"),
        expected_decision="BLOCKED_CIRCUIT_BREAKER",
    ),

    # Symbol on the profile blacklist.
    Scenario(
        name="blacklist-block",
        regime=Regime.RANGE_BOUND,
        signal_direction=SignalDirection.BUY,
        signal_confidence=0.85,
        atr=_OK_ATR,
        price=50000.0,
        blacklist=("BTC/USDT",),
        expected_decision="BLOCKED_BLACKLIST",
    ),

    # Open exposure already saturates notional → RiskGate blocks.
    Scenario(
        name="exposure-saturated",
        regime=Regime.RANGE_BOUND,
        signal_direction=SignalDirection.BUY,
        signal_confidence=0.85,
        atr=_OK_ATR,
        price=50000.0,
        open_exposure_dollars=Decimal("10000"),
        expected_decision="BLOCKED_RISK",
        expected_reason_substring="exposure_at_notional",
    ),

    # Happy path: healthy regime, healthy ATR, BUY signal, room to size.
    Scenario(
        name="bull-buy-approved",
        regime=Regime.TRENDING_UP,
        signal_direction=SignalDirection.BUY,
        signal_confidence=0.85,
        atr=_OK_ATR,
        price=50000.0,
        expected_decision="APPROVED",
    ),
]
