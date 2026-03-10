from typing import Optional
from dataclasses import dataclass
from ._ema import EMACalculator

@dataclass(frozen=True, slots=True)
class MACDResult:
    macd_line: float
    signal_line: float
    histogram: float

class MACDCalculator:
    __slots__ = ('fast_ema', 'slow_ema', 'signal_ema')

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast_ema = EMACalculator(fast)
        self.slow_ema = EMACalculator(slow)
        self.signal_ema = EMACalculator(signal)

    def update(self, price: float) -> Optional[MACDResult]:
        fast_val = self.fast_ema.update(price)
        slow_val = self.slow_ema.update(price)

        if slow_val is None or fast_val is None:
            return None

        macd_line = fast_val - slow_val
        signal_line = self.signal_ema.update(macd_line)

        if signal_line is None:
            return None

        return MACDResult(
            macd_line=macd_line,
            signal_line=signal_line,
            histogram=macd_line - signal_line
        )
