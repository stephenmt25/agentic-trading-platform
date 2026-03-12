import numpy as np
from typing import Optional
from libs.core.enums import Regime
from .hmm_model import HMMRegimeModel


# Regime mapping based on emission parameters:
# States are ordered by increasing volatility from the HMM means.
# The mapper sorts states by their mean volatility (feature index 1)
# and maps them to regimes.

REGIME_ORDER = [
    Regime.RANGE_BOUND,      # Lowest volatility
    Regime.TRENDING_UP,      # Low-moderate vol, positive returns
    Regime.TRENDING_DOWN,    # Low-moderate vol, negative returns
    Regime.HIGH_VOLATILITY,  # High volatility
    Regime.CRISIS,           # Highest volatility
]


def map_state_to_regime(model: HMMRegimeModel, state_index: int) -> Optional[Regime]:
    """Map HMM hidden state index to a Regime enum based on emission parameters."""
    if not model._is_fitted or state_index is None:
        return None

    try:
        # Sort states by mean volatility (2nd feature) ascending
        means = model._model.means_  # shape: (n_states, 2)
        vol_means = means[:, 1]
        sorted_indices = np.argsort(vol_means)

        # Find position of this state in the volatility-sorted order
        position = int(np.where(sorted_indices == state_index)[0][0])

        # Adjust trending direction based on mean return sign
        regime = REGIME_ORDER[position]
        mean_return = means[state_index, 0]

        if regime == Regime.TRENDING_UP and mean_return < 0:
            regime = Regime.TRENDING_DOWN
        elif regime == Regime.TRENDING_DOWN and mean_return > 0:
            regime = Regime.TRENDING_UP

        return regime
    except Exception:
        return None
