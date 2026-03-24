from typing import Optional
import math


class ChoppinessCalculator:
    """Choppiness Index (0-100). High values (>61) = choppy/ranging, low (<38) = trending.

    update(high, low, close) -> Optional[float]
    Returns None during the priming period.
    Uses a rolling sum of ATR(1) over `period` bars divided by the
    highest-high minus lowest-low over the same window.
    """

    __slots__ = ('period', 'count', 'prev_close', '_tr_buf', '_high_buf', '_low_buf')

    def __init__(self, period: int = 14):
        self.period = period
        self.count = 0
        self.prev_close = 0.0
        self._tr_buf: list[float] = []
        self._high_buf: list[float] = []
        self._low_buf: list[float] = []

    def update(self, high: float, low: float, close: float) -> Optional[float]:
        if self.count == 0:
            self.prev_close = close
            self._high_buf.append(high)
            self._low_buf.append(low)
            # First bar: TR = high - low (no previous close)
            self._tr_buf.append(high - low)
            self.count = 1
            return None

        # True Range
        tr = max(
            high - low,
            abs(high - self.prev_close),
            abs(low - self.prev_close),
        )
        self.prev_close = close
        self.count += 1

        # Maintain rolling buffers of size `period`
        if len(self._tr_buf) < self.period:
            self._tr_buf.append(tr)
            self._high_buf.append(high)
            self._low_buf.append(low)
        else:
            idx = (self.count - 1) % self.period
            self._tr_buf[idx] = tr
            self._high_buf[idx] = high
            self._low_buf[idx] = low

        if len(self._tr_buf) < self.period:
            return None

        atr_sum = sum(self._tr_buf)
        highest_high = max(self._high_buf)
        lowest_low = min(self._low_buf)
        hl_range = highest_high - lowest_low

        if hl_range <= 0:
            return 0.0

        # CHOP = 100 * LOG10(sum(TR, period) / (HH - LL)) / LOG10(period)
        chop = 100.0 * math.log10(atr_sum / hl_range) / math.log10(self.period)
        return max(0.0, min(100.0, chop))
