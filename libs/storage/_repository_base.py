from ._timescale_client import TimescaleClient
from typing import Any, List, Optional
import asyncpg

class BaseRepository:
    def __init__(self, db: TimescaleClient):
        self._db = db

    async def _execute(self, query: str, *args: Any) -> str:
        return await self._db.execute(query, *args)

    async def _fetch(self, query: str, *args: Any) -> List[asyncpg.Record]:
        return await self._db.fetch(query, *args)

    async def _fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        return await self._db.fetchrow(query, *args)
