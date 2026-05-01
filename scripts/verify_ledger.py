"""Verify the 2nd-Brain (PR1) ledger is wired correctly.

Checks:
  1. Schema present: decision_event_id columns on orders+positions, closed_trades + debate_transcripts tables exist.
  2. Row counts in each table.
  3. PR1 acceptance join (the canonical query from docs/SECOND-BRAIN-PR1-PLAN.md).
  4. Coverage: what fraction of orders/positions/closed_trades have the linkage columns populated.
  5. Debate transcript sanity: count + structure of latest row.
"""
import asyncio
from pathlib import Path

import asyncpg


def db_url() -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            return v.replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit("missing PRAXIS_DATABASE_URL")


async def main() -> None:
    c = await asyncpg.connect(db_url())
    try:
        print("=== schema check ===")
        cols = await c.fetch(
            """
            SELECT table_name, column_name FROM information_schema.columns
            WHERE column_name = 'decision_event_id' ORDER BY table_name
            """
        )
        for r in cols:
            print(" ", dict(r))

        present = await c.fetchrow(
            """
            SELECT to_regclass('closed_trades') AS closed_trades,
                   to_regclass('debate_transcripts') AS debate_transcripts
            """
        )
        print(" ", dict(present))

        print("\n=== row counts ===")
        tables = [
            "trade_decisions", "orders", "positions",
            "closed_trades", "debate_transcripts",
            "agent_score_history", "agent_weight_history",
        ]
        for t in tables:
            n = await c.fetchval(f"SELECT COUNT(*) FROM {t}")
            print(f"  {t:<22} {n:>8}")

        print("\n=== PR1 acceptance join: most recent 5 EXECUTED/APPROVED chains ===")
        rows = await c.fetch(
            """
            SELECT
                td.event_id::text     AS decision,
                td.symbol,
                td.outcome,
                o.order_id::text      AS order_id,
                p.position_id::text   AS position_id,
                ct.exit_price,
                ct.close_reason,
                ct.realized_pnl_pct
            FROM trade_decisions td
            LEFT JOIN orders o          ON o.decision_event_id = td.event_id
            LEFT JOIN positions p       ON p.decision_event_id = td.event_id
            LEFT JOIN closed_trades ct  ON ct.position_id = p.position_id
            WHERE td.outcome IN ('APPROVED','EXECUTED')
              AND td.created_at > NOW() - INTERVAL '14 days'
            ORDER BY td.created_at DESC LIMIT 5
            """
        )
        if not rows:
            print("  (no APPROVED/EXECUTED decisions in last 14 days)")
        for r in rows:
            print(" ", dict(r))

        print("\n=== chain coverage ===")
        cov = await c.fetchrow(
            """
            SELECT
              COUNT(*)                                                  AS total_orders,
              COUNT(*) FILTER (WHERE decision_event_id IS NOT NULL)     AS orders_with_decision,
              COUNT(*) FILTER (WHERE decision_event_id IS NULL)         AS orders_without_decision
            FROM orders
            """
        )
        print(" orders:    ", dict(cov))
        cov = await c.fetchrow(
            """
            SELECT
              COUNT(*)                                                  AS total_positions,
              COUNT(*) FILTER (WHERE decision_event_id IS NOT NULL)     AS positions_with_decision
            FROM positions
            """
        )
        print(" positions: ", dict(cov))
        cov = await c.fetchrow(
            """
            SELECT
              COUNT(*)                                                  AS total_closed,
              COUNT(*) FILTER (WHERE position_id IS NOT NULL)           AS with_position,
              COUNT(*) FILTER (WHERE close_reason IS NOT NULL)          AS with_reason,
              COUNT(*) FILTER (WHERE realized_pnl_pct IS NOT NULL)      AS with_pnl
            FROM closed_trades
            """
        )
        print(" closed:    ", dict(cov))

        print("\n=== debate transcript sanity ===")
        n = await c.fetchval("SELECT COUNT(*) FROM debate_transcripts")
        print(f"  total transcripts: {n}")
        if n:
            latest = await c.fetchrow(
                """
                SELECT cycle_id::text, symbol, created_at,
                       jsonb_array_length(rounds) AS round_count
                FROM debate_transcripts ORDER BY created_at DESC LIMIT 1
                """
            )
            print("  latest:", dict(latest))

        print("\n=== latest decision: what does it link to? ===")
        latest = await c.fetchrow(
            """
            SELECT event_id::text, profile_id::text, symbol, outcome, created_at
            FROM trade_decisions ORDER BY created_at DESC LIMIT 1
            """
        )
        if latest:
            print(" ", dict(latest))
            ev = latest["event_id"]
            linked = await c.fetchrow(
                """
                SELECT
                  (SELECT COUNT(*) FROM orders     WHERE decision_event_id = $1::uuid) AS orders,
                  (SELECT COUNT(*) FROM positions  WHERE decision_event_id = $1::uuid) AS positions
                """,
                ev,
            )
            print("  links:", dict(linked))

        print("\n=== outcome distribution last 24h ===")
        rows = await c.fetch(
            """
            SELECT outcome, COUNT(*) AS n FROM trade_decisions
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY outcome ORDER BY n DESC
            """
        )
        if not rows:
            print("  (no decisions in last 24h)")
        for r in rows:
            print(" ", dict(r))
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
