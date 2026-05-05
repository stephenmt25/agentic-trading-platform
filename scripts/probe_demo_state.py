"""Why aren't decisions landing for the demo profile?

Reads:
- profile is_active flag
- live indicator state for ETH/USDT (does the rule match?)
- any other active profiles competing
"""
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


async def main() -> None:
    c = await asyncpg.connect(url())
    try:
        prof = await c.fetchrow(
            "SELECT name, is_active, deleted_at, strategy_rules::text FROM trading_profiles WHERE profile_id = $1::uuid",
            PROFILE_ID,
        )
        print("=== demo profile ===")
        for k, v in dict(prof).items():
            print(f"  {k}: {v}")

        print("\n=== all active non-deleted profiles ===")
        rows = await c.fetch(
            "SELECT profile_id::text, name, is_active FROM trading_profiles WHERE deleted_at IS NULL ORDER BY created_at"
        )
        for r in rows:
            print(f"  {r['profile_id'][:8]}  is_active={r['is_active']}  {r['name']}")

        print("\n=== latest indicators on each symbol from trade_decisions (any profile) ===")
        rows = await c.fetch(
            """
            SELECT DISTINCT ON (symbol)
              symbol, created_at, indicators::text AS ind
            FROM trade_decisions
            ORDER BY symbol, created_at DESC
            """
        )
        for r in rows:
            ind = r["ind"][:240] if r["ind"] else "(empty)"
            print(f"  {r['symbol']}  @ {r['created_at']}")
            print(f"    {ind}")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
