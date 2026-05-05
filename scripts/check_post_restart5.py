import asyncio
from datetime import datetime, timezone
from pathlib import Path
import asyncpg


def url() -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace(
                "postgresql+asyncpg://", "postgresql://"
            )


async def main() -> None:
    cutoff = datetime.fromtimestamp(
        Path(".praxis_logs/restart5.out").stat().st_mtime, tz=timezone.utc
    )
    print(f"cutoff (restart5): {cutoff.isoformat()}")
    c = await asyncpg.connect(url())
    try:
        n = await c.fetchval(
            "SELECT COUNT(*) FROM trade_decisions WHERE created_at > $1", cutoff
        )
        print(f"fresh decisions across all profiles: {n}")
        if n == 0:
            return
        rows = await c.fetch(
            """
            SELECT outcome, COUNT(*) AS n FROM trade_decisions
            WHERE created_at > $1
            GROUP BY outcome ORDER BY n DESC
            """,
            cutoff,
        )
        total = n
        for r in rows:
            print(f"  {r['outcome']:<25} {r['n']:>4}  ({100*r['n']/total:.1f}%)")
        n_o = await c.fetchval("SELECT COUNT(*) FROM orders WHERE created_at > $1", cutoff)
        n_p = await c.fetchval("SELECT COUNT(*) FROM positions WHERE opened_at > $1", cutoff)
        print(f"\nfresh orders: {n_o}")
        print(f"fresh positions: {n_p}")
        rows = await c.fetch(
            """
            SELECT created_at, profile_id::text, symbol, outcome
            FROM trade_decisions WHERE created_at > $1
            ORDER BY created_at DESC LIMIT 5
            """,
            cutoff,
        )
        print("\nlast 5:")
        for r in rows:
            print(f"  {r['created_at']}  {r['profile_id'][:8]}  {r['symbol']}  {r['outcome']}")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
