"""Unit tests for the ingestion pipeline.

Covers:
- CandleAggregator: 1m → 5m/15m/1h derivation, rollover flush, multi-symbol,
  non-closed candle rejection, force_flush.
- libs.exchange.backfill.fill_gap: cold start, warm start (since cursor),
  REST-fetch failure handling.
"""

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from libs.core.models import NormalisedCandle
from libs.exchange.backfill import COLD_START_LIMIT, fill_gap
from services.ingestion.src.candle_aggregator import (
    CandleAggregator,
    _bucket_start_ms,
)


# ---------------------------------------------------------------------------
# _bucket_start_ms
# ---------------------------------------------------------------------------

class TestBucketStartMs:
    def test_floors_to_5m(self):
        ts_ms = 1704067630_000  # 2024-01-01 00:07:10 UTC
        assert _bucket_start_ms(ts_ms, 300) == 1704067500_000  # 00:05:00

    def test_floors_to_1h(self):
        ts_ms = 1704070800_000  # 2024-01-01 01:00:00 UTC (boundary)
        assert _bucket_start_ms(ts_ms, 3600) == 1704070800_000  # unchanged

    def test_on_boundary_unchanged(self):
        ts_ms = 1704067500_000  # 00:05:00
        assert _bucket_start_ms(ts_ms, 300) == 1704067500_000


# ---------------------------------------------------------------------------
# CandleAggregator
# ---------------------------------------------------------------------------

def _make_1m(
    bucket_minute: int,
    open_: str = "50000",
    high: str = "50000",
    low: str = "50000",
    close: str = "50000",
    volume: str = "1.0",
    symbol: str = "BTC/USDT",
) -> NormalisedCandle:
    # Minute N since 2024-01-01 00:00 UTC
    bucket_ms = 1704067200_000 + bucket_minute * 60 * 1000
    return NormalisedCandle(
        symbol=symbol,
        exchange="BINANCE",
        timeframe="1m",
        bucket_ms=bucket_ms,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
        closed=True,
    )


@pytest.mark.asyncio
async def test_1m_written_immediately():
    repo = AsyncMock()
    agg = CandleAggregator(repo)
    await agg.handle_candle(_make_1m(0))
    # First call should be the 1m write with timeframe="1m".
    args, _ = repo.write_candle.call_args_list[0]
    symbol, tf, ohlcv, bucket = args
    assert symbol == "BTC/USDT"
    assert tf == "1m"
    assert bucket == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_non_closed_candle_ignored():
    repo = AsyncMock()
    agg = CandleAggregator(repo)
    c_open = replace(_make_1m(0), closed=False)
    await agg.handle_candle(c_open)
    repo.write_candle.assert_not_awaited()


@pytest.mark.asyncio
async def test_5m_rollover_flushes_correct_aggregate():
    """Five 1m bars fold into one 5m bar. On the 6th (start of next 5m
    window) the aggregator must flush a 5m candle with correct OHLCV."""
    repo = AsyncMock()
    agg = CandleAggregator(repo)

    # 5 bars in the 00:00-00:05 window with known OHLCV.
    bars = [
        _make_1m(0, open_="100", high="110", low="95", close="108", volume="1"),
        _make_1m(1, open_="108", high="120", low="105", close="115", volume="2"),
        _make_1m(2, open_="115", high="125", low="90", close="100", volume="3"),  # new low
        _make_1m(3, open_="100", high="130", low="99", close="128", volume="4"),  # new high
        _make_1m(4, open_="128", high="130", low="120", close="122", volume="5"),
    ]
    for b in bars:
        await agg.handle_candle(b)

    # At this point: 5 × 1m writes, no higher-TF flush yet.
    written_tfs = [call.args[1] for call in repo.write_candle.call_args_list]
    assert written_tfs.count("1m") == 5
    assert "5m" not in written_tfs

    # 6th bar crosses into the 00:05-00:10 window — triggers 5m flush.
    await agg.handle_candle(_make_1m(5, open_="122", close="122"))

    flushes_5m = [c for c in repo.write_candle.call_args_list if c.args[1] == "5m"]
    assert len(flushes_5m) == 1
    symbol, tf, ohlcv, bucket = flushes_5m[0].args
    assert ohlcv["open"] == Decimal("100")    # first bar's open
    assert ohlcv["high"] == Decimal("130")    # bar 4's high
    assert ohlcv["low"] == Decimal("90")      # bar 3's low
    assert ohlcv["close"] == Decimal("122")   # bar 5's close (last folded)
    assert ohlcv["volume"] == Decimal("15")   # 1+2+3+4+5
    assert bucket == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_multi_symbol_isolation():
    repo = AsyncMock()
    agg = CandleAggregator(repo)
    await agg.handle_candle(_make_1m(0, symbol="BTC/USDT", volume="1"))
    await agg.handle_candle(_make_1m(0, symbol="ETH/USDT", volume="10"))
    # Both symbols have their own 5m bucket, not mixed.
    assert agg._current["BTC/USDT"]["5m"]["volume"] == Decimal("1")
    assert agg._current["ETH/USDT"]["5m"]["volume"] == Decimal("10")


@pytest.mark.asyncio
async def test_force_flush_emits_all_open_buckets():
    repo = AsyncMock()
    agg = CandleAggregator(repo)
    await agg.handle_candle(_make_1m(0))
    repo.write_candle.reset_mock()

    await agg.force_flush()
    written_tfs = sorted({call.args[1] for call in repo.write_candle.call_args_list})
    assert written_tfs == ["15m", "1h", "5m"]


@pytest.mark.asyncio
async def test_older_bucket_bar_does_not_corrupt_current():
    """If a stray older-bucket 1m bar arrives after we've advanced, it must
    not fold into the wrong higher-TF bucket."""
    repo = AsyncMock()
    agg = CandleAggregator(repo)

    await agg.handle_candle(_make_1m(5, open_="200", high="210", low="200", close="205", volume="1"))
    # Now a late bar from the *previous* 5m window shows up — must be ignored.
    await agg.handle_candle(_make_1m(2, open_="100", high="110", low="90", close="100", volume="99"))

    # The current 5m bucket still reflects bar at minute 5 only, not the late bar.
    b5 = agg._current["BTC/USDT"]["5m"]
    assert b5["volume"] == Decimal("1")
    assert b5["high"] == Decimal("210")


# ---------------------------------------------------------------------------
# backfill.fill_gap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fill_gap_cold_start_fetches_bounded_history():
    repo = AsyncMock()
    repo.get_candles = AsyncMock(return_value=[])
    repo.write_candle = AsyncMock()

    rest = MagicMock()
    # Return two fake bars.
    rest.fetch_ohlcv = MagicMock(return_value=[
        [1704067200_000, 100.0, 110.0, 95.0, 105.0, 1.5],
        [1704067260_000, 105.0, 115.0, 100.0, 110.0, 2.0],
    ])

    n = await fill_gap(repo, rest, "BTC/USDT", "1m")
    assert n == 2

    # Cold start → since=None, limit=COLD_START_LIMIT.
    call = rest.fetch_ohlcv.call_args
    assert call.kwargs["since"] is None
    assert call.kwargs["limit"] == COLD_START_LIMIT


@pytest.mark.asyncio
async def test_fill_gap_warm_start_uses_cursor():
    """With prior data, 'since' must be last_bucket + one interval (ms)."""
    repo = AsyncMock()
    repo.get_candles = AsyncMock(
        return_value=[{"time": datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)}]
    )
    repo.write_candle = AsyncMock()

    rest = MagicMock()
    rest.fetch_ohlcv = MagicMock(return_value=[])

    await fill_gap(repo, rest, "BTC/USDT", "1h")

    call = rest.fetch_ohlcv.call_args
    # 2024-01-01 00:00 UTC = 1704067200000; +1h interval = +3_600_000ms
    assert call.kwargs["since"] == 1704067200_000 + 3_600_000


@pytest.mark.asyncio
async def test_fill_gap_swallows_rest_errors():
    """A REST fetch failure must not block startup — return 0, don't raise."""
    repo = AsyncMock()
    repo.get_candles = AsyncMock(return_value=[])
    rest = MagicMock()
    rest.fetch_ohlcv = MagicMock(side_effect=RuntimeError("network down"))

    n = await fill_gap(repo, rest, "BTC/USDT", "1m")
    assert n == 0
    repo.write_candle.assert_not_awaited()


@pytest.mark.asyncio
async def test_fill_gap_writes_bars_as_utc_datetime():
    repo = AsyncMock()
    repo.get_candles = AsyncMock(return_value=[])
    repo.write_candle = AsyncMock()

    rest = MagicMock()
    rest.fetch_ohlcv = MagicMock(return_value=[
        [1704067200_000, 100.0, 110.0, 95.0, 105.0, 1.5],
    ])

    await fill_gap(repo, rest, "BTC/USDT", "1m")
    args = repo.write_candle.call_args.args
    symbol, tf, ohlcv, bucket = args
    assert bucket == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert ohlcv["volume"] == Decimal("1.5")
