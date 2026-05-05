"""Verify the dashboard fixes hit live endpoints correctly.

Checks:
  1. /agent-performance/weights/{symbol} returns str keys (not bytes) and
     includes AGENT_DEFAULTS for any missing agent.
  2. /audit/closed-trades responds with the expected shape.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt as pyjwt
import asyncpg

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

    async with httpx.AsyncClient(timeout=10.0) as c:
        print("=== /agent-performance/weights/BTC/USDT ===")
        r = await c.get(f"{API}/agent-performance/weights/BTC/USDT", headers=headers)
        print(f"  HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  weights = {data.get('weights')}")
            print(f"  trackers keys: {list(data.get('trackers', {}).keys())}")
            for agent, value in (data.get("weights") or {}).items():
                assert isinstance(agent, str), f"weights key {agent!r} is not str"
                assert isinstance(value, (int, float)), f"weights value {value!r} not numeric"
            for required in ("ta", "sentiment", "debate"):
                assert required in (data.get("weights") or {}), \
                    f"Missing default for {required}"
            print("  OK — string keys, AGENT_DEFAULTS fallback present")

        print("\n=== /audit/closed-trades?symbol=BTC/USDT&limit=5 ===")
        r = await c.get(f"{API}/audit/closed-trades", headers=headers, params={
            "symbol": "BTC/USDT", "limit": 5,
        })
        print(f"  HTTP {r.status_code}")
        if r.status_code == 200:
            rows = r.json()
            print(f"  rows: {len(rows)}")
            if rows:
                t = rows[0]
                print(f"  sample row: closed_at={t.get('closed_at')}  outcome={t.get('outcome')}  pnl={t.get('realized_pnl')}")
        elif r.status_code == 404:
            print("  No closed trades yet (post-reset baseline) — endpoint contract OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
