"""REST-based OHLCV gap-fill.

Used on service startup and after every successful WS reconnect: any bars
between `max(bucket)` in TimescaleDB and "now" are fetched from the exchange
REST API and upserted. `market_data_ohlcv.write_candle` uses ON CONFLICT DO
UPDATE, so re-running a range is safe.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Optional, Protocol

from libs.observability import get_logger

logger = get_logger("exchange.backfill")

# Seconds per timeframe — mirrors services.ingestion.src.candle_aggregator.
TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}

# Matches the existing constant in scripts/backfill_candles.py — used when the
# DB has no prior candles and we're bootstrapping from scratch.
COLD_START_LIMIT = 500


class _CCXTRestLike(Protocol):
    """Minimum interface we need from a sync ccxt client.

    Abstracted so tests can supply a fake without touching the network.
    """

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list: ...


class _RepoLike(Protocol):
    async def get_candles(self, symbol: str, timeframe: str, limit: int) -> list: ...
    async def write_candle(
        self, symbol: str, timeframe: str, ohlcv: dict, bucket: datetime
    ) -> None: ...


async def _latest_bucket_ms(
    repo: _RepoLike, symbol: str, timeframe: str
) -> Optional[int]:
    rows = await repo.get_candles(symbol, timeframe, limit=1)
    if not rows:
        return None
    # repo returns oldest-to-newest; with limit=1 there's a single row, the newest.
    ts = rows[-1]["time"]
    if isinstance(ts, datetime):
        return int(ts.timestamp() * 1000)
    return int(ts)


async def fill_gap(
    repo: _RepoLike,
    exchange: _CCXTRestLike,
    symbol: str,
    timeframe: str,
) -> int:
    """Fetch and upsert bars between `max(bucket)` and now.

    Returns the number of bars written. Safe to call repeatedly — upsert handles
    duplicates. Silently logs and returns 0 on fetch errors (don't block startup).
    """
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    last_ms = await _latest_bucket_ms(repo, symbol, timeframe)

    if last_ms is None:
        # Cold start: grab the last COLD_START_LIMIT bars.
        since = None
        limit = COLD_START_LIMIT
    else:
        # Start one bar *after* the latest we have, to avoid re-fetching
        # the most recent stored bar on every reconnect.
        since = last_ms + TIMEFRAME_SECONDS[timeframe] * 1000
        limit = None  # let the exchange default apply; we'll page if needed

    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
    except Exception as e:  # noqa: BLE001 — REST fetch is best-effort on startup
        logger.warning(
            "backfill_fetch_failed",
            symbol=symbol,
            timeframe=timeframe,
            error=str(e),
        )
        return 0

    interval_ms = TIMEFRAME_SECONDS[timeframe] * 1000
    now_ms = int(time.time() * 1000)
    written = 0
    for bar in ohlcv:
        ts_ms, o, h, l, c, v = bar
        ts_ms = int(ts_ms)
        # Skip any bar whose bucket hasn't finished yet — its OHLCV is in flux
        # and writing it would contaminate the hypertable with partial values
        # that only get overwritten on the NEXT rollover.
        if ts_ms + interval_ms > now_ms:
            continue
        bucket = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        await repo.write_candle(
            symbol,
            timeframe,
            {
                "open": Decimal(str(o)),
                "high": Decimal(str(h)),
                "low": Decimal(str(l)),
                "close": Decimal(str(c)),
                "volume": Decimal(str(v)),
            },
            bucket,
        )
        written += 1

    if written:
        logger.info(
            "backfill_complete",
            symbol=symbol,
            timeframe=timeframe,
            bars=written,
            from_ms=since,
        )
    return written


async def fill_gaps(
    repo: _RepoLike,
    exchange: _CCXTRestLike,
    symbols: Iterable[str],
    timeframes: Iterable[str] = ("1m", "5m", "15m", "1h"),
) -> int:
    """Convenience: fill every (symbol, timeframe) pair. Returns total bars."""
    total = 0
    for symbol in symbols:
        for tf in timeframes:
            total += await fill_gap(repo, exchange, symbol, tf)
    return total
