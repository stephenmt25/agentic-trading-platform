import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from libs.config import settings
import asyncpg


async def main() -> int:
    db = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    c = await asyncpg.connect(db)
    try:
        rows = await c.fetch(
            """SELECT created_at, symbol, outcome, profile_id::text AS pid
               FROM trade_decisions
               WHERE created_at > NOW() - INTERVAL '10 minutes'
                   AND (shadow IS NULL OR shadow = FALSE)
               ORDER BY created_at DESC LIMIT 12"""
        )
        print(f"Decisions in last 10 min: {len(rows)}")
        for r in rows:
            print(f"  {r['created_at'].strftime('%H:%M:%S')}  prof={r['pid'][:8]}  {r['symbol']:<10}  {r['outcome']}")
    finally:
        await c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
