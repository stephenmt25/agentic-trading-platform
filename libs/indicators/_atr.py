from typing import Optional

class ATRCalculator:
    __slots__ = ('period', 'count', 'sum_tr', 'atr', 'prev_close')

    def __init__(self, period: int = 14):
        self.period = period
        self.count = 0
        self.sum_tr = 0.0
        self.atr = 0.0
        self.prev_close = 0.0

    def update(self, high: float, low: float, close: float) -> Optional[float]:
        if self.count == 0:
            tr = high - low
            self.sum_tr += tr
            self.prev_close = close
            self.count += 1
            return None

        tr = max(
            high - low,
            abs(high - self.prev_close),
            abs(low - self.prev_close)
        )
        self.prev_close = close

        if self.count < self.period:
            self.sum_tr += tr
            self.count += 1
            if self.count == self.period:
                self.atr = self.sum_tr / self.period
                return self.atr
            return None
        else:
            self.atr = ((self.atr * (self.period - 1)) + tr) / self.period
            self.count += 1
            return self.atr
