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

    async def aggregate_by_attribute(
        self,
        *,
        dimension: str,
        profile_id: Optional[UUID] = None,
        symbol: Optional[str] = None,
        window_hours: int = 168,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Bucket closed trades by a single closed_trades attribute.

        ``dimension`` selects the bucket expression:

        - ``side``:           BUY vs SELL
        - ``regime``:         entry_regime (NULL → 'unknown')
        - ``hold_duration``:  < 1h, 1–6h, 6–24h, ≥ 24h
        - ``hour``:           night/morning/afternoon/evening (UTC)
        - ``day_of_week``:    Mon..Sun (UTC)

        Output rows: bucket label, count, win/loss/breakeven counts, win
        rate, avg realized PnL %, avg realized PnL ($). Ordered by count
        descending — partner-facing readers care about the heaviest
        buckets first.
        """
        bucket_exprs: Dict[str, str] = {
            "symbol": "ct.symbol",
            "side": "ct.side",
            "regime": "COALESCE(ct.entry_regime, 'unknown')",
            "outcome": "ct.outcome",
            "close_reason": "ct.close_reason",
            "hold_duration": (
                "CASE "
                "WHEN ct.holding_duration_s < 3600 THEN '< 1h' "
                "WHEN ct.holding_duration_s < 21600 THEN '1–6h' "
                "WHEN ct.holding_duration_s < 86400 THEN '6–24h' "
                "ELSE '≥ 24h' "
                "END"
            ),
            "hour": (
                "CASE "
                "WHEN EXTRACT(hour FROM ct.opened_at AT TIME ZONE 'UTC') < 6  THEN 'night (00–05 UTC)' "
                "WHEN EXTRACT(hour FROM ct.opened_at AT TIME ZONE 'UTC') < 12 THEN 'morning (06–11 UTC)' "
                "WHEN EXTRACT(hour FROM ct.opened_at AT TIME ZONE 'UTC') < 18 THEN 'afternoon (12–17 UTC)' "
                "ELSE 'evening (18–23 UTC)' "
                "END"
            ),
            "day_of_week": (
                "CASE EXTRACT(dow FROM ct.opened_at AT TIME ZONE 'UTC')::INT "
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

        conditions: list = ["ct.closed_at >= NOW() - ($1 || ' hours')::INTERVAL"]
        params: list = [str(window_hours)]
        idx = 2
        if profile_id:
            conditions.append(f"ct.profile_id = ${idx}")
            params.append(profile_id)
            idx += 1
        if symbol:
            conditions.append(f"ct.symbol = ${idx}")
            params.append(symbol)
            idx += 1
        params.append(limit)

        where = "WHERE " + " AND ".join(conditions)

        query = f"""
        SELECT
            {bucket_expr} AS bucket,
            COUNT(*)::INT                                            AS count,
            COUNT(*) FILTER (WHERE ct.outcome = 'win')::INT          AS win_count,
            COUNT(*) FILTER (WHERE ct.outcome = 'loss')::INT         AS loss_count,
            COUNT(*) FILTER (WHERE ct.outcome = 'breakeven')::INT    AS breakeven_count,
            AVG(ct.realized_pnl_pct)::NUMERIC(10,6)                  AS avg_pnl_pct,
            AVG(ct.realized_pnl)::NUMERIC(20,8)                      AS avg_pnl_usd
        FROM closed_trades ct
        {where}
        GROUP BY bucket
        ORDER BY count DESC, bucket ASC
        LIMIT ${idx}
        """
        rows = await self._fetch(query, *params)

        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            n = d["count"] or 0
            d["win_rate"] = (d["win_count"] / n) if n else None
            for key in ("avg_pnl_pct", "avg_pnl_usd"):
                v = d.get(key)
                if v is not None:
                    d[key] = float(v)
            out.append(d)
        return out

    async def aggregate_rule_heatmap(
        self,
        *,
        profile_id: Optional[UUID] = None,
        symbol: Optional[str] = None,
        window_hours: int = 168,
        min_trades: int = 1,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Aggregate closed-trade outcomes by rule fingerprint.

        Fingerprint is the sorted tuple of ``indicator:operator:threshold``
        from ``trade_decisions.strategy.conditions[]``, joined with ``|``.
        Two decisions whose conditions match in any order produce the same
        fingerprint; ``actual_value`` is intentionally excluded (it's
        per-decision noise, not part of the rule).

        Buckets with ``trade_count < min_trades`` are dropped — a single-
        trade fingerprint isn't actionable.
        """
        conditions: list = ["ct.closed_at >= NOW() - ($1 || ' hours')::INTERVAL",
                            "d.outcome = 'APPROVED'"]
        params: list = [str(window_hours), min_trades]
        idx = 3
        if profile_id:
            conditions.append(f"ct.profile_id = ${idx}")
            params.append(profile_id)
            idx += 1
        if symbol:
            conditions.append(f"ct.symbol = ${idx}")
            params.append(symbol)
            idx += 1
        params.append(limit)

        where = "WHERE " + " AND ".join(conditions)

        query = f"""
        WITH unrolled AS (
            SELECT
                d.event_id,
                d.created_at,
                cond->>'indicator' AS indicator,
                cond->>'operator'  AS operator,
                cond->>'threshold' AS threshold
            FROM closed_trades ct
            INNER JOIN trade_decisions d
                ON d.event_id = ct.decision_event_id
            CROSS JOIN LATERAL jsonb_array_elements(d.strategy->'conditions') AS cond
            {where}
        ),
        fingerprinted AS (
            SELECT
                event_id,
                created_at,
                string_agg(
                    indicator || ':' || operator || ':' || threshold,
                    ' | '
                    ORDER BY indicator, operator, threshold
                ) AS fingerprint
            FROM unrolled
            GROUP BY event_id, created_at
        )
        SELECT
            f.fingerprint,
            COUNT(*)::INT                                            AS trade_count,
            COUNT(*) FILTER (WHERE ct.outcome = 'win')::INT          AS win_count,
            COUNT(*) FILTER (WHERE ct.outcome = 'loss')::INT         AS loss_count,
            COUNT(*) FILTER (WHERE ct.outcome = 'breakeven')::INT    AS breakeven_count,
            AVG(ct.realized_pnl_pct)::NUMERIC(10,6)                  AS avg_pnl_pct,
            AVG(ct.realized_pnl)::NUMERIC(20,8)                      AS avg_pnl_usd,
            MIN(ct.closed_at)                                        AS first_trade_at,
            MAX(ct.closed_at)                                        AS last_trade_at
        FROM fingerprinted f
        INNER JOIN closed_trades ct
            ON ct.decision_event_id = f.event_id
        GROUP BY f.fingerprint
        HAVING COUNT(*) >= $2
        ORDER BY trade_count DESC, fingerprint ASC
        LIMIT ${idx}
        """
        rows = await self._fetch(query, *params)

        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            n = d["trade_count"] or 0
            d["win_rate"] = (d["win_count"] / n) if n else None
            for key in ("avg_pnl_pct", "avg_pnl_usd"):
                v = d.get(key)
                if v is not None:
                    d[key] = float(v)
            for key in ("first_trade_at", "last_trade_at"):
                v = d.get(key)
                if v is not None and hasattr(v, "isoformat"):
                    d[key] = v.isoformat()
            out.append(d)
        return out

    async def aggregate_agent_attribution(
        self,
        *,
        profile_id: Optional[UUID] = None,
        symbol: Optional[str] = None,
        window_hours: int = 168,
        threshold: float = 0.15,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """Bucket closed trades by the agreement pattern of TA / sentiment / debate.

        For each closed trade we look up the originating decision's per-agent
        score and bucket the score into BULL (> +threshold), BEAR
        (< -threshold), or NEUTRAL. The 3-tuple of buckets is the "agreement
        pattern" — e.g. ``TA_BULL+SENT_BULL+DBT_NEUTRAL`` — and we aggregate
        realized P&L over that bucket.

        Output rows: pattern string, count, win/loss/breakeven counts, win
        rate, average realized PnL %, average realized PnL (USD), and the
        average confidence lift (``confidence_after - confidence_before``).
        Rows ordered by count descending; truncated at ``limit`` because the
        long tail of rare patterns isn't actionable.

        Limitations: relies on ``decision_event_id`` being populated on the
        closed_trade row (PR1 audit chain shipped this). Trades whose
        decision row was pruned by archiver retention are silently dropped.
        """
        conditions: list = ["ct.closed_at >= NOW() - ($1 || ' hours')::INTERVAL",
                            "d.outcome = 'APPROVED'"]
        params: list = [str(window_hours), threshold]
        idx = 3
        if profile_id:
            conditions.append(f"ct.profile_id = ${idx}")
            params.append(profile_id)
            idx += 1
        if symbol:
            conditions.append(f"ct.symbol = ${idx}")
            params.append(symbol)
            idx += 1
        params.append(limit)

        where = "WHERE " + " AND ".join(conditions)

        # NB: $2 is the threshold, reused three times in the CASE expressions.
        # asyncpg lets the same numbered placeholder appear multiple times.
        query = f"""
        WITH bucketed AS (
            SELECT
                CASE
                    WHEN (d.agents#>>'{{ta,score}}')::FLOAT > $2 THEN 'TA_BULL'
                    WHEN (d.agents#>>'{{ta,score}}')::FLOAT < -$2 THEN 'TA_BEAR'
                    ELSE 'TA_NEUTRAL'
                END AS ta_bucket,
                CASE
                    WHEN (d.agents#>>'{{sentiment,score}}')::FLOAT > $2 THEN 'SENT_BULL'
                    WHEN (d.agents#>>'{{sentiment,score}}')::FLOAT < -$2 THEN 'SENT_BEAR'
                    ELSE 'SENT_NEUTRAL'
                END AS sent_bucket,
                CASE
                    WHEN (d.agents#>>'{{debate,score}}')::FLOAT > $2 THEN 'DBT_BULL'
                    WHEN (d.agents#>>'{{debate,score}}')::FLOAT < -$2 THEN 'DBT_BEAR'
                    ELSE 'DBT_NEUTRAL'
                END AS debate_bucket,
                COALESCE(
                    (d.agents->>'confidence_after')::FLOAT
                  - (d.agents->>'confidence_before')::FLOAT,
                    0
                ) AS confidence_lift,
                ct.realized_pnl_pct,
                ct.realized_pnl,
                ct.outcome
            FROM closed_trades ct
            INNER JOIN trade_decisions d
                ON d.event_id = ct.decision_event_id
            {where}
        )
        SELECT
            ta_bucket || '+' || sent_bucket || '+' || debate_bucket  AS pattern,
            ta_bucket,
            sent_bucket,
            debate_bucket,
            COUNT(*)::INT                                            AS count,
            COUNT(*) FILTER (WHERE outcome = 'win')::INT             AS win_count,
            COUNT(*) FILTER (WHERE outcome = 'loss')::INT            AS loss_count,
            COUNT(*) FILTER (WHERE outcome = 'breakeven')::INT       AS breakeven_count,
            AVG(realized_pnl_pct)::NUMERIC(10,6)                     AS avg_pnl_pct,
            AVG(realized_pnl)::NUMERIC(20,8)                         AS avg_pnl_usd,
            AVG(confidence_lift)::NUMERIC(10,6)                      AS avg_confidence_lift
        FROM bucketed
        GROUP BY ta_bucket, sent_bucket, debate_bucket
        ORDER BY count DESC
        LIMIT ${idx}
        """
        rows = await self._fetch(query, *params)

        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            n = d["count"] or 0
            d["win_rate"] = (d["win_count"] / n) if n else None
            for key in ("avg_pnl_pct", "avg_pnl_usd", "avg_confidence_lift"):
                v = d.get(key)
                if v is not None:
                    d[key] = float(v)
            out.append(d)
        return out

    async def aggregate_close_reasons(
        self,
        *,
        profile_id: Optional[UUID] = None,
        symbol: Optional[str] = None,
        regime: Optional[str] = None,
        window_hours: int = 168,
        group_by_regime: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return per-close_reason aggregates for the most recent ``window_hours``.

        Output rows include count, win/loss/breakeven counts, win rate,
        average realized PnL %, and median holding duration. When
        ``group_by_regime`` is True, rows are split by ``entry_regime`` as
        well — the regime bucket is NULL for trades that closed without a
        recorded regime, which is preserved as the literal string
        ``"unknown"`` so the frontend doesn't have to special-case it.
        """
        conditions: list = ["closed_at >= NOW() - ($1 || ' hours')::INTERVAL"]
        params: list = [str(window_hours)]
        idx = 2
        if profile_id:
            conditions.append(f"profile_id = ${idx}")
            params.append(profile_id)
            idx += 1
        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1
        if regime:
            conditions.append(f"COALESCE(entry_regime, 'unknown') = ${idx}")
            params.append(regime)
            idx += 1

        where = "WHERE " + " AND ".join(conditions)
        regime_select = ", COALESCE(entry_regime, 'unknown') AS regime" if group_by_regime else ""
        regime_group = ", COALESCE(entry_regime, 'unknown')" if group_by_regime else ""
        order_extra = ", regime" if group_by_regime else ""

        query = f"""
        SELECT
            close_reason
            {regime_select},
            COUNT(*)::INT AS count,
            COUNT(*) FILTER (WHERE outcome = 'win')::INT       AS win_count,
            COUNT(*) FILTER (WHERE outcome = 'loss')::INT      AS loss_count,
            COUNT(*) FILTER (WHERE outcome = 'breakeven')::INT AS breakeven_count,
            AVG(realized_pnl_pct)::NUMERIC(10,6)               AS avg_pnl_pct,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY holding_duration_s)::INT
                                                               AS median_holding_s
        FROM closed_trades
        {where}
        GROUP BY close_reason{regime_group}
        ORDER BY count DESC{order_extra}
        """
        rows = await self._fetch(query, *params)

        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            n = d["count"] or 0
            d["win_rate"] = (d["win_count"] / n) if n else None
            # Decimal → float for JSON; absent rows already None.
            if d.get("avg_pnl_pct") is not None:
                d["avg_pnl_pct"] = float(d["avg_pnl_pct"])
            out.append(d)
        return out
