from __future__ import annotations

import os
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from libs.observability import get_logger
from .hmm_model import HMMRegimeModel

logger = get_logger("regime-hmm.checkpoint")

DEFAULT_MODELS_DIR = Path("models")
CHECKPOINT_VERSION = 1
DEFAULT_STALENESS = timedelta(days=30)


@dataclass
class HMMCheckpoint:
    version: int
    symbol: str
    timeframe: str
    trained_at: datetime
    training_window_start: Optional[datetime]
    training_window_end: Optional[datetime]
    n_train: int
    model: HMMRegimeModel

    def is_stale(self, now: Optional[datetime] = None, max_age: timedelta = DEFAULT_STALENESS) -> bool:
        ref = now or datetime.now(timezone.utc)
        trained = self.trained_at if self.trained_at.tzinfo else self.trained_at.replace(tzinfo=timezone.utc)
        return (ref - trained) > max_age


def _safe_filename(symbol: str) -> str:
    return symbol.replace("/", "_").replace(":", "_")


def checkpoint_path(symbol: str, models_dir: Path = DEFAULT_MODELS_DIR) -> Path:
    return models_dir / f"regime_hmm_{_safe_filename(symbol)}.pkl"


def save_checkpoint(checkpoint: HMMCheckpoint, models_dir: Path = DEFAULT_MODELS_DIR) -> Path:
    models_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_path(checkpoint.symbol, models_dir)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(checkpoint, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)
    logger.info(
        "HMM checkpoint saved",
        symbol=checkpoint.symbol,
        path=str(path),
        n_train=checkpoint.n_train,
        trained_at=checkpoint.trained_at.isoformat(),
    )
    return path


def load_checkpoint(symbol: str, models_dir: Path = DEFAULT_MODELS_DIR) -> Optional[HMMCheckpoint]:
    path = checkpoint_path(symbol, models_dir)
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            obj = pickle.load(f)
    except Exception as e:
        logger.warning("Failed to load HMM checkpoint", symbol=symbol, path=str(path), error=str(e))
        return None
    if not isinstance(obj, HMMCheckpoint) or obj.version != CHECKPOINT_VERSION:
        logger.warning("Checkpoint version mismatch", symbol=symbol, path=str(path))
        return None
    return obj
