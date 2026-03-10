import redis.asyncio as redis
from typing import Optional

class RedisClient:
    _instance: Optional['RedisClient'] = None
    _pool: Optional[redis.ConnectionPool] = None

    def __init__(self, url: str):
        if not self._pool:
            self._pool = redis.ConnectionPool.from_url(url, max_connections=100)
        self._client = redis.Redis(connection_pool=self._pool)

    @classmethod
    def get_instance(cls, url: str) -> 'RedisClient':
        if not cls._instance:
            cls._instance = cls(url)
        return cls._instance

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
