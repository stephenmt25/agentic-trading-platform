from ._rsi import RSICalculator
from ._ema import EMACalculator
from ._macd import MACDCalculator, MACDResult
from ._atr import ATRCalculator
from ._regime import SimpleRegimeClassifier

from typing import Dict, Any

class IndicatorSet:
    __slots__ = ('rsi', 'macd', 'atr', 'regime')
    
    def __init__(self, rsi: RSICalculator, macd: MACDCalculator, atr: ATRCalculator, regime: SimpleRegimeClassifier):
        self.rsi = rsi
        self.macd = macd
        self.atr = atr
        self.regime = regime

def create_indicator_set(profile_config: Dict[str, Any] = None) -> IndicatorSet:
    # Later profile_config allows customization of periods
    return IndicatorSet(
        rsi=RSICalculator(),
        macd=MACDCalculator(),
        atr=ATRCalculator(),
        regime=SimpleRegimeClassifier()
    )

__all__ = [
    "RSICalculator",
    "EMACalculator",
    "MACDCalculator",
    "MACDResult",
    "ATRCalculator",
    "SimpleRegimeClassifier",
    "IndicatorSet",
    "create_indicator_set"
]
