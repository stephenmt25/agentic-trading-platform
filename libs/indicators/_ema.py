from typing import Optional

class EMACalculator:
    __slots__ = ('period', 'multiplier', 'count', 'sum_prices', 'ema')

    def __init__(self, period: int):
        self.period = period
        self.multiplier = 2.0 / (period + 1.0)
        self.count = 0
        self.sum_prices = 0.0
        self.ema = 0.0

    def update(self, price: float) -> Optional[float]:
        if self.count < self.period:
            self.sum_prices += price
            self.count += 1
            if self.count == self.period:
                self.ema = self.sum_prices / self.period
                return self.ema
            return None
        else:
            self.ema = (price - self.ema) * self.multiplier + self.ema
            self.count += 1
            return self.ema
