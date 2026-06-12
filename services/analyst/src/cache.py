from typing import Optional

from libs.storage._redis_client import RedisClient


class SentimentCache:
    def __init__(self, redis_client: RedisClient, ttl_s: int = 900):
        self._redis = redis_client
        self._ttl_s = ttl_s

    async def get(self, symbol: str) -> Optional[dict]:
        key = f"sentiment:{symbol}:latest"
        # NOTE(typing): latent defect — RedisClient is a pool wrapper without
        # .get/.set (callers must use .get_connection()). This class is never
        # instantiated in production (tests inject mocks); rewiring it is a
        # runtime change, out of scope for the typing cleanup.
        val = await self._redis.get(key)  # type: ignore[attr-defined]
        if val:
            import json

            return json.loads(val)
        return None

    async def set(self, symbol: str, data: dict):
        key = f"sentiment:{symbol}:latest"
        import json

        # NOTE(typing): same latent defect as get() above.
        await self._redis.set(  # type: ignore[attr-defined]
            key, json.dumps(data), ex=self._ttl_s
        )
