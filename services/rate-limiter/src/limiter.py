import time
import redis.asyncio as redis
from typing import Optional
from .quota_config import EXCHANGE_QUOTAS
from libs.exchange import RateLimitResult
from libs.core.types import ProfileId

class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def check_and_reserve(self, exchange: str, profile_id: ProfileId) -> RateLimitResult:
        quota = EXCHANGE_QUOTAS.get(exchange.upper())
        if not quota:
            return RateLimitResult(allowed=True)

        key = f"rate_limit:{exchange.lower()}:{profile_id}"
        now_ms = int(time.time() * 1000)
        window_ms = quota.window_sec * 1000
        min_time = now_ms - window_ms

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, min_time)
        pipe.zcard(key)
        pipe.zadd(key, {str(now_ms): now_ms})
        pipe.expire(key, quota.window_sec)
        results = await pipe.execute()

        current_count = results[1]

        if current_count >= quota.limit:
            # rollback the insertion
            await self._redis.zrem(key, str(now_ms))

            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            retry_after_ms = 1000
            if oldest:
                oldest_ts = int(oldest[0][1])
                retry_after_ms = window_ms - (now_ms - oldest_ts)

            return RateLimitResult(allowed=False, retry_after_ms=max(0, retry_after_ms))

        return RateLimitResult(allowed=True)
