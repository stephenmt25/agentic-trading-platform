import asyncio
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
        print("=== outcome distribution (all-time) ===")
        rows = await c.fetch(
            "SELECT outcome, COUNT(*) AS n FROM trade_decisions GROUP BY outcome ORDER BY n DESC"
        )
        total = sum(r["n"] for r in rows)
        for r in rows:
            print(f"  {r['outcome']:<20} {r['n']:>6}  ({100*r['n']/total:.1f}%)")

        print("\n=== outcome distribution (last 24h) ===")
        rows = await c.fetch(
            """
            SELECT outcome, COUNT(*) AS n FROM trade_decisions
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY outcome ORDER BY n DESC
            """
        )
        if not rows:
            print("  (no decisions in last 24h)")
        else:
            total = sum(r["n"] for r in rows)
            for r in rows:
                print(f"  {r['outcome']:<20} {r['n']:>6}  ({100*r['n']/total:.1f}%)")

        print("\n=== gate-block reasons (sampled from indicators jsonb if any) ===")
        sample = await c.fetchrow(
            """
            SELECT outcome, indicators::text AS ind, strategy::text AS strat, regime::text AS regime
            FROM trade_decisions
            WHERE outcome NOT IN ('APPROVED','EXECUTED')
            ORDER BY created_at DESC LIMIT 1
            """
        )
        if sample:
            print(" outcome:", sample["outcome"])
            for k in ["ind", "strat", "regime"]:
                v = sample[k] or ""
                print(f"  {k}: {v[:240]}")

        print("\n=== profile attribution of recent decisions ===")
        rows = await c.fetch(
            """
            SELECT tp.name, td.outcome, COUNT(*) AS n
            FROM trade_decisions td
            LEFT JOIN trading_profiles tp ON tp.profile_id = td.profile_id
            WHERE td.created_at > NOW() - INTERVAL '24 hours'
            GROUP BY tp.name, td.outcome
            ORDER BY n DESC LIMIT 10
            """
        )
        for r in rows:
            print(f"  {str(r['name']):<25} {r['outcome']:<20} {r['n']}")

        print("\n=== agent score history sanity ===")
        n_total = await c.fetchval("SELECT COUNT(*) FROM agent_score_history")
        n_24h = await c.fetchval(
            "SELECT COUNT(*) FROM agent_score_history WHERE created_at > NOW() - INTERVAL '24 hours'"
        )
        print(f"  total: {n_total}, last 24h: {n_24h}")
        rows = await c.fetch(
            """
            SELECT agent_name, COUNT(*) AS n FROM agent_score_history
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY agent_name ORDER BY n DESC
            """
        )
        for r in rows:
            print(f"  {r['agent_name']:<20} {r['n']}")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
