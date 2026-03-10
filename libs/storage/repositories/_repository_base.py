from typing import Any, List, Optional
from .._timescale_client import TimescaleClient

class BaseRepository:
    def __init__(self, db_client: TimescaleClient):
        self._db = db_client

    async def _execute(self, query: str, *args: Any) -> str:
        return await self._db.execute(query, *args)

    async def _fetch(self, query: str, *args: Any) -> List[Any]:
        return await self._db.fetch(query, *args)

    async def _fetchrow(self, query: str, *args: Any) -> Optional[Any]:
        return await self._db.fetchrow(query, *args)
