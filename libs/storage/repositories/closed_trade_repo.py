"""Repository for closed_trades — outcome mapping per closed position.

Append-only audit table. One row per closed position, written by the PnL
closer when a stop-loss / take-profit / time-exit fires. Joins back to
trade_decisions via decision_event_id and to positions via position_id (FK).
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from ._repository_base import BaseRepository


class _JsonEncoder(json.JSONEncoder):
    """Handles numpy scalars and Decimals in JSONB columns (entry_agent_scores)."""

    def default(self, o):
        if hasattr(o, "item"):
            return o.item()
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _dumps(obj) -> Optional[str]:
    if obj is None:
        return None
    return json.dumps(obj, cls=_JsonEncoder)


class ClosedTradeRepository(BaseRepository):
    async def write_closed_trade(
        self,
        position_id: UUID,
        profile_id: UUID,
        symbol: str,
        side: str,
        decision_event_id: Optional[UUID],
        order_id: Optional[UUID],
        entry_price: Decimal,
        entry_quantity: Decimal,
        entry_fee: Decimal,
        entry_regime: Optional[str],
        entry_agent_scores: Optional[dict],
        exit_price: Decimal,
        exit_fee: Decimal,
        close_reason: str,
        opened_at: datetime,
        closed_at: datetime,
        holding_duration_s: int,
        realized_pnl: Decimal,
        realized_pnl_pct: Decimal,
        outcome: str,
    ) -> None:
        query = """
        INSERT INTO closed_trades (
            position_id, profile_id, symbol, side, decision_event_id, order_id,
            entry_price, entry_quantity, entry_fee, entry_regime, entry_agent_scores,
            exit_price, exit_fee, close_reason, opened_at, closed_at, holding_duration_s,
            realized_pnl, realized_pnl_pct, outcome
        ) VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10, $11,
            $12, $13, $14, $15, $16, $17,
            $18, $19, $20
        )
        ON CONFLICT (position_id) DO NOTHING
        """
        await self._execute(
            query,
            position_id,
            profile_id,
            symbol,
            side,
            decision_event_id,
            order_id,
            entry_price,
            entry_quantity,
            entry_fee,
            entry_regime,
            _dumps(entry_agent_scores),
            exit_price,
            exit_fee,
            close_reason,
            opened_at,
            closed_at,
            holding_duration_s,
            realized_pnl,
            realized_pnl_pct,
            outcome,
        )

    async def get_recent(
        self,
        symbol: Optional[str] = None,
        profile_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        conditions: list = []
        params: list = []
        idx = 1

        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1
        if profile_id:
            conditions.append(f"profile_id = ${idx}")
            params.append(profile_id)
            idx += 1

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"""
        SELECT * FROM closed_trades
        {where}
        ORDER BY closed_at DESC
        LIMIT ${idx}
        """
        params.append(limit)
        rows = await self._fetch(query, *params)
        return [dict(r) for r in rows]

    async def get_by_position(self, position_id: UUID) -> Optional[Dict[str, Any]]:
        row = await self._fetchrow(
            "SELECT * FROM closed_trades WHERE position_id = $1", position_id
        )
        return dict(row) if row else None

    async def get_by_decision_event(self, decision_event_id: UUID) -> Optional[Dict[str, Any]]:
        row = await self._fetchrow(
            "SELECT * FROM closed_trades WHERE decision_event_id = $1 LIMIT 1",
            decision_event_id,
        )
        return dict(row) if row else None
