"""Clean baseline reset for honest paper-trading restart.

Background: today's session landed five rails fixes that change the *interpretation*
of every prior closed trade in the EWMA learning loop:

  - CRISIS abstention restored (a08d576) — trades during CRISIS regimes
    should not have happened
  - Mainnet vs testnet volume contamination (commit pre-2026-05-05)
  - Notional unit alignment ($10k vs $100k mismatch)
  - Sentiment + debate fake LLM votes filtered out (today's commit 4b58e52)
  - Bytes-vs-string Redis decode bug in analyst tracker (acb25ae)

The Redis EWMA state (agent:tracker:{symbol}:{agent} + agent:weights:{symbol})
integrates over all those poisoned entries. Going forward we want a
clean reading.

This script:
  1. Archives agent:closed:{symbol} → agent:closed:archive:<ts>:{symbol}
     so the history is preserved for diagnostics.
  2. Same for agent:outcomes:{symbol}.
  3. Deletes agent:tracker:{symbol}:* so EWMA restarts from defaults
     (AGENT_DEFAULTS in libs/core/agent_registry.py).
  4. Deletes agent:weights:{symbol} so the next recompute writes
     fresh weights from defaults.
  5. Deletes sentiment:{symbol}:latest (the cache that was poisoned by
     llm_error fallbacks pre-fix).
  6. Deletes agent:sentiment:{symbol} and agent:debate:{symbol} so the
     next sentiment/debate cycle writes fresh state — failing services
     will now correctly leave these absent rather than stuck-on-cache.

NOT touched:
  - closed_trades and pnl_snapshots Postgres tables — those are historical
    audit and should stay. The frontend's "all-time PnL" reads from those.
  - agent_weight_history Postgres table — same reason; historical record
    of what the system actually computed.

Idempotent: safe to run multiple times. Archives append a unix timestamp.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.config import settings  # noqa: E402
from libs.storage import RedisClient  # noqa: E402


def _decode(v):
    return v.decode() if isinstance(v, bytes) else v


async def audit(redis, label: str) -> None:
    print(f"=== {label} ===")
    for sym in settings.TRADING_SYMBOLS:
        for k in (f"agent:closed:{sym}", f"agent:outcomes:{sym}"):
            t = _decode(await redis.type(k))
            ln = await redis.xlen(k) if t == "stream" else None
            print(f"  {k}  type={t}  len={ln}")
        keys = await redis.keys(f"agent:tracker:{sym}:*")
        print(f"  agent:tracker:{sym}:*  count={len(keys)}")
        for k in (
            f"agent:weights:{sym}",
            f"sentiment:{sym}:latest",
            f"agent:sentiment:{sym}",
            f"agent:debate:{sym}",
        ):
            t = _decode(await redis.type(k))
            print(f"  {k}  type={t}")
        print()


async def reset(redis, archive_ts: int) -> None:
    print(f"=== RESET (archive_ts={archive_ts}) ===")
    for sym in settings.TRADING_SYMBOLS:
        # Archive streams — RENAME is atomic and only succeeds if source exists.
        for src_key in (f"agent:closed:{sym}", f"agent:outcomes:{sym}"):
            archive_key = src_key.replace("agent:", f"agent:archive:{archive_ts}:", 1)
            try:
                await redis.rename(src_key, archive_key)
                print(f"  RENAME  {src_key}  ->  {archive_key}")
            except Exception as e:
                # Source key missing — skip silently (idempotent).
                if "no such key" in str(e).lower():
                    print(f"  RENAME  {src_key}  (absent — skipped)")
                else:
                    raise

        # Drop EWMA aggregates so the next recompute starts from AGENT_DEFAULTS.
        tracker_keys = await redis.keys(f"agent:tracker:{sym}:*")
        for k in tracker_keys:
            kk = _decode(k)
            await redis.delete(kk)
            print(f"  DEL  {kk}")

        for k in (
            f"agent:weights:{sym}",
            f"sentiment:{sym}:latest",          # poisoned cache from llm_error
            f"agent:sentiment:{sym}",           # force fresh write
            f"agent:debate:{sym}",              # force fresh write
        ):
            existed = await redis.delete(k)
            if existed:
                print(f"  DEL  {k}")
            else:
                print(f"  DEL  {k}  (absent — skipped)")
        print()


async def main(do_reset: bool) -> int:
    r = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    await audit(r, "BEFORE")

    if not do_reset:
        print("(dry run — pass --apply to actually reset)")
        return 0

    archive_ts = int(time.time())
    await reset(r, archive_ts)
    await audit(r, "AFTER")
    print(f"\nDone. Archive timestamp: {archive_ts}")
    print("Restart services via `bash run_all.sh --local-frontend` so the")
    print("analyst recompute loop picks up the empty trackers and writes")
    print("AGENT_DEFAULTS as the fresh baseline.")
    return 0


if __name__ == "__main__":
    do_reset = "--apply" in sys.argv
    raise SystemExit(asyncio.run(main(do_reset)))
