import numpy as np
from typing import Optional
from libs.core.enums import Regime
from .hmm_model import HMMRegimeModel


def map_state_to_regime(model: HMMRegimeModel, state_index: int) -> Optional[Regime]:
    """Map HMM hidden state index to a Regime enum based on emission characteristics.

    Classification logic (uses mean return and mean volatility of each state):
    - Volatility in top 20% of range  -> CRISIS
    - Volatility in top 40% of range  -> HIGH_VOLATILITY
    - Remaining states with positive mean return -> TRENDING_UP
    - Remaining states with negative mean return -> TRENDING_DOWN
    - Otherwise (near-zero return, low vol)      -> RANGE_BOUND
    """
    if not model._is_fitted or state_index is None:
        return None

    try:
        means = model._model.means_  # shape: (n_states, n_features)
        mean_return = float(means[state_index, 0])
        mean_vol = float(means[state_index, 1])

        # Compute volatility range across all states for relative thresholds
        all_vols = means[:, 1]
        vol_min = float(np.min(all_vols))
        vol_max = float(np.max(all_vols))
        vol_range = vol_max - vol_min

        if vol_range < 1e-12:
            # All states have identical volatility; fall back to return-based
            if mean_return > 1e-6:
                return Regime.TRENDING_UP
            elif mean_return < -1e-6:
                return Regime.TRENDING_DOWN
            return Regime.RANGE_BOUND

        # Normalised position of this state's volatility within [0, 1]
        vol_percentile = (mean_vol - vol_min) / vol_range

        # High-volatility regimes (thresholds based on relative position)
        if vol_percentile >= 0.80:
            return Regime.CRISIS
        if vol_percentile >= 0.60:
            return Regime.HIGH_VOLATILITY

        # Low/moderate volatility: classify by return direction
        # Use a small dead-zone around zero to avoid noise
        return_threshold = 1e-5
        if mean_return > return_threshold:
            return Regime.TRENDING_UP
        elif mean_return < -return_threshold:
            return Regime.TRENDING_DOWN
        else:
            return Regime.RANGE_BOUND

    except Exception:
        return None
