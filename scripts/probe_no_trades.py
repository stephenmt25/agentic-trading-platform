"""Why has no new trade landed since the 17 closes earlier today?

Walks the decision pipeline state to localize the stall:
  - decision rate per hour (is hot_path even ticking?)
  - outcome breakdown per recent hour (where in the pipeline are we losing them?)
  - per-blocking-gate reasons over the recent window
  - open positions (still saturated?)
  - active profiles + the kill switch
  - latest agent scores (sentiment / debate freshness)
"""
import asyncio
import json
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.config import settings  # noqa: E402
from libs.storage import RedisClient  # noqa: E402


async def main() -> int:
    db = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db)
    try:
        print("=== decisions over last 6 hours, hourly ===")
        rows = await conn.fetch(
            """
            SELECT
              date_trunc('hour', created_at) AS hour,
              COUNT(*) FILTER (WHERE outcome = 'APPROVED')                  AS approved,
              COUNT(*) FILTER (WHERE outcome != 'APPROVED' AND outcome != 'SKIPPED') AS blocked,
              COUNT(*)                                                      AS total
            FROM trade_decisions
            WHERE created_at > NOW() - INTERVAL '6 hours'
              AND (shadow IS NULL OR shadow = FALSE)
            GROUP BY 1 ORDER BY 1 DESC
            """
        )
        for r in rows:
            print(f"  {r['hour']}  approved={r['approved']:>3}  blocked={r['blocked']:>4}  total={r['total']:>4}")

        print("\n=== blocking outcomes — last 2 hours ===")
        rows = await conn.fetch(
            """
            SELECT outcome, COUNT(*) AS n
            FROM trade_decisions
            WHERE created_at > NOW() - INTERVAL '2 hours'
              AND outcome != 'APPROVED'
              AND (shadow IS NULL OR shadow = FALSE)
            GROUP BY outcome ORDER BY n DESC
            """
        )
        for r in rows:
            print(f"  {r['outcome']:<35}  {r['n']}")
        if not rows:
            print("  (no blocked decisions in last 2 hours)")

        print("\n=== blocking gate reasons — last 2 hours ===")
        # Drill into the failing-gate strings inside the JSONB.
        rows = await conn.fetch(
            """
            SELECT outcome, gates::text AS gates_json
            FROM trade_decisions
            WHERE created_at > NOW() - INTERVAL '2 hours'
              AND outcome != 'APPROVED'
              AND (shadow IS NULL OR shadow = FALSE)
            """
        )
        reasons: dict[str, int] = {}
        for r in rows:
            try:
                gates = json.loads(r["gates_json"]) if r["gates_json"] else {}
            except Exception:
                continue
            for name, g in gates.items():
                if isinstance(g, dict) and g.get("passed") is False:
                    reason = g.get("reason") or name
                    key = f"{name}: {reason}"
                    reasons[key] = reasons.get(key, 0) + 1
        for k, n in sorted(reasons.items(), key=lambda x: -x[1])[:15]:
            print(f"  {n:>4}  {k}")
        if not reasons:
            print("  (no failing-gate reasons in last 2 hours)")

        print("\n=== open positions ===")
        rows = await conn.fetch(
            "SELECT profile_id::text AS pid, COUNT(*) AS n, SUM(quantity * entry_price) AS cb "
            "FROM positions WHERE status='OPEN' GROUP BY profile_id"
        )
        if not rows:
            print("  (none — notional fully free)")
        for r in rows:
            cb = float(r["cb"]) if r["cb"] else 0.0
            pct = cb / 10000.0 * 100.0
            print(f"  prof={r['pid'][:8]}  open={r['n']}  cost_basis=${cb:.2f}  ({pct:.1f}% of $10k)")

        print("\n=== latest decision per profile ===")
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (profile_id)
                profile_id::text, symbol, outcome, created_at
            FROM trade_decisions
            WHERE shadow IS NULL OR shadow = FALSE
            ORDER BY profile_id, created_at DESC
            """
        )
        for r in rows:
            print(f"  prof={r['profile_id'][:8]}  {r['symbol']}  {r['outcome']:<25}  {r['created_at']}")

        print("\n=== active profiles ===")
        rows = await conn.fetch(
            "SELECT profile_id::text, name, is_active, allocation_pct, deleted_at FROM trading_profiles "
            "WHERE deleted_at IS NULL ORDER BY created_at"
        )
        for r in rows:
            mark = "*" if r["is_active"] else " "
            print(f"  {mark} {r['profile_id'][:8]}  alloc={r['allocation_pct']}  {r['name']}")
    finally:
        await conn.close()

    print("\n=== Redis runtime flags + latest agent scores ===")
    r = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    ks = await r.get("praxis:kill_switch")
    print(f"  praxis:kill_switch = {ks}")
    print(f"  TRADING_ENABLED    = {settings.TRADING_ENABLED}")
    print(f"  PAPER_TRADING_MODE = {settings.PAPER_TRADING_MODE}")
    print(f"  LLM_BACKEND        = {settings.LLM_BACKEND}")
    for sym in settings.TRADING_SYMBOLS:
        for kind in ("ta_score", "sentiment", "debate"):
            v = await r.get(f"agent:{kind}:{sym}")
            if v is None:
                print(f"  agent:{kind}:{sym}  MISSING")
                continue
            if isinstance(v, bytes):
                v = v.decode()
            try:
                obj = json.loads(v)
                print(f"  agent:{kind}:{sym}  score={obj.get('score')}  source={obj.get('source')}")
            except Exception:
                print(f"  agent:{kind}:{sym}  raw={v[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
