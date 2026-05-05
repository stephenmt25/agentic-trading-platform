"""In-process synthetic-trade pipeline runner.

Mirrors the pre-validation gate sequence in `services/hot_path/src/processor.py`
so e2e tests can drive a tick through the production gates without booting
`run_all.sh`. The order MUST stay in sync with the production processor — when
a gate is added, removed, or reordered there, mirror it here.

Skipped (require external systems): `KillSwitch`, `AgentModifier`,
`HITLGate`, `ValidationClient`. Tests that need those should boot a real
stack.

Asserted gates (in order):
  1. `AbstentionChecker.check_with_reason`
  2. `RegimeDampener.check`         — overwrites `state.regime` from the rule-
                                       based indicator; tests that pre-set
                                       `state.regime` should rely on the
                                       AbstentionChecker for that decision.
  3. preferred_regimes membership
  4. `CircuitBreaker.check`
  5. `BlacklistChecker.check`
  6. `RiskGate.check`

The CRISIS abstention scenario is the explicit regression test for `a08d576`
(AbstentionChecker CRISIS short-circuit silently disabled for ~5 days).
"""

from dataclasses import dataclass
from typing import Optional

from libs.core.models import NormalisedTick

from services.hot_path.src.abstention import AbstentionChecker
from services.hot_path.src.blacklist import BlacklistChecker
from services.hot_path.src.circuit_breaker import CircuitBreaker
from services.hot_path.src.regime_dampener import RegimeDampener
from services.hot_path.src.risk_gate import RiskGate
from services.hot_path.src.strategy_eval import EvaluatedIndicators, SignalResult


@dataclass(frozen=True)
class PipelineOutcome:
    """Result of running a tick through the gates.

    `decision`: 'APPROVED' if every gate passed, else 'BLOCKED_<GATE>' using
        the same naming as the production processor's trace `outcome` field.
    `reason`: gate-specific reason string when blocked; None otherwise.
    `final_signal`: the (regime-damped) signal at the time of approval; None
        if blocked before the dampener stage.
    `suggested_quantity`: from RiskGate when approved; None otherwise.
    """
    decision: str
    reason: Optional[str] = None
    final_signal: Optional[SignalResult] = None
    suggested_quantity: Optional[object] = None  # Decimal at runtime


async def run_pipeline(
    profile_state,
    signal: SignalResult,
    tick: NormalisedTick,
    indicators: EvaluatedIndicators,
    *,
    redis_client=None,
    pubsub=None,
) -> PipelineOutcome:
    """Drive a tick through the production gate sequence.

    `redis_client` and `pubsub` are forwarded to the dampener; pass `None`
    to skip HMM regime resolution and disagreement alerts.
    """

    # Gate 1 — Abstention. CRISIS regression caught here.
    abstain_blocked, abstain_reason = AbstentionChecker.check_with_reason(
        profile_state, signal, tick, indicators
    )
    if abstain_blocked:
        return PipelineOutcome("BLOCKED_ABSTENTION", abstain_reason)

    # Gate 2 — Regime Dampener. Note: this overwrites `state.regime` based
    # on the rule-based indicator's update(price, atr), so any pre-set value
    # only survives if the indicator agrees (or the state is a MagicMock —
    # the comparison `MagicMock == Regime.CRISIS` is False, so the dampener
    # treats it as a non-CRISIS regime).
    dampener = RegimeDampener(redis_client=redis_client, pubsub=pubsub)
    damp_res = await dampener.check(profile_state, signal, tick, indicators)
    if not damp_res.proceed:
        return PipelineOutcome("BLOCKED_REGIME", "regime_dampener_no_proceed")
    damped = SignalResult(
        direction=signal.direction,
        confidence=signal.confidence * damp_res.confidence_multiplier,
        rule_matched=signal.rule_matched,
    )

    # Gate 3 — Preferred-regime membership (C.4 SHADOW path).
    if profile_state.preferred_regimes and profile_state.regime is not None:
        if profile_state.regime not in profile_state.preferred_regimes:
            return PipelineOutcome("BLOCKED_REGIME_MISMATCH", "preferred_regime_mismatch")

    # Gate 4 — Circuit Breaker (daily realised PnL pct vs threshold).
    if CircuitBreaker.check(profile_state):
        return PipelineOutcome("BLOCKED_CIRCUIT_BREAKER", "daily_loss_threshold")

    # Gate 5 — Blacklist.
    if BlacklistChecker.check(profile_state, tick.symbol):
        return PipelineOutcome("BLOCKED_BLACKLIST", "symbol_blacklisted")

    # Gate 6 — Risk Gate (drawdown, exposure, sizing).
    risk_res = RiskGate.check(profile_state, damped, tick)
    if risk_res.blocked:
        return PipelineOutcome("BLOCKED_RISK", risk_res.reason)

    return PipelineOutcome(
        decision="APPROVED",
        reason=None,
        final_signal=damped,
        suggested_quantity=risk_res.suggested_quantity,
    )
