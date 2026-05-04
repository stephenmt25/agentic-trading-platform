"""Offline trainer for the regime HMM (Track A.3).

Fits a 5-state Gaussian HMM on historical 1h OHLCV closes for one symbol and
writes the result to ``models/regime_hmm_<SYMBOL>.pkl``. The running
``services/regime_hmm`` process loads this checkpoint on startup and skips
in-process re-fitting unless the checkpoint is missing or stale (>30 days).

Usage:
    poetry run python scripts/train_hmm.py --symbol BTC/USDT
    poetry run python scripts/train_hmm.py --all
    poetry run python scripts/train_hmm.py --symbol ETH/USDT --timeframe 1h --limit 1000

Caveat (per AUTONOMOUS-EXECUTION-BRIEF.md): only ~30 days of 1h candles are
available per symbol, so 5-state assignment is noisy. The script reports the
training window so the limitation is visible in the checkpoint metadata.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Make the repo root importable when invoked via ``python scripts/train_hmm.py``.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.config import settings  # noqa: E402
from libs.observability import get_logger  # noqa: E402
from libs.storage._timescale_client import TimescaleClient  # noqa: E402
from libs.storage.repositories.market_data_repo import MarketDataRepository  # noqa: E402
from services.regime_hmm.src.checkpoint import (  # noqa: E402
    CHECKPOINT_VERSION,
    HMMCheckpoint,
    save_checkpoint,
)
from services.regime_hmm.src.hmm_model import HMMRegimeModel  # noqa: E402
from services.regime_hmm.src.regime_mapper import map_state_to_regime  # noqa: E402

logger = get_logger("scripts.train_hmm")

DEFAULT_TIMEFRAME = "1h"
DEFAULT_LIMIT = 1000


async def _train_one(
    symbol: str,
    timeframe: str,
    limit: int,
    models_dir: Path,
) -> Optional[Path]:
    timescale = TimescaleClient(settings.DATABASE_URL)
    await timescale.init_pool()
    try:
        repo = MarketDataRepository(timescale)
        candles = await repo.get_candles(symbol, timeframe, limit=limit)
        if not candles:
            logger.error("No candles found", symbol=symbol, timeframe=timeframe)
            return None
        if len(candles) < HMMRegimeModel.MIN_OBSERVATIONS:
            logger.error(
                "Not enough candles to fit HMM",
                symbol=symbol,
                have=len(candles),
                need=HMMRegimeModel.MIN_OBSERVATIONS,
            )
            return None

        prices: List[float] = [float(c["close"]) for c in candles]  # float-ok: hmmlearn requires float
        window_start = candles[0]["time"]
        window_end = candles[-1]["time"]

        logger.info(
            "Fitting HMM",
            symbol=symbol,
            timeframe=timeframe,
            n_candles=len(candles),
            window_start=str(window_start),
            window_end=str(window_end),
        )

        model = HMMRegimeModel()
        ok = model.fit(prices)
        if not ok:
            logger.error("HMM fit returned False", symbol=symbol)
            return None

        # Sanity-check the state→regime map covers all states.
        coverage = {map_state_to_regime(model, i) for i in range(HMMRegimeModel.N_STATES)}
        coverage.discard(None)
        logger.info(
            "Trained HMM regime coverage",
            symbol=symbol,
            n_states=HMMRegimeModel.N_STATES,
            distinct_regimes=len(coverage),
            regimes=sorted(r.value for r in coverage),
        )

        checkpoint = HMMCheckpoint(
            version=CHECKPOINT_VERSION,
            symbol=symbol,
            timeframe=timeframe,
            trained_at=datetime.now(timezone.utc),
            training_window_start=window_start if hasattr(window_start, "tzinfo") else None,
            training_window_end=window_end if hasattr(window_end, "tzinfo") else None,
            n_train=len(prices),
            model=model,
        )
        return save_checkpoint(checkpoint, models_dir=models_dir)
    finally:
        await timescale.close()


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train per-symbol regime HMM checkpoints.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbol", help="One symbol (e.g. BTC/USDT)")
    group.add_argument("--all", action="store_true", help="Train all settings.TRADING_SYMBOLS")
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--models-dir", default="models", help="Output directory")
    return parser.parse_args(argv)


async def _main(args: argparse.Namespace) -> int:
    models_dir = Path(args.models_dir)
    symbols = settings.TRADING_SYMBOLS if args.all else [args.symbol]
    failures = 0
    for sym in symbols:
        path = await _train_one(sym, args.timeframe, args.limit, models_dir)
        if path is None:
            failures += 1
            logger.error("Training failed", symbol=sym)
        else:
            logger.info("Training succeeded", symbol=sym, path=str(path))
    return 1 if failures else 0


def main() -> int:
    return asyncio.run(_main(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
