"""Round-trip + staleness tests for ``services.regime_hmm.src.checkpoint``.

The checkpoint is what ``scripts/train_hmm.py`` writes and what the live
service loads on startup; preserving the file format and the staleness
semantics across refactors is what these tests pin down.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pytest

from services.regime_hmm.src.checkpoint import (
    CHECKPOINT_VERSION,
    DEFAULT_STALENESS,
    HMMCheckpoint,
    checkpoint_path,
    load_checkpoint,
    save_checkpoint,
)
from services.regime_hmm.src.hmm_model import HMMRegimeModel


def _fit_small_model() -> HMMRegimeModel:
    """Synthetic price series with rotating regimes — variety is needed for
    a 5-state full-covariance fit not to collapse into singular emissions."""
    rng = np.random.RandomState(5)
    prices = [100.0]
    for i in range(499):
        phase = i % 150
        if phase < 50:
            pct = rng.normal(0.005, 0.01)
        elif phase < 100:
            pct = rng.normal(0.0, 0.04)
        else:
            pct = rng.normal(-0.003, 0.015)
        prices.append(prices[-1] * (1 + pct))
    model = HMMRegimeModel()
    assert model.fit(prices) is True
    return model


@pytest.fixture()
def trained_model() -> HMMRegimeModel:
    return _fit_small_model()


def test_checkpoint_path_replaces_slash(tmp_path: Path):
    p = checkpoint_path("BTC/USDT", models_dir=tmp_path)
    assert p == tmp_path / "regime_hmm_BTC_USDT.pkl"


def test_save_load_roundtrip(tmp_path: Path, trained_model: HMMRegimeModel):
    cp = HMMCheckpoint(
        version=CHECKPOINT_VERSION,
        symbol="BTC/USDT",
        timeframe="1h",
        trained_at=datetime.now(timezone.utc),
        training_window_start=datetime.now(timezone.utc) - timedelta(days=30),
        training_window_end=datetime.now(timezone.utc),
        n_train=500,
        model=trained_model,
    )
    path = save_checkpoint(cp, models_dir=tmp_path)
    assert path.exists()

    loaded = load_checkpoint("BTC/USDT", models_dir=tmp_path)
    assert loaded is not None
    assert loaded.version == CHECKPOINT_VERSION
    assert loaded.symbol == "BTC/USDT"
    assert loaded.timeframe == "1h"
    assert loaded.n_train == 500
    assert loaded.model._is_fitted is True
    rng = np.random.RandomState(11)
    series = [100.0]
    for _ in range(199):
        series.append(series[-1] * (1 + rng.normal(0.0, 0.01)))
    state = loaded.model.predict_state(series)
    assert state is None or 0 <= state < HMMRegimeModel.N_STATES


def test_load_missing_returns_none(tmp_path: Path):
    assert load_checkpoint("DOES/NOT", models_dir=tmp_path) is None


def test_is_stale_logic(trained_model: HMMRegimeModel):
    fresh = HMMCheckpoint(
        version=CHECKPOINT_VERSION,
        symbol="X/Y",
        timeframe="1h",
        trained_at=datetime.now(timezone.utc) - timedelta(days=5),
        training_window_start=None,
        training_window_end=None,
        n_train=10,
        model=trained_model,
    )
    stale = HMMCheckpoint(
        version=CHECKPOINT_VERSION,
        symbol="X/Y",
        timeframe="1h",
        trained_at=datetime.now(timezone.utc) - DEFAULT_STALENESS - timedelta(days=1),
        training_window_start=None,
        training_window_end=None,
        n_train=10,
        model=trained_model,
    )
    assert fresh.is_stale() is False
    assert stale.is_stale() is True


def test_load_rejects_wrong_version(tmp_path: Path, trained_model: HMMRegimeModel):
    cp = HMMCheckpoint(
        version=CHECKPOINT_VERSION + 99,
        symbol="ETH/USDT",
        timeframe="1h",
        trained_at=datetime.now(timezone.utc),
        training_window_start=None,
        training_window_end=None,
        n_train=200,
        model=trained_model,
    )
    save_checkpoint(cp, models_dir=tmp_path)
    assert load_checkpoint("ETH/USDT", models_dir=tmp_path) is None
