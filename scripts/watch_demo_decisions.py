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
        n_total = await c.fetchval(
            "SELECT COUNT(*) FROM trade_decisions WHERE profile_id = $1::uuid", PROFILE_ID
        )
        print(f"total decisions for demo profile: {n_total}")

        if n_total > 0:
            rows = await c.fetch(
                """
                SELECT outcome, COUNT(*) AS n FROM trade_decisions
                WHERE profile_id = $1::uuid GROUP BY outcome ORDER BY n DESC
                """,
                PROFILE_ID,
            )
            print("by outcome:")
            for r in rows:
                print(f"  {r['outcome']:<25} {r['n']}")

            n_orders = await c.fetchval(
                "SELECT COUNT(*) FROM orders WHERE profile_id = $1::uuid", PROFILE_ID
            )
            n_positions = await c.fetchval(
                "SELECT COUNT(*) FROM positions WHERE profile_id = $1::uuid", PROFILE_ID
            )
            print(f"orders: {n_orders}, positions: {n_positions}")

            latest = await c.fetch(
                """
                SELECT created_at, symbol, outcome FROM trade_decisions
                WHERE profile_id = $1::uuid ORDER BY created_at DESC LIMIT 3
                """,
                PROFILE_ID,
            )
            print("most recent:")
            for r in latest:
                print(f"  {r['created_at']}  {r['symbol']}  {r['outcome']}")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
