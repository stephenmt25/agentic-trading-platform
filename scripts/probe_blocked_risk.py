"""Print the specific block reason cited on recent BLOCKED_RISK decisions
plus the per-profile open-position cost basis."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from libs.config import settings
import asyncpg


async def main() -> int:
    db = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    c = await asyncpg.connect(db)
    try:
        print("=== Recent BLOCKED_RISK decisions — specific reasons ===")
        rows = await c.fetch(
            """SELECT created_at, symbol, profile_id::text AS pid, gates::text AS gates_json
               FROM trade_decisions
               WHERE outcome = 'BLOCKED_RISK' AND created_at > NOW() - INTERVAL '6 hours'
               ORDER BY created_at DESC LIMIT 8"""
        )
        for r in rows:
            gates = json.loads(r["gates_json"]) if r["gates_json"] else {}
            reason = gates.get("risk", {}).get("reason") or gates.get("risk_gate", {}).get("reason") or "?"
            print(f"  {r['created_at'].strftime('%m-%d %H:%M:%S')}  {r['symbol']:<10}  prof={r['pid'][:8]}  reason={reason}")

        print("\n=== Open positions per profile — cost basis vs notional ===")
        rows = await c.fetch(
            """SELECT profile_id::text AS pid, COUNT(*) AS n, SUM(quantity * entry_price) AS cb
               FROM positions WHERE status='OPEN' GROUP BY profile_id"""
        )
        for r in rows:
            cb = float(r["cb"]) if r["cb"] else 0.0
            print(f"  prof={r['pid'][:8]}  open={r['n']}  cost_basis=${cb:.2f}  ($10k notional → {cb/10000*100:.1f}%)")

        print("\n=== Most recent APPROVED in last 24h ===")
        rows = await c.fetch(
            """SELECT created_at, symbol, profile_id::text AS pid
               FROM trade_decisions WHERE outcome = 'APPROVED' AND created_at > NOW() - INTERVAL '24 hours'
               ORDER BY created_at DESC LIMIT 5"""
        )
        for r in rows:
            print(f"  {r['created_at']}  {r['symbol']}  prof={r['pid'][:8]}")
        if not rows:
            print("  (none)")
    finally:
        await c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
