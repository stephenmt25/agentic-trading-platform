from typing import Optional


class ADXCalculator:
    """Average Directional Index using Wilder smoothing.

    update(high, low, close) -> Optional[float]  (0-100 scale)
    Returns None during the priming period (2 * period - 1 bars).
    """

    __slots__ = (
        'period', 'count', 'prev_high', 'prev_low', 'prev_close',
        'smoothed_plus_dm', 'smoothed_minus_dm', 'smoothed_tr',
        'dx_sum', 'adx',
    )

    def __init__(self, period: int = 14):
        self.period = period
        self.count = 0
        self.prev_high = 0.0
        self.prev_low = 0.0
        self.prev_close = 0.0
        self.smoothed_plus_dm = 0.0
        self.smoothed_minus_dm = 0.0
        self.smoothed_tr = 0.0
        self.dx_sum = 0.0
        self.adx = 0.0

    def update(self, high: float, low: float, close: float) -> Optional[float]:
        if self.count == 0:
            self.prev_high = high
            self.prev_low = low
            self.prev_close = close
            self.count = 1
            return None

        # True Range
        tr = max(
            high - low,
            abs(high - self.prev_close),
            abs(low - self.prev_close),
        )

        # Directional Movement
        up_move = high - self.prev_high
        down_move = self.prev_low - low
        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0

        self.prev_high = high
        self.prev_low = low
        self.prev_close = close
        self.count += 1

        # Phase 1: accumulate first `period` bars of DM and TR (bars 1..period)
        if self.count <= self.period:
            self.smoothed_plus_dm += plus_dm
            self.smoothed_minus_dm += minus_dm
            self.smoothed_tr += tr
            return None

        # Phase 2: first Wilder smooth at bar == period + 1
        if self.count == self.period + 1:
            self.smoothed_plus_dm = self.smoothed_plus_dm - (self.smoothed_plus_dm / self.period) + plus_dm
            self.smoothed_minus_dm = self.smoothed_minus_dm - (self.smoothed_minus_dm / self.period) + minus_dm
            self.smoothed_tr = self.smoothed_tr - (self.smoothed_tr / self.period) + tr
        else:
            # Subsequent Wilder smoothing
            self.smoothed_plus_dm = self.smoothed_plus_dm - (self.smoothed_plus_dm / self.period) + plus_dm
            self.smoothed_minus_dm = self.smoothed_minus_dm - (self.smoothed_minus_dm / self.period) + minus_dm
            self.smoothed_tr = self.smoothed_tr - (self.smoothed_tr / self.period) + tr

        # +DI / -DI
        if self.smoothed_tr > 0:
            plus_di = 100.0 * self.smoothed_plus_dm / self.smoothed_tr
            minus_di = 100.0 * self.smoothed_minus_dm / self.smoothed_tr
        else:
            plus_di = 0.0
            minus_di = 0.0

        # DX
        di_sum = plus_di + minus_di
        dx = 100.0 * abs(plus_di - minus_di) / di_sum if di_sum > 0 else 0.0

        # Accumulate DX for first ADX (need `period` DX values)
        bars_since_smooth = self.count - self.period
        if bars_since_smooth <= self.period:
            self.dx_sum += dx
            if bars_since_smooth == self.period:
                self.adx = self.dx_sum / self.period
                return self.adx
            return None

        # Wilder-smoothed ADX
        self.adx = ((self.adx * (self.period - 1)) + dx) / self.period
        return self.adx
