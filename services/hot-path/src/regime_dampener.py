from dataclasses import dataclass
from typing import Optional
from libs.core.enums import Regime
from libs.core.models import NormalisedTick
from .state import ProfileState
from .strategy_eval import SignalResult, EvaluatedIndicators

@dataclass(frozen=True, slots=True)
class DampenerResult:
    proceed: bool
    confidence_multiplier: float

class RegimeDampener:
    @staticmethod
    def check(state: ProfileState, signal: SignalResult, tick: NormalisedTick, inds: EvaluatedIndicators) -> DampenerResult:
        price = float(tick.price)
        
        # Update Regime
        state.regime = state.indicators.regime.update(price, inds.atr)
        
        if state.regime == Regime.CRISIS:
            return DampenerResult(proceed=False, confidence_multiplier=0.0)
            
        if state.regime == Regime.HIGH_VOLATILITY:
            return DampenerResult(proceed=True, confidence_multiplier=0.7)
            
        return DampenerResult(proceed=True, confidence_multiplier=1.0)
