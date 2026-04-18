"""Unit tests for the ingestion pipeline.

Covers:
- CandleAggregator: 1m persistence, higher-TF rollover triggers REST fetch,
  non-closed / non-1m candles short-circuit, exceptions don't kill the stream.
- libs.exchange.backfill.fill_gap: cold start, warm start (since cursor),
  REST-fetch failure handling.
"""

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.core.models import NormalisedCandle
from libs.exchange.backfill import COLD_START_LIMIT, fill_gap
from services.ingestion.src.candle_aggregator import CandleAggregator


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
    timeframe: str = "1m",
    closed: bool = True,
) -> NormalisedCandle:
    bucket_ms = 1704067200_000 + bucket_minute * 60 * 1000
    return NormalisedCandle(
        symbol=symbol,
        exchange="BINANCE",
        timeframe=timeframe,
        bucket_ms=bucket_ms,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
        closed=closed,
    )


@pytest.mark.asyncio
async def test_closed_1m_is_written():
    repo = AsyncMock()
    agg = CandleAggregator(repo, rest=MagicMock())
    await agg.handle_candle(_make_1m(0))
    args = repo.write_candle.call_args_list[0].args
    symbol, tf, ohlcv, bucket = args
    assert symbol == "BTC/USDT"
    assert tf == "1m"
    assert bucket == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_non_closed_candle_ignored():
    repo = AsyncMock()
    agg = CandleAggregator(repo, rest=MagicMock())
    await agg.handle_candle(replace(_make_1m(0), closed=False))
    repo.write_candle.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_1m_closed_candle_persists_as_is():
    """If a source ever emits a higher-TF bar with closed=True, write it directly."""
    repo = AsyncMock()
    agg = CandleAggregator(repo, rest=MagicMock())
    c = _make_1m(0, timeframe="5m")
    await agg.handle_candle(c)
    # Only 1 call, the direct write — no rollover fetches.
    assert repo.write_candle.await_count == 1
    tf = repo.write_candle.call_args.args[1]
    assert tf == "5m"


@pytest.mark.asyncio
async def test_5m_boundary_1m_triggers_fill_gap():
    """A 1m bar at :04 (the last minute of a 5m window) rolls the 5m bucket
    when the next minute starts a new 5m bucket."""
    repo = AsyncMock()
    rest = MagicMock()
    agg = CandleAggregator(repo, rest=rest)

    # Bar at minute 4 -> next minute is 5, crosses 5m boundary.
    # Does NOT cross 15m (15 boundary) or 1h (60 boundary).
    with patch(
        "services.ingestion.src.candle_aggregator.fill_gap",
        new=AsyncMock(return_value=1),
    ) as mock_fill:
        await agg.handle_candle(_make_1m(4))

    # fill_gap called exactly once for 5m.
    assert mock_fill.await_count == 1
    (_repo, _rest, symbol, tf), _kw = mock_fill.call_args
    assert symbol == "BTC/USDT"
    assert tf == "5m"


@pytest.mark.asyncio
async def test_hour_boundary_triggers_all_higher_tf_fetches():
    """A 1m bar at :59 rolls 5m, 15m, AND 1h simultaneously."""
    repo = AsyncMock()
    agg = CandleAggregator(repo, rest=MagicMock())

    with patch(
        "services.ingestion.src.candle_aggregator.fill_gap",
        new=AsyncMock(return_value=1),
    ) as mock_fill:
        await agg.handle_candle(_make_1m(59))

    fetched_tfs = sorted({call.args[3] for call in mock_fill.call_args_list})
    assert fetched_tfs == ["15m", "1h", "5m"]


@pytest.mark.asyncio
async def test_mid_bucket_1m_does_not_trigger_higher_tf_fetch():
    """A 1m bar in the middle of a 5m window (e.g. minute 2) must not roll
    any higher-TF bucket."""
    repo = AsyncMock()
    agg = CandleAggregator(repo, rest=MagicMock())

    with patch(
        "services.ingestion.src.candle_aggregator.fill_gap",
        new=AsyncMock(return_value=0),
    ) as mock_fill:
        await agg.handle_candle(_make_1m(2))

    mock_fill.assert_not_awaited()


@pytest.mark.asyncio
async def test_fill_gap_failure_does_not_propagate():
    """If fill_gap raises, the handler must log and continue — the live
    1m bar has already been written and a single failed rollover shouldn't
    kill the WS stream."""
    repo = AsyncMock()
    agg = CandleAggregator(repo, rest=MagicMock())

    with patch(
        "services.ingestion.src.candle_aggregator.fill_gap",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        # Must not raise.
        await agg.handle_candle(_make_1m(4))

    # The 1m bar was still persisted.
    assert repo.write_candle.await_count == 1


# ---------------------------------------------------------------------------
# backfill.fill_gap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fill_gap_cold_start_fetches_bounded_history():
    repo = AsyncMock()
    repo.get_candles = AsyncMock(return_value=[])
    repo.write_candle = AsyncMock()

    rest = MagicMock()
    rest.fetch_ohlcv = MagicMock(return_value=[
        [1704067200_000, 100.0, 110.0, 95.0, 105.0, 1.5],
        [1704067260_000, 105.0, 115.0, 100.0, 110.0, 2.0],
    ])

    n = await fill_gap(repo, rest, "BTC/USDT", "1m")
    assert n == 2

    call = rest.fetch_ohlcv.call_args
    assert call.kwargs["since"] is None
    assert call.kwargs["limit"] == COLD_START_LIMIT


@pytest.mark.asyncio
async def test_fill_gap_warm_start_uses_cursor():
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
