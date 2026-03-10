from libs.storage._redis_client import RedisClient

class SentimentCache:
    def __init__(self, redis_client: RedisClient, ttl_s: int = 900):
        self._redis = redis_client
        self._ttl_s = ttl_s

    async def get(self, symbol: str) -> dict:
        key = f"sentiment:{symbol}:latest"
        val = await self._redis.get(key)
        if val:
            import json
            return json.loads(val)
        return None

    async def set(self, symbol: str, data: dict):
        key = f"sentiment:{symbol}:latest"
        import json
        await self._redis.set(key, json.dumps(data), ex=self._ttl_s)
