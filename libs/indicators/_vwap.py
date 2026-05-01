from typing import Optional


class VWAPCalculator:
    """Volume-Weighted Average Price over a rolling window of bars.

    update(close, volume) -> Optional[float]
    Returns None on the very first bar (no observations yet). After that the
    rolling sum window grows until it reaches `window` bars, at which point
    the oldest bar is replaced with the newest. Memory is O(window).

    Default window is 1440 bars — suits a 24h VWAP on 1-minute candles. Pick a
    smaller window for higher timeframes.
    """

    __slots__ = ("window", "_pv_buf", "_v_buf", "_idx", "_count", "_sum_pv", "_sum_v")

    def __init__(self, window: int = 1440):
        if window < 1:
            raise ValueError("window must be >= 1")
        self.window = window
        self._pv_buf: list[float] = [0.0] * window
        self._v_buf: list[float] = [0.0] * window
        self._idx = 0
        self._count = 0
        self._sum_pv = 0.0
        self._sum_v = 0.0

    def update(self, close: float, volume: float) -> Optional[float]:
        pv = close * volume
        if self._count < self.window:
            self._pv_buf[self._count] = pv
            self._v_buf[self._count] = volume
            self._sum_pv += pv
            self._sum_v += volume
            self._count += 1
        else:
            old_pv = self._pv_buf[self._idx]
            old_v = self._v_buf[self._idx]
            self._sum_pv += pv - old_pv
            self._sum_v += volume - old_v
            self._pv_buf[self._idx] = pv
            self._v_buf[self._idx] = volume
            self._idx = (self._idx + 1) % self.window

        if self._sum_v <= 0:
            return None
        return self._sum_pv / self._sum_v
