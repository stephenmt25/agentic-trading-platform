"""One-shot live-state probe.

Reads SECRET_KEY + DATABASE_URL from .env, finds an existing user_id,
mints a 1-hour JWT, and queries the API gateway for trading state.
Prints findings to stdout; the token itself is never printed.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import asyncio

import asyncpg
import jwt

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
API = "http://localhost:8000"


def load_env(path: Path) -> dict:
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


async def _first_user(database_url: str):
    # asyncpg doesn't accept the +asyncpg/+psycopg suffixes some libs add
    url = database_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        return await conn.fetchrow(
            "SELECT user_id, email, display_name, provider FROM users ORDER BY created_at LIMIT 1"
        )
    finally:
        await conn.close()


def first_user_id(database_url: str) -> str | None:
    row = asyncio.run(_first_user(database_url))
    if not row:
        return None
    print(f"  user: {row['display_name']} <{row['email']}> ({row['provider']})  id={row['user_id']}")
    return str(row["user_id"])


def mint(secret: str, sub: str) -> str:
    payload = {"sub": sub, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return jwt.encode(payload, secret, algorithm="HS256")


def get(path: str, token: str) -> tuple[int, str]:
    req = Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=4) as r:
            return r.status, r.read().decode()
    except HTTPError as e:
        return e.code, e.read().decode()
    except URLError as e:
        return 0, str(e)


def show(label: str, path: str, token: str, max_chars: int = 1200) -> None:
    code, body = get(path, token)
    print(f"\n=== {label}  [{path}]  HTTP {code} ===")
    try:
        parsed = json.loads(body)
        body = json.dumps(parsed, indent=2, default=str)
    except Exception:
        pass
    print(body[:max_chars] + ("\n... [truncated]" if len(body) > max_chars else ""))


def main() -> int:
    env = load_env(ENV_PATH)
    secret = env.get("PRAXIS_SECRET_KEY")
    db_url = env.get("PRAXIS_DATABASE_URL")
    if not secret or not db_url:
        print("missing PRAXIS_SECRET_KEY or PRAXIS_DATABASE_URL in .env", file=sys.stderr)
        return 2

    print("[1/3] Looking up a user...")
    uid = first_user_id(db_url)
    if not uid:
        print("  no users found — falling back to synthetic uuid")
        uid = "00000000-0000-0000-0000-000000000001"

    print("[2/3] Minting JWT...")
    token = mint(secret, uid)

    print("[3/3] Querying API gateway...")
    show("AUTH /me",          "/auth/me",                       token)
    show("PAPER MODE",        "/paper-trading/mode",            token)
    show("PAPER STATUS",      "/paper-trading/status",          token)
    show("KILL SWITCH",       "/commands/kill-switch",          token)
    show("PROFILES",          "/profiles/",                     token)
    show("AGENTS STATUS",     "/agents/status",                 token)
    show("POSITIONS",         "/positions/",                    token)
    show("PNL SUMMARY",       "/pnl/summary",                   token)
    show("PNL HISTORY",       "/pnl/history",                   token)
    show("ORDERS",            "/orders/",                       token)
    show("RECENT DECISIONS",  "/paper-trading/decisions",       token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
