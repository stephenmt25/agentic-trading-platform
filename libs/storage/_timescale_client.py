import asyncpg
from typing import Any, List, Optional
import asyncio

class TimescaleClient:
    _pool: Optional[asyncpg.Pool] = None

    def __init__(self, url: str):
        self._url = url

    async def init_pool(self):
        if not self._pool:
            self._pool = await asyncpg.create_pool(
                self._url,
                min_size=5,
                max_size=20,
                command_timeout=5.0
            )

    async def execute(self, query: str, *args: Any) -> str:
        if not self._pool:
            raise RuntimeError("Pool not initialized")
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> List[asyncpg.Record]:
        if not self._pool:
            raise RuntimeError("Pool not initialized")
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        if not self._pool:
            raise RuntimeError("Pool not initialized")
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def health_check(self) -> bool:
        if not self._pool:
            return False
        try:
            val = await self.fetchrow("SELECT 1")
            return val is not None
        except Exception:
            return False

    async def close(self):
        if self._pool:
            await self._pool.close()
