"""Tests for Regime HMM service: model fit, state prediction, regime mapping."""

import numpy as np
import pytest

from libs.core.enums import Regime
from services.regime_hmm.src.hmm_model import HMMRegimeModel
from services.regime_hmm.src.regime_mapper import map_state_to_regime


# ---------------------------------------------------------------------------
# HMMRegimeModel tests
# ---------------------------------------------------------------------------

class TestHMMRegimeModel:
    def _noisy_prices(self, n=500, start=100.0):
        """Generate a multi-regime price series suitable for HMM fitting.

        Uses percentage returns to produce well-scaled log-return features.
        Alternates between trending/volatile/calm periods so the HMM
        can identify distinct states.
        """
        rng = np.random.RandomState(5)
        prices = [start]
        for i in range(n - 1):
            phase = i % 150
            if phase < 50:
                pct = rng.normal(0.005, 0.01)   # calm uptrend ~0.5%/step
            elif phase < 100:
                pct = rng.normal(0.0, 0.04)     # high volatility ~4%
            else:
                pct = rng.normal(-0.003, 0.015)  # mild downtrend
            prices.append(prices[-1] * (1 + pct))
        return prices

    def test_constants(self):
        model = HMMRegimeModel()
        assert model.N_STATES == 5
        assert model.ROLLING_WINDOW == 20
        assert model.MIN_OBSERVATIONS == 100

    def test_not_fitted_initially(self):
        model = HMMRegimeModel()
        assert model._is_fitted is False

    def test_fit_with_sufficient_data(self):
        model = HMMRegimeModel()
        prices = self._noisy_prices()
        assert model.fit(prices) is True
        assert model._is_fitted is True

    def test_fit_with_insufficient_data(self):
        model = HMMRegimeModel()
        prices = self._noisy_prices()[:50]  # truncate to too-few points
        assert model.fit(prices) is False
        assert model._is_fitted is False

    def test_predict_state_after_fit(self):
        model = HMMRegimeModel()
        prices = self._noisy_prices()
        model.fit(prices)
        state = model.predict_state(prices)
        assert state is not None
        assert 0 <= state < 5

    def test_predict_state_before_fit_returns_none(self):
        model = HMMRegimeModel()
        prices = self._noisy_prices()
        assert model.predict_state(prices) is None

    def test_predict_state_short_series_returns_none(self):
        model = HMMRegimeModel()
        model.fit(self._noisy_prices())
        assert model.predict_state([100.0, 101.0]) is None

    def test_predict_confidence_after_fit(self):
        model = HMMRegimeModel()
        prices = self._noisy_prices()
        model.fit(prices)
        state = model.predict_state(prices)
        confidence = model.predict_confidence(prices, state)
        assert confidence is not None
        assert 0.0 <= confidence <= 1.0

    def test_predict_confidence_before_fit_returns_none(self):
        model = HMMRegimeModel()
        assert model.predict_confidence(self._noisy_prices(), 0) is None

    def test_predict_confidence_invalid_state_returns_none(self):
        model = HMMRegimeModel()
        model.fit(self._noisy_prices())
        assert model.predict_confidence(self._noisy_prices(), -1) is None
        assert model.predict_confidence(self._noisy_prices(), 5) is None

    def test_build_observations_too_short(self):
        model = HMMRegimeModel()
        result = model._build_observations([100.0] * 10)
        assert result is None

    def test_build_observations_shape(self):
        model = HMMRegimeModel()
        prices = self._noisy_prices()[:50]
        obs = model._build_observations(prices)
        assert obs is not None
        assert obs.ndim == 2
        assert obs.shape[1] == 2  # log_return + volatility


# ---------------------------------------------------------------------------
# Regime mapper tests
# ---------------------------------------------------------------------------

class TestRegimeMapper:
    def _fitted_model(self):
        model = HMMRegimeModel()
        rng = np.random.RandomState(123)
        prices = [100.0]
        for _ in range(499):
            prices.append(max(1.0, prices[-1] + rng.normal(0, 2.0)))
        model.fit(prices)
        return model

    def test_map_returns_regime_enum(self):
        model = self._fitted_model()
        for state_idx in range(5):
            result = map_state_to_regime(model, state_idx)
            assert result is None or isinstance(result, Regime)

    def test_map_unfitted_returns_none(self):
        model = HMMRegimeModel()
        assert map_state_to_regime(model, 0) is None

    def test_map_none_state_returns_none(self):
        model = self._fitted_model()
        assert map_state_to_regime(model, None) is None

    def test_all_states_mapped(self):
        """All 5 HMM states should map to some regime."""
        model = self._fitted_model()
        regimes = [map_state_to_regime(model, i) for i in range(5)]
        assert all(r is not None for r in regimes)
        # All results should be valid Regime values
        for r in regimes:
            assert r in list(Regime)
