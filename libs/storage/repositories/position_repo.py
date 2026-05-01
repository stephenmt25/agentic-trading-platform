from typing import Any, Dict, List, Optional
from uuid import UUID
from libs.core.models import Position
from libs.core.enums import PositionStatus
from libs.core.types import Price, ProfileId, SymbolPair
from ._repository_base import BaseRepository
from datetime import datetime, timezone

class PositionRepository(BaseRepository):
    async def create_position(self, position: Position):
        query = """
        INSERT INTO positions (
            position_id, profile_id, symbol, side, entry_price,
            quantity, entry_fee, opened_at, status,
            order_id, decision_event_id
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """
        status: str = position.status.value if isinstance(position.status, PositionStatus) else str(position.status)

        await self._execute(
            query,
            position.position_id,
            position.profile_id,
            position.symbol,
            position.side.value,
            position.entry_price,
            position.quantity,
            position.entry_fee,
            position.opened_at,
            status,
            position.order_id,
            position.decision_event_id,
        )

    async def close_position(self, position_id: UUID, exit_price: Price):
        query = """
        UPDATE positions 
        SET status = 'CLOSED', closed_at = $1, exit_price = $2
        WHERE position_id = $3
        """
        await self._execute(query, datetime.now(timezone.utc), exit_price, position_id)

    async def get_open_positions(self, profile_id: ProfileId = None) -> List[Any]:
        if profile_id:
            query = "SELECT * FROM positions WHERE profile_id = $1 AND status = 'OPEN'"
            return await self._fetch(query, profile_id)
        else:
            query = "SELECT * FROM positions WHERE status = 'OPEN'"
            return await self._fetch(query)

    async def get_positions_for_symbol(self, symbol: SymbolPair) -> List[Any]:
        query = "SELECT * FROM positions WHERE symbol = $1 AND status = 'OPEN'"
        return await self._fetch(query, symbol)

    async def get_by_decision_event_id(self, decision_event_id: UUID) -> Optional[Any]:
        """Find the position opened from a given trade_decisions.event_id (PR1 audit chain)."""
        query = """
        SELECT * FROM positions
        WHERE decision_event_id = $1
        ORDER BY opened_at DESC
        LIMIT 1
        """
        record = await self._fetchrow(query, decision_event_id)
        return dict(record) if record else None
