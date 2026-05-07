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

    async def aggregate_approved_by_attribute(
        self,
        *,
        dimension: str,
        profile_id: Optional[UUID] = None,
        symbol: Optional[str] = None,
        window_hours: int = 168,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Bucket APPROVED trade decisions by a single attribute.

        ``dimension`` selects the bucket expression. These attributes live
        on trade_decisions itself (or its JSONB columns), distinct from
        the closed-side aggregator on ClosedTradeRepository.

        - ``symbol``:        symbol traded
        - ``direction``:     strategy.direction (BUY/SELL)
        - ``hour``:          UTC hour bucket of created_at
        - ``day_of_week``:   UTC weekday of created_at
        - ``regime``:        regime.regime (NULL → 'unknown')

        Output rows: bucket label, count, percent of total in window.
        Approved decisions don't have realized PnL until they close, so
        we deliberately do NOT JOIN closed_trades here — that's the
        Closed Trades tab's job. Use this view to inspect what kinds of
        decisions the engine *approved*, regardless of eventual outcome.
        """
        bucket_exprs: Dict[str, str] = {
            "symbol": "d.symbol",
            "direction": "COALESCE(d.strategy->>'direction', 'unknown')",
            "regime": "COALESCE(d.regime->>'regime', 'unknown')",
            "hour": (
                "CASE "
                "WHEN EXTRACT(hour FROM d.created_at AT TIME ZONE 'UTC') < 6  THEN 'night (00–05 UTC)' "
                "WHEN EXTRACT(hour FROM d.created_at AT TIME ZONE 'UTC') < 12 THEN 'morning (06–11 UTC)' "
                "WHEN EXTRACT(hour FROM d.created_at AT TIME ZONE 'UTC') < 18 THEN 'afternoon (12–17 UTC)' "
                "ELSE 'evening (18–23 UTC)' "
                "END"
            ),
            "day_of_week": (
                "CASE EXTRACT(dow FROM d.created_at AT TIME ZONE 'UTC')::INT "
                "WHEN 0 THEN 'Sun' "
                "WHEN 1 THEN 'Mon' "
                "WHEN 2 THEN 'Tue' "
                "WHEN 3 THEN 'Wed' "
                "WHEN 4 THEN 'Thu' "
                "WHEN 5 THEN 'Fri' "
                "WHEN 6 THEN 'Sat' "
                "END"
            ),
        }
        if dimension not in bucket_exprs:
            raise ValueError(f"Unknown dimension: {dimension!r}")
        bucket_expr = bucket_exprs[dimension]

        conditions: list = ["d.created_at >= NOW() - ($1 || ' hours')::INTERVAL",
                            "d.outcome = 'APPROVED'",
                            "d.shadow = FALSE"]
        params: list = [str(window_hours)]
        idx = 2
        if profile_id:
            conditions.append(f"d.profile_id = ${idx}")
            params.append(profile_id)
            idx += 1
        if symbol:
            conditions.append(f"d.symbol = ${idx}")
            params.append(symbol)
            idx += 1
        params.append(limit)

        where = "WHERE " + " AND ".join(conditions)

        query = f"""
        WITH bucketed AS (
            SELECT {bucket_expr} AS bucket
            FROM trade_decisions d
            {where}
        ),
        totals AS (
            SELECT COUNT(*)::FLOAT AS total FROM bucketed
        )
        SELECT
            b.bucket,
            COUNT(*)::INT  AS count,
            CASE WHEN t.total > 0 THEN COUNT(*)::FLOAT / t.total ELSE NULL END AS percent
        FROM bucketed b CROSS JOIN totals t
        GROUP BY b.bucket, t.total
        ORDER BY count DESC, b.bucket ASC
        LIMIT ${idx}
        """
        rows = await self._fetch(query, *params)

        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            v = d.get("percent")
            if v is not None:
                d["percent"] = float(v)
            out.append(d)
        return out
