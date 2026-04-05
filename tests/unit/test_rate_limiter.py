"""Tests for Rate Limiter service: sliding window algorithm and quota config."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.rate_limiter.src.limiter import RateLimiter
from services.rate_limiter.src.quota_config import EXCHANGE_QUOTAS


# ---------------------------------------------------------------------------
# QuotaConfig tests
# ---------------------------------------------------------------------------

class TestQuotaConfig:
    def test_binance_quota_exists(self):
        assert "BINANCE" in EXCHANGE_QUOTAS
        assert EXCHANGE_QUOTAS["BINANCE"].limit == 1200
        assert EXCHANGE_QUOTAS["BINANCE"].window_sec == 60

    def test_coinbase_quota_exists(self):
        assert "COINBASE" in EXCHANGE_QUOTAS
        assert EXCHANGE_QUOTAS["COINBASE"].limit == 300
        assert EXCHANGE_QUOTAS["COINBASE"].window_sec == 60


# ---------------------------------------------------------------------------
# RateLimiter tests
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def _make_limiter(self, mock_redis):
        return RateLimiter(mock_redis)

    @pytest.mark.asyncio
    async def test_allows_request_under_limit(self, mock_redis):
        pipe = AsyncMock()
        pipe.zremrangebyscore = MagicMock(return_value=pipe)
        pipe.zcard = MagicMock(return_value=pipe)
        pipe.zadd = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[0, 5, 1, True])  # 5 requests < 1200 limit
        mock_redis.pipeline = MagicMock(return_value=pipe)

        limiter = self._make_limiter(mock_redis)
        result = await limiter.check_and_reserve("BINANCE", "prof-1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_rejects_at_limit(self, mock_redis):
        pipe = AsyncMock()
        pipe.zremrangebyscore = MagicMock(return_value=pipe)
        pipe.zcard = MagicMock(return_value=pipe)
        pipe.zadd = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[0, 1200, 1, True])  # at limit
        mock_redis.pipeline = MagicMock(return_value=pipe)
        mock_redis.zrem = AsyncMock(return_value=1)
        mock_redis.zrange = AsyncMock(return_value=[(b"123", float(int(time.time() * 1000) - 30000))])

        limiter = self._make_limiter(mock_redis)
        result = await limiter.check_and_reserve("BINANCE", "prof-1")
        assert result.allowed is False
        assert result.retry_after_ms is not None
        assert result.retry_after_ms >= 0

    @pytest.mark.asyncio
    async def test_unknown_exchange_allowed(self, mock_redis):
        """Unknown exchange has no quota — should be allowed."""
        limiter = self._make_limiter(mock_redis)
        result = await limiter.check_and_reserve("KRAKEN", "prof-1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_case_insensitive_exchange_lookup(self, mock_redis):
        pipe = AsyncMock()
        pipe.zremrangebyscore = MagicMock(return_value=pipe)
        pipe.zcard = MagicMock(return_value=pipe)
        pipe.zadd = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[0, 0, 1, True])
        mock_redis.pipeline = MagicMock(return_value=pipe)

        limiter = self._make_limiter(mock_redis)
        result = await limiter.check_and_reserve("binance", "prof-1")
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_rollback_on_reject(self, mock_redis):
        """When rate-limited, the optimistically added entry should be rolled back."""
        pipe = AsyncMock()
        pipe.zremrangebyscore = MagicMock(return_value=pipe)
        pipe.zcard = MagicMock(return_value=pipe)
        pipe.zadd = MagicMock(return_value=pipe)
        pipe.expire = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[0, 300, 1, True])  # coinbase at limit
        mock_redis.pipeline = MagicMock(return_value=pipe)
        mock_redis.zrem = AsyncMock(return_value=1)
        mock_redis.zrange = AsyncMock(return_value=[])

        limiter = self._make_limiter(mock_redis)
        await limiter.check_and_reserve("COINBASE", "prof-1")
        mock_redis.zrem.assert_called_once()
