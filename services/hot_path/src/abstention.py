from libs.core.enums import Regime, SignalDirection
from libs.core.models import NormalisedTick
from .state import ProfileState
from .strategy_eval import SignalResult, EvaluatedIndicators

class AbstentionChecker:
    @staticmethod
    def check(state: ProfileState, signal: SignalResult, tick: NormalisedTick, inds: EvaluatedIndicators) -> bool:
        # True = abstain
        
        # 1. ATR < 0.3% of price (Whipsaw protection)
        price = float(tick.price)
        if inds.atr < (price * 0.003):
            return True
            
        # 2. Regime CRISIS
        if state.regime == Regime.CRISIS:
            return True
            
        # 3. Conflicting signals (Not strictly defined here for basic rules, but standard pattern)
        if signal.direction == SignalDirection.ABSTAIN:
            return True
            
        return False
