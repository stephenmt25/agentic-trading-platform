"""Are *any* decisions landing across all profiles in the last 30 min?"""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import asyncpg


def url() -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace(
                "postgresql+asyncpg://", "postgresql://"
            )


async def main() -> None:
    c = await asyncpg.connect(url())
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        n = await c.fetchval(
            "SELECT COUNT(*) FROM trade_decisions WHERE created_at > $1", cutoff
        )
        print(f"decisions across ALL profiles in last 30 min: {n}")

        rows = await c.fetch(
            """
            SELECT created_at, profile_id::text, symbol, outcome
            FROM trade_decisions
            ORDER BY created_at DESC LIMIT 5
            """
        )
        print("\nlast 5 decisions (any profile):")
        for r in rows:
            print(f"  {r['created_at']}  {r['profile_id'][:8]}  {r['symbol']}  {r['outcome']}")

        # Open position count + total cost basis
        rows = await c.fetch(
            """
            SELECT profile_id::text, COUNT(*) AS n, SUM(quantity * entry_price) AS cost_basis_total
            FROM positions
            WHERE closed_at IS NULL
            GROUP BY profile_id
            """
        )
        print("\nopen positions by profile:")
        for r in rows:
            print(f"  {r['profile_id'][:8]}  n={r['n']}  cost_basis=${r['cost_basis_total']:.2f}")

        # Compare to notional ($10k default)
        print("\n(notional = $10000 by default per profile; if cost_basis_total >= $10000, risk gate exposure_at_notional fires)")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
