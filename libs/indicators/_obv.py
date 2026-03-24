from typing import Optional


class OBVCalculator:
    """On-Balance Volume — cumulative volume weighted by price direction.

    update(close, volume) -> Optional[float]
    Returns None on the very first bar (no prior close to compare).
    """

    __slots__ = ('prev_close', 'obv', 'count')

    def __init__(self):
        self.prev_close = 0.0
        self.obv = 0.0
        self.count = 0

    def update(self, close: float, volume: float) -> Optional[float]:
        if self.count == 0:
            self.prev_close = close
            self.obv = volume
            self.count = 1
            return None

        if close > self.prev_close:
            self.obv += volume
        elif close < self.prev_close:
            self.obv -= volume
        # If close == prev_close, OBV stays unchanged

        self.prev_close = close
        self.count += 1
        return self.obv
