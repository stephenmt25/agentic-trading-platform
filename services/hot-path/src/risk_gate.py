from libs.core.models import NormalisedTick
from .state import ProfileState
from .strategy_eval import SignalResult

class RiskGate:
    @staticmethod
    def check(state: ProfileState, signal: SignalResult, tick: NormalisedTick) -> bool:
        """
        True = blocked.
        Checks allocation limits and drawdown violations pre-trade.
        """
        if state.current_allocation_pct >= float(state.risk_limits.max_allocation_pct):
            return True
            
        if state.current_drawdown_pct > float(state.risk_limits.max_drawdown_pct):
            return True
            
        return False
