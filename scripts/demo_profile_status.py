"""Comprehensive status snapshot for the demo profile."""
import asyncio
from pathlib import Path
import asyncpg

PROFILE_ID = "c557fcdc-2bc2-4ef3-8004-102cd71859c0"


def url() -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace(
                "postgresql+asyncpg://", "postgresql://"
            )
    raise SystemExit("missing")


async def main() -> None:
    c = await asyncpg.connect(url())
    try:
        first = await c.fetchval(
            "SELECT MIN(created_at) FROM trade_decisions WHERE profile_id = $1::uuid", PROFILE_ID
        )
        last = await c.fetchval(
            "SELECT MAX(created_at) FROM trade_decisions WHERE profile_id = $1::uuid", PROFILE_ID
        )
        total = await c.fetchval(
            "SELECT COUNT(*) FROM trade_decisions WHERE profile_id = $1::uuid", PROFILE_ID
        )
        print(f"=== Demo · Pullback Long ({PROFILE_ID[:8]}…) ===")
        print(f"first decision: {first}")
        print(f"latest:         {last}")
        if first and last:
            mins = (last - first).total_seconds() / 60
            print(f"window:         {mins:.1f} min")
            if mins > 0:
                print(f"rate:           {total / mins:.1f} decisions/min")
        print(f"total:          {total}")

        print("\n=== outcome breakdown ===")
        rows = await c.fetch(
            """
            SELECT outcome, COUNT(*) AS n FROM trade_decisions
            WHERE profile_id = $1::uuid GROUP BY outcome ORDER BY n DESC
            """,
            PROFILE_ID,
        )
        for r in rows:
            print(f"  {r['outcome']:<25} {r['n']:>5}  ({100*r['n']/total:.1f}%)")

        print("\n=== symbol breakdown ===")
        rows = await c.fetch(
            """
            SELECT symbol, COUNT(*) AS n FROM trade_decisions
            WHERE profile_id = $1::uuid GROUP BY symbol ORDER BY n DESC
            """,
            PROFILE_ID,
        )
        for r in rows:
            print(f"  {r['symbol']:<15} {r['n']:>5}")

        print("\n=== HITL pending queue ===")
        # The HITL gate writes a row to hitl_pending when blocking. Operators
        # respond via /hitl/respond, which moves the trade forward.
        try:
            pending = await c.fetch(
                """
                SELECT created_at, symbol, status FROM hitl_pending
                WHERE profile_id = $1::uuid
                ORDER BY created_at DESC LIMIT 10
                """,
                PROFILE_ID,
            )
            if not pending:
                print("  (empty — either nothing in queue or table not present)")
            else:
                pcount = await c.fetchval(
                    "SELECT COUNT(*) FROM hitl_pending WHERE profile_id = $1::uuid",
                    PROFILE_ID,
                )
                print(f"  total in queue: {pcount}")
                print("  most recent:")
                for r in pending:
                    print(f"    {r['created_at']}  {r['symbol']}  {r['status']}")
        except asyncpg.exceptions.UndefinedTableError:
            print("  hitl_pending table does not exist — HITL state may live in Redis")

        print("\n=== orders / positions / closed ===")
        n_o = await c.fetchval("SELECT COUNT(*) FROM orders WHERE profile_id = $1::uuid", PROFILE_ID)
        n_p = await c.fetchval("SELECT COUNT(*) FROM positions WHERE profile_id = $1::uuid", PROFILE_ID)
        n_c = await c.fetchval("SELECT COUNT(*) FROM closed_trades WHERE profile_id = $1::uuid", PROFILE_ID)
        print(f"  orders:         {n_o}")
        print(f"  positions:      {n_p}")
        print(f"  closed_trades:  {n_c}")

        print("\n=== last 5 decisions (verbose) ===")
        rows = await c.fetch(
            """
            SELECT created_at, symbol, outcome,
                   indicators->>'rsi' AS rsi,
                   indicators->>'histogram' AS macd_hist
            FROM trade_decisions
            WHERE profile_id = $1::uuid ORDER BY created_at DESC LIMIT 5
            """,
            PROFILE_ID,
        )
        for r in rows:
            rsi = float(r['rsi']) if r['rsi'] else None
            mh = float(r['macd_hist']) if r['macd_hist'] else None
            print(
                f"  {r['created_at']}  {r['symbol']}  {r['outcome']:<20} "
                f"rsi={rsi:.1f if rsi else None}  macd_hist={mh:.3f if mh else None}"
                if rsi is not None and mh is not None
                else f"  {r['created_at']}  {r['symbol']}  {r['outcome']}"
            )
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
