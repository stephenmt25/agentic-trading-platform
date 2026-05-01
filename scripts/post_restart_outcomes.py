"""Outcome distribution for the demo profile since the most recent restart.

Reads .praxis_logs/restart4.out for the latest restart timestamp, or falls back
to the last 5 minutes if the log isn't there.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg

PROFILE_ID = "c557fcdc-2bc2-4ef3-8004-102cd71859c0"


def url() -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith("PRAXIS_DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace(
                "postgresql+asyncpg://", "postgresql://"
            )


def restart_ts() -> datetime:
    p = Path(".praxis_logs/restart4.out")
    if p.exists():
        return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return datetime.now(timezone.utc) - timedelta(minutes=10)


async def main() -> None:
    cutoff = restart_ts()
    print(f"reporting on decisions since {cutoff.isoformat()}")
    c = await asyncpg.connect(url())
    try:
        n = await c.fetchval(
            "SELECT COUNT(*) FROM trade_decisions WHERE profile_id = $1::uuid AND created_at > $2",
            PROFILE_ID, cutoff,
        )
        print(f"total fresh decisions: {n}")
        if n == 0:
            print("(no decisions yet — wait a couple minutes)")
            return
        rows = await c.fetch(
            """
            SELECT outcome, COUNT(*) AS n FROM trade_decisions
            WHERE profile_id = $1::uuid AND created_at > $2
            GROUP BY outcome ORDER BY n DESC
            """,
            PROFILE_ID, cutoff,
        )
        for r in rows:
            print(f"  {r['outcome']:<22} {r['n']:>4}  ({100*r['n']/n:.1f}%)")

        n_o = await c.fetchval(
            "SELECT COUNT(*) FROM orders WHERE profile_id = $1::uuid AND created_at > $2",
            PROFILE_ID, cutoff,
        )
        n_p = await c.fetchval(
            "SELECT COUNT(*) FROM positions WHERE profile_id = $1::uuid AND opened_at > $2",
            PROFILE_ID, cutoff,
        )
        print(f"\nfresh orders: {n_o}, fresh positions: {n_p}")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
