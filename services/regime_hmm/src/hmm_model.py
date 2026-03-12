import numpy as np
from typing import Optional, List
from hmmlearn.hmm import GaussianHMM

from libs.observability import get_logger

logger = get_logger("regime-hmm.model")


class HMMRegimeModel:
    """Hidden Markov Model for market regime classification.

    Trained on 2-feature observations: [log_return, rolling_volatility].
    Uses 5 hidden states mapped to Regime enum values.
    """

    N_STATES = 5
    ROLLING_WINDOW = 20
    MIN_OBSERVATIONS = 100

    def __init__(self):
        self._model = GaussianHMM(
            n_components=self.N_STATES,
            covariance_type="full",
            n_iter=100,
            random_state=42,
        )
        self._is_fitted = False

    def fit(self, prices: List[float]) -> bool:
        """Fit the HMM on historical price data. Returns True if successful."""
        if len(prices) < self.MIN_OBSERVATIONS:
            logger.warning("Insufficient data for HMM fit", n_prices=len(prices))
            return False

        observations = self._build_observations(prices)
        if observations is None or len(observations) < self.MIN_OBSERVATIONS:
            return False

        try:
            self._model.fit(observations)
            self._is_fitted = True
            logger.info("HMM fitted successfully", n_obs=len(observations))
            return True
        except Exception as e:
            logger.error("HMM fit failed", error=str(e))
            return False

    def predict_state(self, prices: List[float]) -> Optional[int]:
        """Predict the current hidden state given recent prices. Returns state index 0-4."""
        if not self._is_fitted:
            return None

        observations = self._build_observations(prices)
        if observations is None or len(observations) < 2:
            return None

        try:
            states = self._model.predict(observations)
            return int(states[-1])
        except Exception as e:
            logger.error("HMM predict failed", error=str(e))
            return None

    def _build_observations(self, prices: List[float]) -> Optional[np.ndarray]:
        """Build 2-feature observation matrix: [log_return, rolling_volatility]."""
        if len(prices) < self.ROLLING_WINDOW + 2:
            return None

        arr = np.array(prices, dtype=np.float64)
        log_returns = np.diff(np.log(arr))

        # Rolling volatility (std of log returns over window)
        vol = np.array([
            np.std(log_returns[max(0, i - self.ROLLING_WINDOW + 1):i + 1])
            for i in range(len(log_returns))
        ])

        # Trim to align
        start = self.ROLLING_WINDOW - 1
        observations = np.column_stack([
            log_returns[start:],
            vol[start:],
        ])

        return observations
