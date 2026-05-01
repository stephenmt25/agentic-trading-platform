"""Pull the trigger_reason from the most recent BLOCKED_HITL decision so we
can confirm the new size_pct math is showing up live."""
import asyncio
import json
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
        rows = await c.fetch(
            """
            SELECT created_at, symbol, outcome, gates::text AS gates_text
            FROM trade_decisions
            WHERE profile_id = $1::uuid
              AND outcome = 'BLOCKED_HITL'
            ORDER BY created_at DESC LIMIT 5
            """,
            PROFILE_ID,
        )
        if not rows:
            print("(no BLOCKED_HITL decisions found)")
            return
        for r in rows:
            try:
                gates = json.loads(r["gates_text"]) if r["gates_text"] else {}
            except Exception:
                gates = {}
            hitl = gates.get("hitl_gate") or gates.get("hitl") or {}
            reason = hitl.get("reason") if isinstance(hitl, dict) else None
            print(f"{r['created_at']}  {r['symbol']}")
            if reason:
                print(f"  hitl reason: {reason}")
            else:
                print(f"  gates payload (raw): {r['gates_text'][:400] if r['gates_text'] else '(empty)'}")
            print()
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(main())
