from dataclasses import dataclass
from typing import Optional
import math


@dataclass(frozen=True, slots=True)
class BollingerResult:
    upper: float
    middle: float
    lower: float
    bandwidth: float
    pct_b: float


class BollingerCalculator:
    """Bollinger Bands (SMA-based) with bandwidth and %B.

    update(close) -> Optional[BollingerResult]
    Returns None during the priming period (first `period - 1` bars).
    """

    __slots__ = ('period', 'num_std', 'count', '_buf', '_sum', '_sum_sq')

    def __init__(self, period: int = 20, num_std: float = 2.0):
        self.period = period
        self.num_std = num_std
        self.count = 0
        self._buf: list[float] = []
        self._sum = 0.0
        self._sum_sq = 0.0

    def update(self, close: float) -> Optional[BollingerResult]:
        # Ring-buffer style: append until full, then replace oldest
        if self.count < self.period:
            self._buf.append(close)
            self._sum += close
            self._sum_sq += close * close
            self.count += 1
            if self.count < self.period:
                return None
        else:
            idx = self.count % self.period
            old = self._buf[idx]
            self._sum += close - old
            self._sum_sq += close * close - old * old
            self._buf[idx] = close
            self.count += 1

        mean = self._sum / self.period
        variance = (self._sum_sq / self.period) - (mean * mean)
        # Guard against floating-point noise producing tiny negative variance
        std = math.sqrt(max(0.0, variance))

        upper = mean + self.num_std * std
        lower = mean - self.num_std * std
        bandwidth = (upper - lower) / mean if mean > 0 else 0.0
        band_range = upper - lower
        pct_b = (close - lower) / band_range if band_range > 0 else 0.5

        return BollingerResult(
            upper=upper,
            middle=mean,
            lower=lower,
            bandwidth=bandwidth,
            pct_b=pct_b,
        )
