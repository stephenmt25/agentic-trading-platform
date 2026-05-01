import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID
from ._repository_base import BaseRepository


class _TraceEncoder(json.JSONEncoder):
    """Handles numpy scalars and Decimals in trace JSONB columns."""

    def default(self, o):
        # numpy bool_ / int_ / float_ are not JSON-serializable by default
        if hasattr(o, "item"):
            return o.item()
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _dumps(obj) -> str:
    return json.dumps(obj, cls=_TraceEncoder)


class DecisionRepository(BaseRepository):
    """Repository for trade_decisions table — full decision trace persistence."""

    async def write_decision(
        self,
        event_id: UUID,
        profile_id: UUID,
        symbol: str,
        outcome: str,
        input_price,
        input_volume,
        indicators: dict,
        strategy: dict,
        regime: Optional[dict],
        agents: Optional[dict],
        gates: dict,
        profile_rules: dict,
        order_id: Optional[UUID] = None,
        created_at=None,
        shadow: bool = False,
    ) -> None:
        query = """
        INSERT INTO trade_decisions
            (event_id, profile_id, symbol, outcome, input_price, input_volume,
             indicators, strategy, regime, agents, gates, profile_rules, order_id, shadow, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, COALESCE($15, NOW()))
        """
        await self._execute(
            query,
            event_id,
            profile_id,
            symbol,
            outcome,
            input_price,
            input_volume,
            _dumps(indicators),
            _dumps(strategy),
            _dumps(regime) if regime else None,
            _dumps(agents) if agents else None,
            _dumps(gates),
            _dumps(profile_rules),
            order_id,
            shadow,
            created_at,
        )

    async def get_decisions(
        self,
        profile_id: Optional[str] = None,
        symbol: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        shadow: Optional[bool] = False,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: list = []
        idx = 1

        if profile_id:
            conditions.append(f"profile_id = ${idx}")
            params.append(UUID(profile_id))
            idx += 1
        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1
        if outcome:
            conditions.append(f"outcome = ${idx}")
            params.append(outcome)
            idx += 1
        # shadow filter: explicit None means "include everything", default False
        # excludes shadow rows so the live Decision Feed stays clean.
        if shadow is not None:
            conditions.append(f"shadow = ${idx}")
            params.append(shadow)
            idx += 1

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"""
        SELECT * FROM trade_decisions
        {where}
        ORDER BY created_at DESC
        OFFSET ${idx} LIMIT ${idx + 1}
        """
        params.extend([offset, limit])
        records = await self._fetch(query, *params)
        return [dict(r) for r in records]

    async def get_decision(self, event_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM trade_decisions WHERE event_id = $1 LIMIT 1"
        row = await self._fetchrow(query, UUID(event_id))
        return dict(row) if row else None
