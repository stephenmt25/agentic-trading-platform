from dataclasses import dataclass
from typing import Optional

from ._ema import EMACalculator
from ._atr import ATRCalculator


@dataclass(frozen=True, slots=True)
class KeltnerResult:
    upper: float
    middle: float
    lower: float


class KeltnerCalculator:
    """Keltner Channel = EMA(close, period) +/- mult * ATR(period).

    update(high, low, close) -> Optional[KeltnerResult]
    Returns None until both the EMA and ATR have primed.
    """

    __slots__ = ("period", "mult", "_ema", "_atr")

    def __init__(self, period: int = 20, mult: float = 2.0):
        self.period = period
        self.mult = mult
        self._ema = EMACalculator(period=period)
        self._atr = ATRCalculator(period=period)

    def update(self, high: float, low: float, close: float) -> Optional[KeltnerResult]:
        ema_val = self._ema.update(close)
        atr_val = self._atr.update(high, low, close)
        if ema_val is None or atr_val is None:
            return None
        upper = ema_val + self.mult * atr_val
        lower = ema_val - self.mult * atr_val
        return KeltnerResult(upper=upper, middle=ema_val, lower=lower)
