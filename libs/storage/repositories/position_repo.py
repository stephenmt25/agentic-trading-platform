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
        """Legacy unguarded close (OPEN/any -> CLOSED). Retained as the fallback
        used by PositionCloser.close() when PRAXIS_EXCHANGE_CLOSE_ENABLED is off.
        The real-exchange-close path uses the CAS methods below instead."""
        query = """
        UPDATE positions
        SET status = 'CLOSED', closed_at = $1, exit_price = $2
        WHERE position_id = $3
        """
        await self._execute(query, datetime.now(timezone.utc), exit_price, position_id)

    # --- Real-exchange-close lifecycle (PR1) ------------------------------
    # Compare-and-set transitions. Each returns True only if THIS call moved the
    # row, which makes the close idempotent: the exit monitor runs every tick and
    # the manual endpoint is concurrent, so without a status guard a position
    # would spawn multiple reduce-only orders and double-bump the daily-PnL
    # counter / agent EWMA (neither is protected by the closed_trades conflict
    # guard). RETURNING + None-check gives exactly-once semantics.

    async def begin_close(self, position_id: UUID, close_order_id: UUID) -> bool:
        """CAS OPEN -> PENDING_CLOSE, recording the reduce-only close order id.
        Returns True iff this call won the transition (so only one close order is
        ever published per position)."""
        query = """
        UPDATE positions
        SET status = 'PENDING_CLOSE', close_order_id = $2
        WHERE position_id = $1 AND status = 'OPEN'
        RETURNING position_id
        """
        row = await self._fetchrow(query, position_id, close_order_id)
        return row is not None

    async def finalize_close(self, position_id: UUID, exit_price: Price) -> bool:
        """CAS PENDING_CLOSE -> CLOSED at the confirmed exchange fill price.
        Returns True iff this call won the transition, so a duplicate fill event
        is a no-op and the PnL/closed_trades/daily-bump writes that follow run
        exactly once."""
        query = """
        UPDATE positions
        SET status = 'CLOSED', closed_at = $1, exit_price = $2
        WHERE position_id = $3 AND status = 'PENDING_CLOSE'
        RETURNING position_id
        """
        row = await self._fetchrow(query, datetime.now(timezone.utc), exit_price, position_id)
        return row is not None

    async def revert_close(self, position_id: UUID) -> bool:
        """CAS PENDING_CLOSE -> OPEN, clearing close_order_id. Used when the
        reduce-only close order is rejected so the position is monitored again."""
        query = """
        UPDATE positions
        SET status = 'OPEN', close_order_id = NULL
        WHERE position_id = $1 AND status = 'PENDING_CLOSE'
        RETURNING position_id
        """
        row = await self._fetchrow(query, position_id)
        return row is not None

    async def get_by_id(self, position_id: UUID) -> Optional[Any]:
        """Fetch a single position row by id. Used by the close consumer to load
        a PENDING_CLOSE position when its reduce-only fill arrives."""
        query = "SELECT * FROM positions WHERE position_id = $1"
        record = await self._fetchrow(query, position_id)
        return dict(record) if record else None

    async def set_protective_order_id(self, position_id: UUID, protective_order_id: str) -> None:
        """Record the exchange-side protective-stop order id placed at open
        (the venue's id string). Best-effort metadata — never on a hot path."""
        query = "UPDATE positions SET protective_order_id = $2 WHERE position_id = $1"
        await self._execute(query, position_id, protective_order_id)

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
