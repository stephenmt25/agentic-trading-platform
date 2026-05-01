from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from libs.core.enums import Regime
from libs.core.models import NormalisedTick
from .state import ProfileState
from .strategy_eval import SignalResult

_ZERO = Decimal("0")
_MIN_TRADE_DOLLARS = Decimal("10")


@dataclass(frozen=True, slots=True)
class RiskGateResult:
    blocked: bool
    suggested_quantity: Decimal
    reason: Optional[str] = None


class RiskGate:
    @staticmethod
    def check(state: ProfileState, signal: SignalResult, tick: NormalisedTick) -> RiskGateResult:
        """Block if the profile is out of risk room or free capital; otherwise
        return a dollar-bounded suggested quantity in asset units.

        Sizing is now equity-aware. Trade dollars come from the profile's free
        capital (`notional - open_exposure_dollars`), scaled by
        `max_allocation_pct × confidence`, dampened for drawdown / regime, and
        finally divided by current price. Previously `suggested_quantity` was
        returned as a raw fraction that was treated as asset units downstream
        — that made BTC trades ~33× larger than ETH trades for the same
        configuration and let exposure stack past notional.
        """
        max_alloc = state.risk_limits.max_allocation_pct
        max_dd = state.risk_limits.max_drawdown_pct
        notional = state.notional
        open_exposure = state.open_exposure_dollars
        free_capital = max(_ZERO, notional - open_exposure)
        price = tick.price if tick.price > _ZERO else _ZERO

        # 1. Drawdown gate
        if state.current_drawdown_pct > max_dd:
            return RiskGateResult(blocked=True, suggested_quantity=_ZERO, reason="drawdown_limit_exceeded")

        # 2. Aggregate exposure cap — open positions already use the profile's
        # full notional, no room to add more.
        if free_capital <= _ZERO:
            return RiskGateResult(blocked=True, suggested_quantity=_ZERO, reason="exposure_at_notional")

        # 3. Sane price required to size in asset units
        if price <= _ZERO:
            return RiskGateResult(blocked=True, suggested_quantity=_ZERO, reason="invalid_price")

        confidence = Decimal(str(signal.confidence))
        trade_dollars = free_capital * max_alloc * confidence

        # Reduce by 50% if drawdown > half of limit
        if max_dd > 0 and state.current_drawdown_pct > (max_dd / 2):
            trade_dollars *= Decimal("0.5")

        # Reduce by 30% if HIGH_VOLATILITY regime
        if state.regime == Regime.HIGH_VOLATILITY:
            trade_dollars *= Decimal("0.7")

        # 4. Skip dust trades — exchange minimums make sub-$10 fills impossible
        if trade_dollars < _MIN_TRADE_DOLLARS:
            return RiskGateResult(blocked=True, suggested_quantity=_ZERO, reason="trade_below_minimum")

        qty = trade_dollars / price
        return RiskGateResult(blocked=False, suggested_quantity=qty)
