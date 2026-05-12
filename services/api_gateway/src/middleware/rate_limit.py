from fastapi import Request, Response
from fastapi.routing import APIRoute
from libs.storage._redis_client import RedisClient
from libs.observability import get_logger
import time

logger = get_logger("api-gateway.rate-limit")


class RateLimiterMiddleware:
    def __init__(self, redis_client: RedisClient, limit: int = 60, window: int = 60, auth_limit: int = 10):
        self._redis = redis_client
        self._limit = limit
        self._window = window
        self._auth_limit = auth_limit

    def _get_route_pattern(self, request: Request) -> str:
        """Use the matched route pattern instead of the actual path to prevent key explosion."""
        for route in request.app.routes:
            if isinstance(route, APIRoute):
                match, _ = route.matches(request.scope)
                if match.value >= 1:  # PARTIAL or FULL match
                    return route.path
        return request.url.path

    async def __call__(self, request: Request, call_next):
        # Skip internal health checks and auth callbacks (called server-side by NextAuth)
        if request.url.path in ["/health", "/ready", "/auth/callback", "/auth/refresh"]:
            return await call_next(request)

        identifier = getattr(request.state, "user_id", request.client.host)

        is_auth_route = request.url.path.startswith("/auth/")
        current_limit = self._auth_limit if is_auth_route else self._limit

        route_pattern = self._get_route_pattern(request)
        key = f"rate_limit:api:{identifier}:{route_pattern}"
        now_ms = int(time.time() * 1000)
        window_ms = self._window * 1000
        min_time = now_ms - window_ms

        # Fail-OPEN on Redis errors. Without this, a Redis outage 500s every
        # endpoint behind this middleware — including /commands/kill-switch,
        # which is exactly the endpoint operators need during a Redis outage.
        try:
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, min_time)
            pipe.zcard(key)
            results = await pipe.execute()
            current_count = results[1]
        except Exception as e:
            logger.warning("Rate limiter Redis unreachable — failing open", error=str(e))
            return await call_next(request)

        if current_count >= current_limit:
            try:
                oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            except Exception:
                oldest = None
            retry_after_sec = 1
            if oldest:
                oldest_ts = int(oldest[0][1])
                retry_after_sec = max(1, int((window_ms - (now_ms - oldest_ts)) / 1000))

            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={"Retry-After": str(retry_after_sec)}
            )

        # Only record the request if not rate-limited
        try:
            pipe = self._redis.pipeline()
            pipe.zadd(key, {str(now_ms): now_ms})
            pipe.expire(key, self._window)
            await pipe.execute()
        except Exception:
            pass  # Best-effort — request was already permitted above

        response = await call_next(request)
        return response
