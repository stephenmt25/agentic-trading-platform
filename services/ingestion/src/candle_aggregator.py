"""Persist authoritative OHLCV from `watch_ohlcv`-driven 1m candles.

Design: the 1m stream is the source of truth. Higher timeframes (5m/15m/1h)
are NOT aggregated in memory — that was a bug, because a service starting
mid-bucket would produce partial aggregates and overwrite correct backfilled
values on rollover. Instead, whenever a 1m bar's close coincides with a
higher-TF rollover, we REST-fetch that higher-TF bar from the exchange,
same idempotent path as startup backfill.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from libs.core.models import NormalisedCandle
from libs.exchange.backfill import fill_gap
from libs.observability import get_logger

logger = get_logger("ingestion.candles")


# Higher timeframes we keep fresh on every 1m close.
DERIVED_TIMEFRAMES = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


def _ms_to_datetime(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


class CandleAggregator:
    """Writes finalized 1m bars and triggers higher-TF REST fetches on rollover."""

    def __init__(self, repo, rest):
        self._repo = repo
        # Sync ccxt REST client (e.g. `ccxt.binance(...)`) — used to fetch
        # authoritative closed bars for 5m/15m/1h when a rollover is detected.
        self._rest = rest

    async def handle_candle(self, candle: NormalisedCandle) -> None:
        if not candle.closed:
            return

        # Sources can emit non-1m closed bars directly; persist them as-is.
        if candle.timeframe != "1m":
            await self._write(candle.symbol, candle.timeframe, candle)
            return

        # 1. Persist the 1m bar — canonical record.
        await self._write(candle.symbol, "1m", candle)

        # 2. For each higher TF, check if this 1m's close rolled the bucket.
        #    The "next 1m" start is bucket_ms + 60_000; if that crosses a
        #    higher-TF boundary, the current higher-TF bar just closed.
        next_1m_ms = candle.bucket_ms + 60_000
        for tf_label, tf_seconds in DERIVED_TIMEFRAMES.items():
            interval_ms = tf_seconds * 1000
            current_bucket = (candle.bucket_ms // interval_ms) * interval_ms
            next_bucket = (next_1m_ms // interval_ms) * interval_ms
            if next_bucket > current_bucket:
                # Higher-TF rolled — fetch the now-closed bar from REST.
                try:
                    await fill_gap(self._repo, self._rest, candle.symbol, tf_label)
                except Exception as e:  # noqa: BLE001 — never let this kill the stream
                    logger.warning(
                        "higher_tf_rollover_fetch_failed",
                        symbol=candle.symbol,
                        timeframe=tf_label,
                        error=str(e),
                    )

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

    async def force_flush(self) -> None:
        # No in-memory state to flush — higher-TFs are driven by REST on rollover.
        return None
