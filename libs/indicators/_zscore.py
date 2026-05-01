import math
from typing import Optional


class ZScoreCalculator:
    """Rolling z-score: (close - SMA(close, period)) / sample_stdev(close, period).

    update(close) -> Optional[float]
    Returns None until `period` bars have been observed, or when stdev is zero
    (e.g. a constant price window) — both conditions leave the score undefined.
    Uses sample stdev (ddof=1) to match the partner-feedback Z-score reference.
    """

    __slots__ = ("period", "_buf", "_idx", "_count", "_sum", "_sum_sq")

    def __init__(self, period: int = 20):
        if period < 2:
            raise ValueError("period must be >= 2 (sample stdev requires >=2 obs)")
        self.period = period
        self._buf: list[float] = [0.0] * period
        self._idx = 0
        self._count = 0
        self._sum = 0.0
        self._sum_sq = 0.0

    def update(self, close: float) -> Optional[float]:
        if self._count < self.period:
            self._buf[self._count] = close
            self._sum += close
            self._sum_sq += close * close
            self._count += 1
            if self._count < self.period:
                return None
        else:
            old = self._buf[self._idx]
            self._sum += close - old
            self._sum_sq += close * close - old * old
            self._buf[self._idx] = close
            self._idx = (self._idx + 1) % self.period

        n = self.period
        mean = self._sum / n
        # Sample variance: (Σx² − n·mean²) / (n−1).
        variance = max(0.0, (self._sum_sq - n * mean * mean) / (n - 1))
        stdev = math.sqrt(variance)
        if stdev == 0.0:
            return None
        return (close - mean) / stdev
