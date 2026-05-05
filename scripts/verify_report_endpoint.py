"""Smoke test for POST /paper-trading/reports/generate.

Mints a JWT, hits the endpoint for today's UTC date, then for an explicit
historical date to confirm both paths return well-formed responses.
"""
from __future__ import annotations

import asyncio
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


async def post(c: httpx.AsyncClient, headers: dict, date: str) -> None:
    print(f"=== POST /paper-trading/reports/generate  date={date} ===")
    r = await c.post(f"{API}/paper-trading/reports/generate", headers=headers, json={"date": date})
    print(f"  HTTP {r.status_code}")
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    if r.status_code == 200:
        print(f"  wrote: {body.get('wrote')}")
        print(f"  report: {body.get('report')}")
    else:
        print(f"  body: {body}")


async def main() -> int:
    uid = await first_user_id()
    token = mint(settings.SECRET_KEY, uid)
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(timezone.utc).date().isoformat()
    earlier = (datetime.now(timezone.utc).date() - timedelta(days=2)).isoformat()
    future = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()

    async with httpx.AsyncClient(timeout=30.0) as c:
        await post(c, headers, today)
        print()
        await post(c, headers, earlier)
        print()
        await post(c, headers, future)
        print()
        # Validation error test
        print("=== POST with malformed date ===")
        r = await c.post(f"{API}/paper-trading/reports/generate", headers=headers, json={"date": "not-a-date"})
        print(f"  HTTP {r.status_code}  body: {r.text[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
