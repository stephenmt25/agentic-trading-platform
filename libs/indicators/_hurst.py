import math
from typing import Optional


class HurstCalculator:
    """Hurst Exponent via single-window R/S analysis on log-returns.

    H ≈ 0.5  → random walk
    H > 0.5  → trending / persistent
    H < 0.5  → mean-reverting / anti-persistent

    update(close) -> Optional[float]
    Returns None until `window + 1` bars have been observed (need `window`
    log-returns). Computes one R/S value per call against the most recent
    `window` returns and returns log(R/S) / log(window) — the simple-window
    estimator. Multi-window aggregated Hurst is more accurate but ~20× slower
    and not needed at the per-tick latency budget.

    Window default 50 keeps per-tick cost to single-digit microseconds in pure
    Python. If the window contains a constant series (R==0 or S==0), Hurst is
    undefined and None is returned.
    """

    __slots__ = ("window", "_buf", "_idx", "_count")

    def __init__(self, window: int = 50):
        if window < 8:
            raise ValueError("window must be >= 8 for a meaningful R/S estimate")
        self.window = window
        # Need window+1 prices to derive `window` returns. Allocate +1 slot.
        self._buf: list[float] = [0.0] * (window + 1)
        self._idx = 0
        self._count = 0

    def update(self, close: float) -> Optional[float]:
        cap = self.window + 1
        if self._count < cap:
            self._buf[self._count] = close
            self._count += 1
            if self._count < cap:
                return None
        else:
            self._buf[self._idx] = close
            self._idx = (self._idx + 1) % cap

        # Reconstruct window in temporal order starting from oldest slot.
        if self._count < cap:
            prices = self._buf[: self._count]
        else:
            prices = self._buf[self._idx:] + self._buf[: self._idx]

        # Log returns
        n = self.window
        returns = [0.0] * n
        for i in range(n):
            p0 = prices[i]
            p1 = prices[i + 1]
            if p0 <= 0 or p1 <= 0:
                return None
            returns[i] = math.log(p1 / p0)

        mean_r = sum(returns) / n
        # Cumulative deviation, range, and stdev
        cum = 0.0
        cmin = math.inf
        cmax = -math.inf
        sq_sum = 0.0
        for r in returns:
            d = r - mean_r
            cum += d
            if cum < cmin:
                cmin = cum
            if cum > cmax:
                cmax = cum
            sq_sum += d * d
        rng = cmax - cmin
        # Population stdev — denominator n is the canonical R/S form.
        std = math.sqrt(sq_sum / n)
        if rng == 0.0 or std == 0.0:
            return None
        rs = rng / std
        # log(R/S) / log(n) — single-window Hurst estimator.
        return math.log(rs) / math.log(n)
