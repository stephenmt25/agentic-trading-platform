"""Regenerate today's daily report and print the resulting summary +
trade count, end-to-end against the live API."""
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


async def main() -> int:
    uid = await first_user_id()
    token = mint(settings.SECRET_KEY, uid)
    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(timezone.utc).date().isoformat()

    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(f"{API}/paper-trading/reports/generate", headers=headers, json={"date": today})
        print(f"POST generate -> HTTP {r.status_code}")
        body = r.json()
        print(f"  wrote: {body.get('wrote')}")
        print(f"  summary: {body.get('report')}")

        r = await c.get(f"{API}/paper-trading/reports/{today}/detail", headers=headers)
        body = r.json()
        print(f"GET detail   -> HTTP {r.status_code}, trades.length={len(body.get('trades', []))}, summary.total_trades={body.get('summary', {}).get('total_trades')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
