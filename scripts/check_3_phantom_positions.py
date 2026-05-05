"""Check the 3 mystery positions: when did their decisions happen, and did
the close-all script touch them?"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from libs.config import settings
import asyncpg


PHANTOM_POSITIONS = [
    "50dce658-0b48-454e-bcde-d6e03b9788ae",
    "5da03984-2b30-4102-b581-a83f2181d992",
    "b41c569f-c1e1-417c-8cf6-9064a902ba07",
]


async def main() -> int:
    db = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    c = await asyncpg.connect(db)
    try:
        print("=== Decisions that opened these 3 positions ===")
        rows = await c.fetch(
            """SELECT event_id::text, created_at, symbol, outcome, profile_id::text AS pid
               FROM trade_decisions WHERE event_id = ANY($1::uuid[])""",
            PHANTOM_POSITIONS,
        )
        for r in rows:
            print(f"  decision {r['event_id'][:8]}  {r['created_at']}  {r['symbol']}  {r['outcome']}  prof={r['pid'][:8]}")

        print("\n=== Positions table for these decisions (any status) ===")
        rows = await c.fetch(
            """SELECT position_id::text, status, opened_at, closed_at, exit_price, decision_event_id::text
               FROM positions WHERE decision_event_id = ANY($1::uuid[])""",
            PHANTOM_POSITIONS,
        )
        for r in rows:
            print(f"  pos {r['position_id'][:8]}  status={r['status']}  opened={r['opened_at']}  closed={r['closed_at']}  exit=${r['exit_price']}")

        print("\n=== closed_trades for these decisions ===")
        rows = await c.fetch(
            """SELECT position_id::text, closed_at, outcome, realized_pnl, close_reason
               FROM closed_trades WHERE decision_event_id = ANY($1::uuid[])""",
            PHANTOM_POSITIONS,
        )
        for r in rows:
            print(f"  pos {r['position_id'][:8]}  closed={r['closed_at']}  outcome={r['outcome']}  pnl=${r['realized_pnl']}  reason={r['close_reason']}")
        if not rows:
            print("  (no closed_trades rows — these were never officially closed)")

        print("\n=== Any duplicate position rows by decision_event_id? ===")
        rows = await c.fetch(
            """SELECT decision_event_id::text, COUNT(*) AS n, array_agg(status) AS statuses
               FROM positions WHERE decision_event_id = ANY($1::uuid[])
               GROUP BY decision_event_id"""
            ,
            PHANTOM_POSITIONS,
        )
        for r in rows:
            print(f"  decision {r['decision_event_id'][:8]}  {r['n']} position row(s)  statuses={r['statuses']}")
    finally:
        await c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
