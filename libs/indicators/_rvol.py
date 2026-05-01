from typing import Optional


class RVOLCalculator:
    """Relative Volume = current_volume / SMA(volume, period).

    update(volume) -> Optional[float]
    Returns None until `period` bars have been observed. Returns None when the
    historical SMA is zero (avoid divide-by-zero on quiet markets).
    """

    __slots__ = ("period", "_buf", "_idx", "_count", "_sum")

    def __init__(self, period: int = 20):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self._buf: list[float] = [0.0] * period
        self._idx = 0
        self._count = 0
        self._sum = 0.0

    def update(self, volume: float) -> Optional[float]:
        if self._count < self.period:
            self._buf[self._count] = volume
            self._sum += volume
            self._count += 1
            if self._count < self.period:
                return None
            mean = self._sum / self.period
            return volume / mean if mean > 0 else None

        old = self._buf[self._idx]
        self._sum += volume - old
        self._buf[self._idx] = volume
        self._idx = (self._idx + 1) % self.period
        mean = self._sum / self.period
        return volume / mean if mean > 0 else None
