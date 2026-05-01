from typing import Optional, Tuple
from libs.core.enums import Regime, SignalDirection
from libs.core.models import NormalisedTick
from .state import ProfileState
from .strategy_eval import SignalResult, EvaluatedIndicators


class AbstentionChecker:
    # TEST-ONLY: crisis_regime short-circuit temporarily disabled to allow trading
    # under high-volatility regimes during dashboard testing. Re-enable before any
    # paper or live run that should be trusted.
    @staticmethod
    def check(state: ProfileState, signal: SignalResult, tick: NormalisedTick, inds: EvaluatedIndicators) -> bool:
        # True = abstain

        # 1. ATR < 0.3% of price (Whipsaw protection)
        price = float(tick.price)  # float-ok: indicator library requires float
        if inds.atr < (price * 0.003):
            return True

        # 2. Regime CRISIS — DISABLED for testing
        # if state.regime == Regime.CRISIS:
        #     return True

        # 3. Conflicting signals (Not strictly defined here for basic rules, but standard pattern)
        if signal.direction == SignalDirection.ABSTAIN:
            return True

        return False

    @staticmethod
    def check_with_reason(
        state: ProfileState, signal: SignalResult, tick: NormalisedTick, inds: EvaluatedIndicators
    ) -> Tuple[bool, Optional[str]]:
        """Returns (blocked, reason) — same logic as check() but with reason string."""
        price = float(tick.price)
        if inds.atr < (price * 0.003):
            return True, f"low_atr ({inds.atr:.4f} < {price * 0.003:.4f})"

        # Regime CRISIS — DISABLED for testing (matches check() above)
        # if state.regime == Regime.CRISIS:
        #     return True, "crisis_regime"

        if signal.direction == SignalDirection.ABSTAIN:
            return True, "signal_abstain"

        return False, None
