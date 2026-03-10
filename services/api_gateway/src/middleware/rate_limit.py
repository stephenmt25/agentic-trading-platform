from fastapi import Request, HTTPException, Response
from libs.storage._redis_client import RedisClient
import time
from typing import Optional

class RateLimiterMiddleware:
    def __init__(self, redis_client: RedisClient, limit: int = 60, window: int = 60, auth_limit: int = 10):
        self._redis = redis_client
        self._limit = limit
        self._window = window
        self._auth_limit = auth_limit

    async def __call__(self, request: Request, call_next):
        # Skip internal health checks
        if request.url.path in ["/health", "/ready"]:
            return await call_next(request)

        # Identify User (IP if unauthenticated, sub if auth'ed)
        # Assuming middleware runs after auth sets request.state.user_id if present
        identifier = getattr(request.state, "user_id", request.client.host)
        
        is_auth_route = request.url.path.startswith("/auth/")
        current_limit = self._auth_limit if is_auth_route else self._limit
        
        key = f"rate_limit:api:{identifier}:{request.url.path}"
        now_ms = int(time.time() * 1000)
        window_ms = self._window * 1000
        min_time = now_ms - window_ms

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, min_time)
        pipe.zcard(key)
        pipe.zadd(key, {str(now_ms): now_ms})
        pipe.expire(key, self._window)
        results = await pipe.execute()

        current_count = results[1]

        if current_count >= current_limit:
            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            retry_after_sec = 1
            if oldest:
                oldest_ts = int(oldest[0][1])
                retry_after_sec = max(1, int((window_ms - (now_ms - oldest_ts)) / 1000))

            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={"Retry-After": str(retry_after_sec)}
            )

        response = await call_next(request)
        return response
