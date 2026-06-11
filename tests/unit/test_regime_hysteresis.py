"""Unit tests for PR6 — regime hysteresis (closes the 2.11 hysteresis gap).

The classifier must not flip the regime every bar when a value hovers near a
threshold. Hysteresis is asymmetric: enter severe regimes at the threshold, leave
them only past a relaxed threshold; prior state (`_current`) is the memory.
"""

from libs.core.enums import Regime
from libs.indicators._regime import SimpleRegimeClassifier

# Controlled percentiles for direct _classify exercise (bypasses the windows).
P95, P75, P50, SMA = 100.0, 50.0, 20.0, 1000.0


def _c(hysteresis=0.10):
    return SimpleRegimeClassifier(hysteresis=hysteresis)


class TestHysteresis:
    def test_warmup_returns_none(self):
        c = SimpleRegimeClassifier(sma_period=5, vol_lookback=5)
        # Fewer than the window length -> not enough data yet.
        assert c.update(100.0, 1.0) is None
        assert c.update(101.0, 1.0) is None

    def test_enters_high_vol_at_threshold(self):
        c = _c()
        c._current = None
        # atr just over p75 -> HIGH_VOLATILITY immediately (fast entry)
        assert c._classify(SMA, 55.0, SMA, P95, P75, P50) == Regime.HIGH_VOLATILITY

    def test_high_vol_is_sticky_within_band(self):
        c = _c(0.10)
        c._current = Regime.HIGH_VOLATILITY
        # atr dipped below p75 (50) but still above the relaxed exit p75*0.9=45
        # -> stays HIGH_VOLATILITY (no thrash)
        assert c._classify(SMA, 47.0, SMA, P95, P75, P50) == Regime.HIGH_VOLATILITY

    def test_high_vol_exits_past_relaxed_threshold(self):
        c = _c(0.10)
        c._current = Regime.HIGH_VOLATILITY
        # atr decisively below the relaxed exit (45) -> leaves HIGH_VOLATILITY
        assert c._classify(SMA, 40.0, SMA, P95, P75, P50) != Regime.HIGH_VOLATILITY

    def test_no_hysteresis_flips_every_bar(self):
        """Control: with hysteresis=0 the same dip below p75 leaves HIGH_VOL —
        confirming the stickiness above is the hysteresis, not luck."""
        c = _c(0.0)
        c._current = Regime.HIGH_VOLATILITY
        assert c._classify(SMA, 47.0, SMA, P95, P75, P50) != Regime.HIGH_VOLATILITY

    def test_crisis_entry_and_sticky_exit(self):
        c = _c(0.10)
        c._current = None
        # vol > p95 and price > 10% below SMA -> CRISIS
        assert c._classify(850.0, 110.0, SMA, P95, P75, P50) == Regime.CRISIS
        # still elevated vol (above p95*0.9=90) and price not fully recovered -> stays
        c._current = Regime.CRISIS
        assert c._classify(950.0, 95.0, SMA, P95, P75, P50) == Regime.CRISIS
        # vol decisively recovered (below 90) -> leaves CRISIS
        c._current = Regime.CRISIS
        assert c._classify(950.0, 80.0, SMA, P95, P75, P50) != Regime.CRISIS

    def test_trending_band_prevents_sma_cross_thrash(self):
        c = _c(0.10)  # band = sma*0.02*0.1 = 2.0
        c._current = Regime.TRENDING_UP
        # atr=30 is between p50 (20) and p75 (50): not RANGE_BOUND, not HIGH_VOL,
        # so it falls through to the trend classification. Price dipped just below
        # SMA but within the band -> stays UP (no flip).
        assert c._classify(999.0, 30.0, SMA, P95, P75, P50) == Regime.TRENDING_UP
        # price clearly below SMA-band -> flips DOWN
        assert c._classify(995.0, 30.0, SMA, P95, P75, P50) == Regime.TRENDING_DOWN
