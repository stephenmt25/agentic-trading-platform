from typing import Any, Dict, Optional

import redis.asyncio as redis

# Default short-timeout settings. Used by everything by default so a Redis
# outage produces an exception within seconds instead of an infinite hang.
# Required by the KillSwitch fail-safe at services/hot_path/src/kill_switch.py
# which depends on Redis errors being raised so its except branch fires.
_DEFAULT_SOCKET_TIMEOUT_S = 5.0
_DEFAULT_SOCKET_CONNECT_TIMEOUT_S = 2.0
_DEFAULT_HEALTH_CHECK_INTERVAL_S = 15


class RedisClient:
    _instance: Optional["RedisClient"] = None
    _long_instance: Optional["RedisClient"] = None

    def __init__(self, url: str, *, long_blocking: bool = False):
        kwargs: Dict[str, Any] = {"max_connections": 100}
        if not long_blocking:
            kwargs.update(
                socket_timeout=_DEFAULT_SOCKET_TIMEOUT_S,
                socket_connect_timeout=_DEFAULT_SOCKET_CONNECT_TIMEOUT_S,
                health_check_interval=_DEFAULT_HEALTH_CHECK_INTERVAL_S,
            )
        self._pool = redis.ConnectionPool.from_url(url, **kwargs)
        self._client = redis.Redis(connection_pool=self._pool)

    @classmethod
    def get_instance(cls, url: str) -> "RedisClient":
        if cls._instance is None:
            cls._instance = cls(url)
        return cls._instance

    @classmethod
    def get_long_blocking_instance(cls, url: str) -> "RedisClient":
        # Separate pool with no socket_timeout — for BLPOP with human-scale
        # timeouts (HITL approval, 60 s) and xreadgroup with multi-second
        # block windows (backtest job worker, 5 s).
        if cls._long_instance is None:
            cls._long_instance = cls(url, long_blocking=True)
        return cls._long_instance

    def get_connection(self) -> redis.Redis:
        return self._client

    async def health_check(self) -> bool:
        try:
            return await self._client.ping()
        except Exception:
            return False

    async def close(self):
        if self._pool:
            await self._pool.disconnect()
