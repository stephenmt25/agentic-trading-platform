"""Tests for Ingestion service: data routing and candle aggregation."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.core.models import NormalisedTick
from services.ingestion.src.data_router import DataRouter, _bucket_for_timeframe


# ---------------------------------------------------------------------------
# _bucket_for_timeframe tests
# ---------------------------------------------------------------------------

class TestBucketForTimeframe:
    def test_1m_bucket(self):
        # 2026-01-01 12:03:45 UTC → should floor to 12:03:00
        ts = datetime(2026, 1, 1, 12, 3, 45, tzinfo=timezone.utc).timestamp()
        bucket = _bucket_for_timeframe(ts, 60)
        assert bucket.minute == 3
        assert bucket.second == 0

    def test_5m_bucket(self):
        # 12:07:30 → should floor to 12:05:00
        ts = datetime(2026, 1, 1, 12, 7, 30, tzinfo=timezone.utc).timestamp()
        bucket = _bucket_for_timeframe(ts, 300)
        assert bucket.minute == 5

    def test_1h_bucket(self):
        # 14:45:00 → should floor to 14:00:00
        ts = datetime(2026, 1, 1, 14, 45, 0, tzinfo=timezone.utc).timestamp()
        bucket = _bucket_for_timeframe(ts, 3600)
        assert bucket.hour == 14
        assert bucket.minute == 0

    def test_exact_boundary(self):
        # Exactly on a 5m boundary → stays the same
        ts = datetime(2026, 1, 1, 12, 10, 0, tzinfo=timezone.utc).timestamp()
        bucket = _bucket_for_timeframe(ts, 300)
        assert bucket.minute == 10


# ---------------------------------------------------------------------------
# DataRouter tests
# ---------------------------------------------------------------------------

class TestDataRouter:
    def _make_tick(self, symbol="BTC/USDT", price=Decimal("50000"), volume=Decimal("1.0"),
                   timestamp_us=1704067200_000000):
        return NormalisedTick(
            symbol=symbol,
            exchange="BINANCE",
            timestamp=timestamp_us,
            price=price,
            volume=volume,
        )

    def test_aggregate_first_tick_creates_candle(self):
        repo = AsyncMock()
        router = DataRouter(repo)
        tick = self._make_tick()
        router.aggregate_tick(tick)

        assert "BTC/USDT" in router._current_candles
        for tf in ["1m", "5m", "15m", "1h"]:
            assert tf in router._current_candles["BTC/USDT"]
            candle = router._current_candles["BTC/USDT"][tf]
            assert candle["open"] == tick.price
            assert candle["close"] == tick.price
            assert candle["high"] == tick.price
            assert candle["low"] == tick.price

    def test_aggregate_updates_hlcv(self):
        repo = AsyncMock()
        router = DataRouter(repo)

        # First tick
        router.aggregate_tick(self._make_tick(price=Decimal("50000"), timestamp_us=1704067200_000000))
        # Second tick — same bucket, higher price
        router.aggregate_tick(self._make_tick(price=Decimal("51000"), timestamp_us=1704067200_000000 + 1_000000))
        # Third tick — same bucket, lower price
        router.aggregate_tick(self._make_tick(price=Decimal("49000"), timestamp_us=1704067200_000000 + 2_000000))

        candle = router._current_candles["BTC/USDT"]["1m"]
        assert candle["open"] == Decimal("50000")
        assert candle["high"] == Decimal("51000")
        assert candle["low"] == Decimal("49000")
        assert candle["close"] == Decimal("49000")
        assert candle["volume"] == Decimal("3.0")

    def test_different_symbols_tracked_independently(self):
        repo = AsyncMock()
        router = DataRouter(repo)

        router.aggregate_tick(self._make_tick(symbol="BTC/USDT", price=Decimal("50000")))
        router.aggregate_tick(self._make_tick(symbol="ETH/USDT", price=Decimal("3000")))

        assert "BTC/USDT" in router._current_candles
        assert "ETH/USDT" in router._current_candles

    @pytest.mark.asyncio
    async def test_force_flush_calls_repo(self):
        repo = AsyncMock()
        repo.write_candle = AsyncMock()
        router = DataRouter(repo)
        router.aggregate_tick(self._make_tick())

        await router.force_flush()
        assert repo.write_candle.call_count > 0
