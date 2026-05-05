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
            print(f"  first trade outcome={t['outcome']}  pnl={t['realized_pnl']}  reason={t['close_reason']}")
            ag = t.get("decision_agents")
            gates = t.get("decision_gates")
            inds = t.get("decision_indicators")
            regime = t.get("decision_regime")
            print(f"  decision_event_id: {t.get('decision_event_id')}")
            print(f"  decision_agents: {type(ag).__name__}  keys={list(ag.keys()) if isinstance(ag, dict) else None}")
            print(f"  decision_gates: {type(gates).__name__}  keys={list(gates.keys()) if isinstance(gates, dict) else None}")
            print(f"  decision_indicators: {type(inds).__name__}  keys={list(inds.keys()) if isinstance(inds, dict) else None}")
            print(f"  decision_regime: {regime}")
            print(f"  sample agent attribution:")
            if isinstance(ag, dict):
                for a in ("ta", "sentiment", "debate"):
                    print(f"    {a}: {ag.get(a)}")
                print(f"    confidence_before={ag.get('confidence_before')}  confidence_after={ag.get('confidence_after')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
