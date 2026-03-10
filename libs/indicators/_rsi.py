import numpy as np
from typing import Optional

class RSICalculator:
    __slots__ = ('period', 'window_size', 'prices', 'count', 'avg_gain', 'avg_loss')

    def __init__(self, period: int = 14, window_size: int = 1000):
        self.period = period
        self.window_size = window_size
        self.prices = np.zeros(window_size, dtype=np.float64)
        self.count = 0
        self.avg_gain = 0.0
        self.avg_loss = 0.0

    def update(self, price: float) -> Optional[float]:
        idx = self.count % self.window_size
        self.prices[idx] = price
        
        if self.count == 0:
            self.count += 1
            return None

        prev_price = self.prices[(self.count - 1) % self.window_size]
        change = price - prev_price
        
        gain = change if change > 0 else 0.0
        loss = -change if change < 0 else 0.0

        if self.count < self.period:
            self.avg_gain += gain
            self.avg_loss += loss
            self.count += 1
            return None
        elif self.count == self.period:
            self.avg_gain = (self.avg_gain + gain) / self.period
            self.avg_loss = (self.avg_loss + loss) / self.period
            self.count += 1
        else:
            self.avg_gain = ((self.avg_gain * (self.period - 1)) + gain) / self.period
            self.avg_loss = ((self.avg_loss * (self.period - 1)) + loss) / self.period
            self.count += 1

        if self.avg_loss == 0:
            return 100.0
            
        rs = self.avg_gain / self.avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
