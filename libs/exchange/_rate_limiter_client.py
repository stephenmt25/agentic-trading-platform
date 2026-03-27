"""Exchange API rate limiter using Redis sliding window.

Each exchange has a configured request quota (e.g., Binance: 1200/min,
Coinbase: 300/min). This client enforces those limits using a Redis
sorted set per exchange+profile pair.

Previously a stub that always returned allowed=True (defect D-11).
"""

import time
from dataclasses import dataclass
from typing import Optional

import redis.asyncio as redis

from libs.core.types import ExchangeName, ProfileId


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_ms: Optional[int] = None


# Exchange quotas — requests per window
_EXCHANGE_QUOTAS = {
    "BINANCE": {"limit": 1200, "window_sec": 60},
    "COINBASE": {"limit": 300, "window_sec": 60},
}
_DEFAULT_QUOTA = {"limit": 600, "window_sec": 60}


class RateLimiterClient:
    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def check_and_reserve(self, exchange: ExchangeName, profile_id: ProfileId) -> RateLimitResult:
        """Check rate limit and reserve a slot if allowed.

        Uses a Redis sorted set sliding window:
        - Key: rate_limit:{exchange}:{profile_id}
        - Members: timestamp_ms with score = timestamp_ms
        - Window: remove entries older than window_sec, count remaining
        """
        quota = _EXCHANGE_QUOTAS.get(str(exchange).upper(), _DEFAULT_QUOTA)
        limit = quota["limit"]
        window_sec = quota["window_sec"]

        key = f"rate_limit:{exchange}:{profile_id}"
        now_ms = int(time.time() * 1000)
        window_ms = window_sec * 1000
        min_time = now_ms - window_ms

        # Atomic pipeline: clean expired, count, add new, set TTL
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, min_time)
        pipe.zcard(key)
        pipe.zadd(key, {str(now_ms): now_ms})
        pipe.expire(key, window_sec + 1)
        results = await pipe.execute()

        current_count = results[1]  # count BEFORE our addition

        if current_count >= limit:
            # Over limit — rollback the optimistic insertion
            await self._redis.zrem(key, str(now_ms))

            # Calculate retry-after from oldest entry
            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            retry_after_ms = 1000
            if oldest:
                oldest_ts = int(oldest[0][1])
                retry_after_ms = max(0, window_ms - (now_ms - oldest_ts))

            return RateLimitResult(allowed=False, retry_after_ms=retry_after_ms)

        return RateLimitResult(allowed=True)
