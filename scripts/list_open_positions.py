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
            """SELECT position_id::text, profile_id::text AS pid, symbol, side,
                      quantity, entry_price, opened_at, decision_event_id::text
               FROM positions WHERE status = 'OPEN' ORDER BY opened_at DESC LIMIT 30"""
        )
        print(f"Open positions: {len(rows)}")
        for r in rows:
            cb = float(r['quantity']) * float(r['entry_price'])
            print(
                f"  {r['opened_at']}  prof={r['pid'][:8]}  {r['symbol']:<10}  "
                f"{r['side']}  qty={float(r['quantity']):.6f}  "
                f"entry=${float(r['entry_price']):.2f}  cost=${cb:.2f}  "
                f"decision={r['decision_event_id']}"
            )
    finally:
        await c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
