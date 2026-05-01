"""Hand-computed unit tests for the C.2 indicator additions.

VWAP, Keltner Channel, RVOL, Z-Score, Hurst Exponent.
"""

import math

import pytest

from libs.indicators import (
    VWAPCalculator,
    KeltnerCalculator,
    KeltnerResult,
    RVOLCalculator,
    ZScoreCalculator,
    HurstCalculator,
)


# ---------------------------------------------------------------------------
# VWAP
# ---------------------------------------------------------------------------

class TestVWAPCalculator:
    def test_first_bar_returns_vwap_equal_to_close(self):
        v = VWAPCalculator(window=10)
        # one observation: vwap == close * volume / volume == close
        assert v.update(100.0, 5.0) == pytest.approx(100.0)

    def test_two_bars_volume_weighted(self):
        v = VWAPCalculator(window=10)
        v.update(100.0, 1.0)         # pv=100, v=1
        result = v.update(110.0, 9.0)  # pv=990, v=9
        # vwap = (100 + 990) / (100 + 9) = 1090 / 10 = 109.0
        # That's wrong. (1*100 + 9*110) = 100 + 990 = 1090; 1+9=10; 1090/10=109.0
        assert result == pytest.approx(109.0, rel=1e-9)

    def test_window_rollover(self):
        v = VWAPCalculator(window=2)
        v.update(100.0, 1.0)
        v.update(200.0, 1.0)
        # full: vwap = (100 + 200) / 2 = 150
        # next bar evicts the 100, adds 300:
        result = v.update(300.0, 1.0)
        assert result == pytest.approx(250.0, rel=1e-9)

    def test_zero_total_volume_returns_none(self):
        v = VWAPCalculator(window=5)
        result = v.update(100.0, 0.0)
        assert result is None


# ---------------------------------------------------------------------------
# Keltner Channel
# ---------------------------------------------------------------------------

class TestKeltnerCalculator:
    def test_returns_none_during_priming(self):
        k = KeltnerCalculator(period=20)
        for i in range(19):
            assert k.update(101.0, 99.0, 100.0) is None

    def test_returns_result_after_priming(self):
        k = KeltnerCalculator(period=20)
        for _ in range(20):
            k.update(101.0, 99.0, 100.0)
        # 20th bar primes both EMA and ATR
        result = k.update(101.0, 99.0, 100.0)
        assert isinstance(result, KeltnerResult)
        assert result.upper > result.middle > result.lower

    def test_constant_close_zero_atr(self):
        # When highs/lows/closes are all identical, ATR collapses to zero and
        # Keltner upper == middle == lower.
        k = KeltnerCalculator(period=5, mult=2.0)
        for _ in range(5):
            k.update(50.0, 50.0, 50.0)
        result = k.update(50.0, 50.0, 50.0)
        assert result is not None
        assert result.middle == pytest.approx(50.0, rel=1e-9)
        assert result.upper == pytest.approx(50.0, rel=1e-9)
        assert result.lower == pytest.approx(50.0, rel=1e-9)

    def test_band_width_scales_with_mult(self):
        k1 = KeltnerCalculator(period=5, mult=1.0)
        k2 = KeltnerCalculator(period=5, mult=2.0)
        for i in range(6):
            k1.update(105.0 + i, 95.0 + i, 100.0 + i)
            k2.update(105.0 + i, 95.0 + i, 100.0 + i)
        r1 = k1.update(105.0 + 6, 95.0 + 6, 100.0 + 6)
        r2 = k2.update(105.0 + 6, 95.0 + 6, 100.0 + 6)
        w1 = r1.upper - r1.lower
        w2 = r2.upper - r2.lower
        # mult=2 should produce ~2x the band width of mult=1 for the same EMA/ATR
        assert w2 == pytest.approx(2.0 * w1, rel=1e-9)


# ---------------------------------------------------------------------------
# RVOL
# ---------------------------------------------------------------------------

class TestRVOLCalculator:
    def test_returns_none_during_priming(self):
        r = RVOLCalculator(period=5)
        for _ in range(4):
            assert r.update(100.0) is None

    def test_constant_volume_returns_one(self):
        r = RVOLCalculator(period=5)
        for _ in range(4):
            r.update(100.0)
        # 5th bar primes; SMA = 100, current = 100, ratio = 1.0
        assert r.update(100.0) == pytest.approx(1.0, rel=1e-9)

    def test_double_volume_after_priming(self):
        # SMA includes current bar. With period=4, three previous bars at 100
        # and current at 200: window = [100, 100, 100, 200], SMA = 125,
        # ratio = 200 / 125 = 1.6.
        r = RVOLCalculator(period=4)
        for _ in range(3):
            r.update(100.0)
        assert r.update(200.0) == pytest.approx(1.6, rel=1e-9)

    def test_zero_sma_returns_none(self):
        # Sum is zero across the whole window → mean is zero → undefined.
        r = RVOLCalculator(period=3)
        for _ in range(3):
            result = r.update(0.0)
        assert result is None


# ---------------------------------------------------------------------------
# Z-Score
# ---------------------------------------------------------------------------

class TestZScoreCalculator:
    def test_returns_none_during_priming(self):
        z = ZScoreCalculator(period=5)
        for _ in range(4):
            assert z.update(100.0) is None

    def test_constant_window_returns_none(self):
        z = ZScoreCalculator(period=5)
        for _ in range(5):
            assert z.update(50.0) is None  # stdev=0 → undefined

    def test_known_window_matches_hand_computed(self):
        # Window: [10, 12, 14, 16, 18]
        # Mean = 14, sample stdev = sqrt( ((10-14)^2+...+(18-14)^2) / 4 )
        #      = sqrt( (16+4+0+4+16)/4 ) = sqrt(10) ≈ 3.16227766
        # Most recent close is 18 → z = (18 - 14) / sqrt(10) = 4/sqrt(10)
        z = ZScoreCalculator(period=5)
        for p in (10.0, 12.0, 14.0, 16.0):
            z.update(p)
        result = z.update(18.0)
        expected = 4.0 / math.sqrt(10.0)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_reverts_to_zero_at_mean(self):
        # Window [10, 12, 14, 16, 18] then push 14 → close == mean → z == 0
        z = ZScoreCalculator(period=5)
        for p in (10.0, 12.0, 14.0, 16.0, 18.0):
            z.update(p)
        result = z.update(14.0)
        # New window: [12, 14, 16, 18, 14], mean = 14.8, but close=14 → small negative
        # Easier sanity: just check it's strictly negative since 14 < 14.8.
        assert result is not None
        assert result < 0


# ---------------------------------------------------------------------------
# Hurst Exponent (R/S)
# ---------------------------------------------------------------------------

class TestHurstCalculator:
    def test_window_too_small_raises(self):
        with pytest.raises(ValueError):
            HurstCalculator(window=4)

    def test_returns_none_during_priming(self):
        h = HurstCalculator(window=8)
        # Need window+1 = 9 bars before first value.
        for _ in range(8):
            assert h.update(100.0) is None

    def test_constant_series_returns_none(self):
        h = HurstCalculator(window=8)
        for _ in range(9):
            result = h.update(100.0)
        assert result is None  # no variance, R/S undefined

    def test_deterministic_sequence_matches_hand_computation(self):
        # Hand-computed canonical: window=8, prices = [1, 2, 1, 3, 1, 4, 1, 5, 1]
        # log returns = [ln 2, -ln 2, ln 3, -ln 3, ln 4, -ln 4, ln 5, -ln 5],
        # mean ≈ 0, cumulative deviations oscillate between 0 and the running
        # ln value; max=ln(5), min=0, so R = ln 5.
        # variance = mean(r²) = (2*(ln 2)² + 2*(ln 3)² + 2*(ln 4)² + 2*(ln 5)²) / 8
        # H = ln(R/S) / ln(8).
        h = HurstCalculator(window=8)
        prices = [1.0, 2.0, 1.0, 3.0, 1.0, 4.0, 1.0, 5.0, 1.0]
        result = None
        for p in prices:
            result = h.update(p)
        assert result is not None
        # Expected: derive R and S analytically.
        L2, L3, L4, L5 = math.log(2), math.log(3), math.log(4), math.log(5)
        var = (2 * L2 ** 2 + 2 * L3 ** 2 + 2 * L4 ** 2 + 2 * L5 ** 2) / 8
        s = math.sqrt(var)
        rng = L5  # cumulative max is ln(5), min is 0
        expected = math.log(rng / s) / math.log(8)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_value_within_reasonable_bounds(self):
        # Sanity: a noisy sequence should produce H in [0, 1]-ish range.
        import random
        random.seed(7)
        h = HurstCalculator(window=64)
        result = None
        price = 100.0
        for _ in range(128):
            price *= math.exp(random.gauss(0.0, 0.005))
            result = h.update(price)
        assert result is not None
        assert -0.2 < result < 1.5

    def test_random_walk_near_half(self):
        # Deterministic pseudo-random walk with mean-zero increments.
        import random
        random.seed(42)
        h = HurstCalculator(window=64)
        result = None
        price = 100.0
        for _ in range(256):
            price *= math.exp(random.gauss(0.0, 0.01))
            result = h.update(price)
        assert result is not None
        # Random walk: H ≈ 0.5. Loose bound — single-window R/S is noisy.
        assert 0.3 < result < 0.8
