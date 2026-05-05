"""Smoke test for GET /paper-trading/reports/{date}/detail."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import httpx
import jwt as pyjwt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.config import settings  # noqa: E402

API = "http://localhost:8000"


async def first_user_id() -> str:
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    try:
        row = await conn.fetchrow("SELECT user_id FROM users ORDER BY created_at LIMIT 1")
        return str(row["user_id"]) if row else "00000000-0000-0000-0000-000000000001"
    finally:
        await conn.close()


def mint(secret: str, sub: str) -> str:
    payload = {"sub": sub, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return pyjwt.encode(payload, secret, algorithm="HS256")


async def main() -> int:
    uid = await first_user_id()
    token = mint(settings.SECRET_KEY, uid)
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(timezone.utc).date().isoformat()

    async with httpx.AsyncClient(timeout=30.0) as c:
        print(f"=== GET /paper-trading/reports/{today}/detail ===")
        r = await c.get(f"{API}/paper-trading/reports/{today}/detail", headers=headers)
        print(f"  HTTP {r.status_code}")
        if r.status_code != 200:
            print(f"  body: {r.text[:300]}")
            return 1
        d = r.json()
        print(f"  report_date: {d.get('report_date')}")
        print(f"  summary: {d.get('summary')}")
        trades = d.get("trades", [])
        print(f"  trades: {len(trades)}")
        if trades:
            t = trades[0]
            print(f"  first trade keys: {sorted(t.keys())}")
            print(f"  outcome={t['outcome']}  pnl={t['realized_pnl']}  reason={t['close_reason']}")
            print(f"  order: {t.get('order')}")
            pr = t.get("profile_rules") or {}
            print(f"  profile_rules keys: {list(pr.keys()) if isinstance(pr, dict) else None}")
            if isinstance(pr, dict):
                print(f"    direction={pr.get('direction')}  logic={pr.get('logic')}  base_conf={pr.get('base_confidence')}")
                conds = pr.get("conditions") or []
                print(f"    conditions: {len(conds)} entries")
        blocked = d.get("blocked", {})
        print(f"  blocked.total: {blocked.get('total')}")
        print(f"  blocked.counts_by_outcome: {blocked.get('counts_by_outcome')}")
        recent = blocked.get("recent", [])
        print(f"  blocked.recent: {len(recent)} rows (showing first):")
        if recent:
            b = recent[0]
            print(f"    {b['created_at'][11:19] if b['created_at'] else '—'}  {b['symbol']}  {b['outcome']}  gates_keys={list(b['gates'].keys()) if b.get('gates') else None}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
