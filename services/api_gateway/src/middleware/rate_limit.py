import time

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRoute
from redis.asyncio import Redis

from libs.config import settings
from libs.observability import get_logger
from libs.storage._redis_client import RedisClient

logger = get_logger("api-gateway.rate-limit")


def user_rate_limit(scope: str, limit: int, window_s: int):
    """Route-level post-auth per-user rate bucket (registry row 64c).

    `RateLimiterMiddleware` below runs BEFORE the router-level auth dependency,
    so `request.state.user_id` is never set when it executes and its bucket
    keys on client IP only — a shared bucket behind any proxy. This factory
    returns a FastAPI dependency that runs AFTER auth (router deps populate
    `request.state.user_id` first), giving destructive routes a true
    per-user sliding window.

    Fail-OPEN on Redis errors: an unreachable limiter must never lock an
    operator out of POST /commands/kill-switch — the exact endpoint needed
    during a Redis outage (mirrors the middleware's fail-open contract).
    """

    async def _enforce(request: Request) -> None:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            # Router-level auth should have rejected already; defense in depth.
            raise HTTPException(status_code=401, detail="Authentication required")

        redis = RedisClient.get_instance(settings.REDIS_URL).get_connection()
        key = f"rate_limit:user:{scope}:{user_id}"
        now_ms = int(time.time() * 1000)
        window_ms = window_s * 1000
        min_time = now_ms - window_ms

        try:
            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, min_time)
            pipe.zcard(key)
            results = await pipe.execute()
            current_count = results[1]
        except Exception as e:
            logger.warning(
                "Per-user rate limiter Redis unreachable — failing open",
                scope=scope,
                error=str(e),
            )
            return

        if current_count >= limit:
            retry_after_sec = 1
            try:
                oldest = await redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_ts = int(oldest[0][1])
                    retry_after_sec = max(
                        1, int((window_ms - (now_ms - oldest_ts)) / 1000)
                    )
            except Exception:
                pass
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after_sec)},
            )

        try:
            pipe = redis.pipeline()
            pipe.zadd(key, {str(now_ms): now_ms})
            pipe.expire(key, window_s)
            await pipe.execute()
        except Exception:
            pass  # Best-effort — request was already permitted above

    return _enforce


class RateLimiterMiddleware:
    def __init__(
        self,
        # The wired-in object is RedisClient.get_connection()'s underlying
        # redis.asyncio.Redis (see main.py create_app), not the wrapper.
        redis_client: Redis,
        limit: int = 60,
        window: int = 60,
        auth_limit: int = 10,
    ):
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

        # request.client is None only for synthetic ASGI scopes (e.g. bare test
        # clients); a None-guard here would silently change the bucket key, so
        # keep runtime behavior and silence the optional-access warning only.
        identifier = getattr(request.state, "user_id", request.client.host)  # type: ignore[union-attr]

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
            logger.warning(
                "Rate limiter Redis unreachable — failing open", error=str(e)
            )
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
                headers={"Retry-After": str(retry_after_sec)},
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
