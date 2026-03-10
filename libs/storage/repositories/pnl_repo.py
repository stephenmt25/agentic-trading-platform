from typing import List, Dict, Any, Optional
from datetime import datetime
from libs.core.types import ProfileId
from ._repository_base import BaseRepository

class PnlRepository(BaseRepository):
    async def write_snapshot(self, snapshot: Dict[str, Any]):
        query = """
        INSERT INTO pnl_snapshots (
            profile_id, symbol, gross_pnl, net_pnl_pre_tax, net_pnl_post_tax, 
            total_fees, estimated_tax, cost_basis, pct_return, snapshot_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        await self._execute(
            query,
            snapshot['profile_id'],
            snapshot['symbol'],
            snapshot['gross_pnl'],
            snapshot['net_pnl_pre_tax'],
            snapshot['net_pnl_post_tax'],
            snapshot['total_fees'],
            snapshot['estimated_tax'],
            snapshot['cost_basis'],
            snapshot['pct_return'],
            snapshot.get('snapshot_at', datetime.utcnow())
        )

    async def get_snapshots(self, profile_id: ProfileId, start: datetime, end: datetime) -> List[Any]:
        query = """
        SELECT * FROM pnl_snapshots 
        WHERE profile_id = $1 AND snapshot_at BETWEEN $2 AND $3
        ORDER BY snapshot_at ASC
        """
        return await self._fetch(query, profile_id, start, end)

    async def get_latest(self, profile_id: ProfileId) -> Optional[Any]:
        query = """
        SELECT * FROM pnl_snapshots 
        WHERE profile_id = $1 
        ORDER BY snapshot_at DESC LIMIT 1
        """
        return await self._fetchrow(query, profile_id)
