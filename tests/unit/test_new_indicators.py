import pytest
import math
from libs.indicators import ADXCalculator, BollingerCalculator, BollingerResult, OBVCalculator, ChoppinessCalculator


# ---------------------------------------------------------------------------
# ADX
# ---------------------------------------------------------------------------

class TestADXCalculator:
    def test_returns_none_during_priming(self):
        adx = ADXCalculator(period=14)
        # Need 2*period bars before first ADX value
        for i in range(20):
            val = adx.update(100 + i, 99 + i, 99.5 + i)
        assert val is None  # still priming at bar 20

    def test_returns_value_after_priming(self):
        adx = ADXCalculator(period=14)
        # Feed 30 bars of trending data — enough to prime (2*14-1 = 27 bars minimum)
        vals = []
        for i in range(35):
            v = adx.update(100 + i * 0.5, 99 + i * 0.5, 99.5 + i * 0.5)
            vals.append(v)
        # At least one non-None value should appear
        non_none = [v for v in vals if v is not None]
        assert len(non_none) > 0
        assert all(0 <= v <= 100 for v in non_none)

    def test_trending_market_high_adx(self):
        adx = ADXCalculator(period=14)
        # Strong uptrend: each bar higher than the last
        last = None
        for i in range(50):
            last = adx.update(100 + i * 2, 99 + i * 2, 99.5 + i * 2)
        assert last is not None
        assert last > 20  # strong trend should produce ADX > 20

    def test_flat_market_low_adx(self):
        adx = ADXCalculator(period=14)
        # Flat market: bars alternate around same level
        last = None
        for i in range(50):
            offset = 0.1 if i % 2 == 0 else -0.1
            last = adx.update(100.5 + offset, 99.5 + offset, 100 + offset)
        assert last is not None
        assert last < 30  # flat market should have lower ADX


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

class TestBollingerCalculator:
    def test_returns_none_during_priming(self):
        bb = BollingerCalculator(period=20)
        for i in range(19):
            val = bb.update(100.0 + i * 0.1)
        assert val is None

    def test_returns_result_at_period(self):
        bb = BollingerCalculator(period=20)
        for i in range(19):
            bb.update(100.0)
        val = bb.update(100.0)
        assert val is not None
        assert isinstance(val, BollingerResult)

    def test_constant_price_zero_bandwidth(self):
        bb = BollingerCalculator(period=5)
        for _ in range(4):
            bb.update(50.0)
        result = bb.update(50.0)
        assert result is not None
        assert result.middle == pytest.approx(50.0)
        assert result.bandwidth == pytest.approx(0.0)
        assert result.pct_b == pytest.approx(0.5)  # at middle

    def test_pct_b_high_when_price_near_upper(self):
        bb = BollingerCalculator(period=20, num_std=2.0)
        # Establish stable base, then spike
        for _ in range(19):
            bb.update(100.0)
        result = bb.update(120.0)
        assert result is not None
        # Price jump should push %B well above 0.5
        assert result.pct_b > 0.9

    def test_pct_b_low_when_price_near_lower(self):
        bb = BollingerCalculator(period=20, num_std=2.0)
        # Establish stable base, then drop
        for _ in range(19):
            bb.update(100.0)
        result = bb.update(80.0)
        assert result is not None
        # Price drop should push %B well below 0.5
        assert result.pct_b < 0.1

    def test_upper_above_lower(self):
        bb = BollingerCalculator(period=5)
        prices = [10, 11, 12, 11, 10]
        result = None
        for p in prices:
            result = bb.update(float(p))
        assert result is not None
        assert result.upper > result.middle > result.lower


# ---------------------------------------------------------------------------
# OBV
# ---------------------------------------------------------------------------

class TestOBVCalculator:
    def test_returns_none_on_first_bar(self):
        obv = OBVCalculator()
        assert obv.update(100.0, 1000.0) is None

    def test_price_up_adds_volume(self):
        obv = OBVCalculator()
        obv.update(100.0, 1000.0)
        val = obv.update(101.0, 500.0)
        assert val == 1500.0  # initial 1000 + 500

    def test_price_down_subtracts_volume(self):
        obv = OBVCalculator()
        obv.update(100.0, 1000.0)
        val = obv.update(99.0, 300.0)
        assert val == 700.0  # initial 1000 - 300

    def test_price_unchanged_no_change(self):
        obv = OBVCalculator()
        obv.update(100.0, 1000.0)
        val = obv.update(100.0, 500.0)
        assert val == 1000.0  # unchanged

    def test_multi_bar_sequence(self):
        obv = OBVCalculator()
        obv.update(10.0, 100.0)          # initial OBV = 100, returns None
        assert obv.update(11.0, 200.0) == 300.0   # up: 100 + 200
        assert obv.update(10.5, 150.0) == 150.0   # down: 300 - 150
        assert obv.update(10.5, 100.0) == 150.0   # flat: no change
        assert obv.update(12.0, 300.0) == 450.0   # up: 150 + 300


# ---------------------------------------------------------------------------
# Choppiness Index
# ---------------------------------------------------------------------------

class TestChoppinessCalculator:
    def test_returns_none_during_priming(self):
        chop = ChoppinessCalculator(period=14)
        for i in range(13):
            val = chop.update(101.0, 99.0, 100.0)
        assert val is None

    def test_returns_value_after_priming(self):
        chop = ChoppinessCalculator(period=14)
        for i in range(14):
            chop.update(101.0 + i * 0.1, 99.0 + i * 0.1, 100.0 + i * 0.1)
        val = chop.update(101.0 + 14 * 0.1, 99.0 + 14 * 0.1, 100.0 + 14 * 0.1)
        assert val is not None
        assert 0.0 <= val <= 100.0

    def test_trending_market_low_choppiness(self):
        chop = ChoppinessCalculator(period=14)
        # Strong trend: consistently moving up
        last = None
        for i in range(30):
            last = chop.update(100 + i * 2 + 1, 100 + i * 2 - 1, 100 + i * 2)
        assert last is not None
        assert last < 50  # trending should have low choppiness

    def test_ranging_market_high_choppiness(self):
        chop = ChoppinessCalculator(period=14)
        # Choppy: alternating up and down within same range
        last = None
        for i in range(30):
            if i % 2 == 0:
                last = chop.update(102, 98, 101)
            else:
                last = chop.update(102, 98, 99)
        assert last is not None
        assert last > 40  # choppy should have higher choppiness

    def test_clamped_0_100(self):
        chop = ChoppinessCalculator(period=5)
        for i in range(20):
            val = chop.update(100 + i, 99 + i, 99.5 + i)
            if val is not None:
                assert 0.0 <= val <= 100.0
