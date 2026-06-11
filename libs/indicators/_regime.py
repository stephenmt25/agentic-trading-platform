from typing import Optional

import numpy as np

from libs.core.enums import Regime


class SimpleRegimeClassifier:
    """Rule-based regime classifier with hysteresis (PR6 — closes the 2.11 gap).

    Without prior-state memory, a value hovering near a threshold (e.g. ATR at
    the 75th percentile) flips the regime every bar — boundary thrash that
    whipsaws the regime-dampened sizing. Hysteresis is ASYMMETRIC: a more severe
    regime (CRISIS, HIGH_VOLATILITY) is ENTERED at the normal threshold (react
    fast to rising risk), but only LEFT once the signal crosses a relaxed
    threshold `hysteresis` below it (sticky on the way down). That is the safe
    direction for a trading system: quick to de-risk, slow to re-risk.
    """

    __slots__ = (
        "sma_period",
        "vol_lookback",
        "hysteresis",
        "prices",
        "atrs",
        "price_count",
        "atr_count",
        "sum_price",
        "_current",
    )

    def __init__(
        self, sma_period: int = 200, vol_lookback: int = 90, hysteresis: float = 0.10
    ):
        self.sma_period = sma_period
        self.vol_lookback = vol_lookback
        # Relaxation band for leaving a regime, as a fraction of the threshold.
        self.hysteresis = hysteresis
        self.prices = np.zeros(sma_period, dtype=np.float64)
        self.atrs = np.zeros(vol_lookback, dtype=np.float64)
        self.price_count = 0
        self.atr_count = 0
        self.sum_price = 0.0
        self._current: Optional[Regime] = None  # prior-state memory

    @property
    def current(self) -> Optional[Regime]:
        return self._current

    def update(self, price: float, atr: float) -> Optional[Regime]:
        # Update SMA
        idx = self.price_count % self.sma_period
        old_price = self.prices[idx]
        self.prices[idx] = price
        self.sum_price = self.sum_price - old_price + price
        self.price_count += 1

        # Update ATR
        a_idx = self.atr_count % self.vol_lookback
        self.atrs[a_idx] = atr
        self.atr_count += 1

        if self.price_count < self.sma_period or self.atr_count < self.vol_lookback:
            return None

        sma = self.sum_price / self.sma_period
        p95_atr = np.percentile(self.atrs, 95)
        p75_atr = np.percentile(self.atrs, 75)
        p50_atr = np.percentile(self.atrs, 50)

        self._current = self._classify(price, atr, sma, p95_atr, p75_atr, p50_atr)
        return self._current

    def _classify(self, price, atr, sma, p95, p75, p50) -> Regime:
        h = self.hysteresis
        cur = self._current
        crisis_price = sma * 0.90

        # --- CRISIS (highest priority): vol > 95th pctl AND price > 10% below SMA.
        # Enter at the threshold; once in CRISIS, stay until BOTH vol and price
        # have decisively recovered past the relaxed band.
        if atr > p95 and price < crisis_price:
            return Regime.CRISIS
        if (
            cur == Regime.CRISIS
            and atr > p95 * (1 - h)
            and price < crisis_price * (1 + h)
        ):
            return Regime.CRISIS

        # --- HIGH_VOLATILITY: vol > 75th pctl. Sticky exit at p75*(1-h).
        if atr > p75:
            return Regime.HIGH_VOLATILITY
        if cur == Regime.HIGH_VOLATILITY and atr > p75 * (1 - h):
            return Regime.HIGH_VOLATILITY

        # --- RANGE_BOUND: within 2% of SMA AND vol < 50th. Relaxed exit band.
        dist = abs(price - sma) / sma if sma else 0.0
        if dist <= 0.02 and atr < p50:
            return Regime.RANGE_BOUND
        if cur == Regime.RANGE_BOUND and dist <= 0.02 * (1 + h) and atr < p50 * (1 + h):
            return Regime.RANGE_BOUND

        # --- TRENDING: price vs SMA, with a small band around the SMA cross so a
        # price oscillating around the mean doesn't flip UP/DOWN every bar.
        band = sma * 0.02 * h
        if cur == Regime.TRENDING_UP:
            return Regime.TRENDING_UP if price >= sma - band else Regime.TRENDING_DOWN
        if cur == Regime.TRENDING_DOWN:
            return Regime.TRENDING_DOWN if price <= sma + band else Regime.TRENDING_UP
        return Regime.TRENDING_UP if price > sma else Regime.TRENDING_DOWN
