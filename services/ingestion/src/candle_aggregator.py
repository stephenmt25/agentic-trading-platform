"""Aggregate authoritative 1-minute candles into 5m / 15m / 1h bars.

Flow: the Binance (or Coinbase) adapter streams *finalized* 1m bars via
`NormalisedCandle(closed=True)`. This aggregator:

1. Writes the 1m bar to TimescaleDB immediately (source of truth).
2. Folds the 1m bar into the currently-open 5m / 15m / 1h buckets in memory.
3. When a higher-timeframe bucket rolls over, flushes the completed bar to DB.

Aggregation math is correct-by-construction because the inputs are Binance's
own klines: volumes sum, highs/lows are true extremes over the constituent 1m
bars, open = first 1m open, close = last 1m close.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from libs.core.models import NormalisedCandle
from libs.observability import get_logger

logger = get_logger("ingestion.candles")


# Higher timeframes we derive from 1m. Order matters: callers expect 5m < 15m < 1h.
DERIVED_TIMEFRAMES = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


def _bucket_start_ms(ts_ms: int, tf_seconds: int) -> int:
    """Floor an epoch-ms timestamp to the start of its timeframe bucket."""
    interval_ms = tf_seconds * 1000
    return (ts_ms // interval_ms) * interval_ms


def _ms_to_datetime(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


class CandleAggregator:
    """Receives finalized 1m candles, derives & persists all timeframes."""

    def __init__(self, repo):
        self._repo = repo
        # {symbol: {tf_label: {"bucket_ms", "open", "high", "low", "close", "volume"}}}
        self._current: Dict[str, Dict[str, Dict[str, Any]]] = {}

    async def handle_candle(self, candle: NormalisedCandle) -> None:
        """Entry point. Only finalized 1m bars are expected (closed=True)."""
        if not candle.closed:
            return
        if candle.timeframe != "1m":
            # If a source ever sends a higher-TF bar directly, just persist it.
            await self._write(candle.symbol, candle.timeframe, candle)
            return

        # 1. Persist the 1m bar immediately — it's the canonical record.
        await self._write(candle.symbol, "1m", candle)

        # 2. Fold into the derived-timeframe buckets.
        symbol_buckets = self._current.setdefault(candle.symbol, {})
        for tf_label, tf_seconds in DERIVED_TIMEFRAMES.items():
            bucket_ms = _bucket_start_ms(candle.bucket_ms, tf_seconds)
            current = symbol_buckets.get(tf_label)

            if current is None:
                symbol_buckets[tf_label] = _init_bucket(candle, bucket_ms)
                continue

            if bucket_ms > current["bucket_ms"]:
                # Previous higher-TF bucket is complete — flush and start fresh.
                await self._flush(candle.symbol, tf_label, current)
                symbol_buckets[tf_label] = _init_bucket(candle, bucket_ms)
            elif bucket_ms == current["bucket_ms"]:
                _fold_into(current, candle)
            # else: older bar (backfill race) — skip to avoid corrupting bucket.

    async def _write(self, symbol: str, timeframe: str, candle: NormalisedCandle) -> None:
        await self._repo.write_candle(
            symbol,
            timeframe,
            {
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            },
            _ms_to_datetime(candle.bucket_ms),
        )

    async def _flush(self, symbol: str, timeframe: str, bucket: Dict[str, Any]) -> None:
        try:
            await self._repo.write_candle(
                symbol,
                timeframe,
                {
                    "open": bucket["open"],
                    "high": bucket["high"],
                    "low": bucket["low"],
                    "close": bucket["close"],
                    "volume": bucket["volume"],
                },
                _ms_to_datetime(bucket["bucket_ms"]),
            )
        except Exception as e:  # noqa: BLE001 — never let a flush error kill the stream
            logger.error(
                "candle_flush_failed",
                symbol=symbol,
                timeframe=timeframe,
                bucket_ms=bucket["bucket_ms"],
                error=str(e),
            )

    async def force_flush(self) -> None:
        """Flush all currently-open higher-TF buckets. Call on shutdown only."""
        tasks = []
        for symbol, tf_map in self._current.items():
            for tf_label, bucket in tf_map.items():
                tasks.append(self._flush(symbol, tf_label, bucket))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def _init_bucket(candle: NormalisedCandle, bucket_ms: int) -> Dict[str, Any]:
    return {
        "bucket_ms": bucket_ms,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


def _fold_into(bucket: Dict[str, Any], candle: NormalisedCandle) -> None:
    # Open is preserved (first 1m bar of the higher-TF bucket).
    bucket["high"] = max(bucket["high"], candle.high)
    bucket["low"] = min(bucket["low"], candle.low)
    bucket["close"] = candle.close
    bucket["volume"] = bucket["volume"] + candle.volume
