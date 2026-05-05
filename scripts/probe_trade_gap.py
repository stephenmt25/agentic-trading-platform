"""Diagnose why closed_trades has no entries after 2026-04-28.

Checks the position lifecycle from decision → order → position → close to find
where the chain stalled.
"""
from __future__ import annotations

import asyncio
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
        print("=== closed_trades — last/first dates ===")
        row = await conn.fetchrow(
            "SELECT MIN(closed_at) AS first, MAX(closed_at) AS last, COUNT(*) AS n FROM closed_trades"
        )
        print(f"  rows={row['n']}  first={row['first']}  last={row['last']}")

        print("\n=== positions — all-time + open ===")
        rows = await conn.fetch(
            "SELECT status, COUNT(*) AS n, MIN(opened_at) AS first, MAX(opened_at) AS last "
            "FROM positions GROUP BY status ORDER BY status"
        )
        for r in rows:
            print(f"  status={r['status']:<10}  n={r['n']}  first={r['first']}  last={r['last']}")

        print("\n=== open positions detail ===")
        rows = await conn.fetch(
            "SELECT position_id::text, profile_id::text, symbol, side, entry_price, quantity, "
            "       opened_at FROM positions WHERE status='OPEN' ORDER BY opened_at DESC LIMIT 10"
        )
        for r in rows:
            print(f"  {r['symbol']:<10}  {r['side']:<4}  qty={r['quantity']}  entry=${r['entry_price']}  opened={r['opened_at']}")
        if not rows:
            print("  (none)")

        print("\n=== orders — last 10 ===")
        rows = await conn.fetch(
            "SELECT order_id::text, symbol, side, quantity, status, created_at "
            "FROM orders ORDER BY created_at DESC LIMIT 10"
        )
        for r in rows:
            print(f"  {r['created_at']}  {r['symbol']:<10}  {r['side']:<4}  qty={r['quantity']}  status={r['status']}")
        if not rows:
            print("  (none)")

        print("\n=== trade_decisions — recent volume + outcomes ===")
        row = await conn.fetchrow(
            "SELECT COUNT(*) AS total, MIN(created_at) AS first, MAX(created_at) AS last "
            "FROM trade_decisions WHERE created_at > NOW() - INTERVAL '24 hours'"
        )
        print(f"  last 24h: total={row['total']}  first={row['first']}  last={row['last']}")

        rows = await conn.fetch(
            "SELECT outcome, COUNT(*) AS n FROM trade_decisions "
            "WHERE created_at > NOW() - INTERVAL '24 hours' GROUP BY outcome ORDER BY n DESC"
        )
        for r in rows:
            print(f"    {r['outcome']:<35}  n={r['n']}")

        print("\n=== active profiles ===")
        rows = await conn.fetch(
            "SELECT profile_id::text, name, is_active, allocation_pct, deleted_at FROM trading_profiles "
            "WHERE deleted_at IS NULL ORDER BY created_at"
        )
        for r in rows:
            mark = "*" if r['is_active'] else " "
            print(f"  {mark} {r['profile_id'][:8]}  alloc={r['allocation_pct']}  {r['name']}")

    finally:
        await conn.close()

    print("\n=== Redis runtime flags ===")
    r = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    ks = await r.get("praxis:kill_switch")
    print(f"  praxis:kill_switch = {ks}")
    print(f"  TRADING_ENABLED = {settings.TRADING_ENABLED}")
    print(f"  PAPER_TRADING_MODE = {settings.PAPER_TRADING_MODE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
