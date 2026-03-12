from dataclasses import dataclass
from typing import Optional
from libs.core.enums import Regime
from libs.core.models import NormalisedTick
from .state import ProfileState
from .strategy_eval import SignalResult


@dataclass(frozen=True, slots=True)
class RiskGateResult:
    blocked: bool
    suggested_quantity: float
    reason: Optional[str] = None


class RiskGate:
    @staticmethod
    def check(state: ProfileState, signal: SignalResult, tick: NormalisedTick) -> RiskGateResult:
        """
        Returns RiskGateResult with blocking status and dynamic position sizing.
        """
        max_alloc = float(state.risk_limits.max_allocation_pct)
        max_dd = float(state.risk_limits.max_drawdown_pct)

        if state.current_allocation_pct >= max_alloc:
            return RiskGateResult(blocked=True, suggested_quantity=0.0, reason="allocation_limit_reached")

        if state.current_drawdown_pct > max_dd:
            return RiskGateResult(blocked=True, suggested_quantity=0.0, reason="drawdown_limit_exceeded")

        # Dynamic position sizing
        base_qty = max_alloc * signal.confidence

        # Reduce by 50% if drawdown > half of limit
        if max_dd > 0 and state.current_drawdown_pct > (max_dd / 2):
            base_qty *= 0.5

        # Reduce by 30% if HIGH_VOLATILITY regime
        if state.regime == Regime.HIGH_VOLATILITY:
            base_qty *= 0.7

        base_qty = max(0.0, base_qty)

        return RiskGateResult(blocked=False, suggested_quantity=base_qty)
