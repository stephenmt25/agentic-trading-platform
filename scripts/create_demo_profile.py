"""Create a 'Demo · Pullback Long' profile that fires often enough to populate
the live UI for the partner demo, but is a real strategy concept (buy the dip
in an uptrend), not a tautology.

Rule: long when RSI < 50 AND MACD histogram > 0.
- RSI < 50: price is in a pullback (below midline)
- MACD histogram > 0: but momentum hasn't flipped bearish yet
Together: buy modest dips while uptrend intact. Will match several times per
hour on BTC/USDT in normal markets. Most matches will still get filtered by
the abstention gate (~80%) and circuit breaker (~17%) — that's the point;
the Decision Feed fills up showing the engine working.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import asyncpg
import jwt

API = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"


def env(key: str) -> str:
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"missing {key} in .env")


async def _first_user(db_url: str) -> str:
    url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    c = await asyncpg.connect(url)
    try:
        row = await c.fetchrow("SELECT user_id::text FROM users ORDER BY created_at LIMIT 1")
        if not row:
            raise SystemExit("no users in DB")
        return row["user_id"]
    finally:
        await c.close()


def mint(secret: str, sub: str) -> str:
    payload = {"sub": sub, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return jwt.encode(payload, secret, algorithm="HS256")


def post_json(path: str, token: str, body: dict) -> tuple[int, str]:
    data = json.dumps(body).encode()
    req = Request(
        f"{API}{path}",
        data=data,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except HTTPError as e:
        return e.code, e.read().decode()


def main() -> int:
    secret = env("PRAXIS_SECRET_KEY")
    db_url = env("PRAXIS_DATABASE_URL")
    uid = asyncio.run(_first_user(db_url))
    token = mint(secret, uid)

    body = {
        "name": "Demo · Pullback Long",
        "rules_json": {
            "direction": "long",
            "match_mode": "all",
            "confidence": 0.65,
            "signals": [
                {"indicator": "rsi", "comparison": "below", "threshold": 50.0},
                {"indicator": "macd_histogram", "comparison": "above", "threshold": 0.0},
            ],
        },
        "risk_limits": {},
        "allocation_pct": 1.0,
    }

    code, resp = post_json("/profiles/", token, body)
    print(f"POST /profiles/  HTTP {code}")
    try:
        parsed = json.loads(resp)
        print(json.dumps(parsed, indent=2, default=str))
        if code == 201:
            pid = parsed.get("id") or parsed.get("profile", {}).get("profile_id")
            print(f"\nDemo profile created: {pid}")
            print("It is active by default. Watch /trade for live decisions.")
            return 0
    except Exception:
        print(resp)
    return 1 if code >= 300 else 0


if __name__ == "__main__":
    raise SystemExit(main())
