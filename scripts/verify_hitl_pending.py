"""Hit GET /hitl/pending and report what the Approvals panel will see at first paint."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import asyncpg
import jwt


def env(key: str) -> str:
    for line in Path(".env").read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"missing {key}")


async def first_user_id() -> str:
    db = env("PRAXIS_DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
    c = await asyncpg.connect(db)
    try:
        return await c.fetchval("SELECT user_id::text FROM users LIMIT 1")
    finally:
        await c.close()


def main() -> None:
    token = jwt.encode(
        {"sub": asyncio.run(first_user_id()),
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        env("PRAXIS_SECRET_KEY"), algorithm="HS256",
    )
    req = Request("http://localhost:8000/hitl/pending",
                  headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=5) as r:
            print(f"HTTP {r.status}")
            data = json.loads(r.read().decode())
            print(f"queue size: {len(data)}")
            for i, item in enumerate(data, 1):
                print(f"\n[{i}] event_id={item.get('event_id')}")
                print(f"    symbol={item.get('symbol')} side={item.get('side')}")
                print(f"    price={item.get('price')}  qty={item.get('quantity')}")
                print(f"    confidence={item.get('confidence')}")
                print(f"    trigger={item.get('trigger_reason')}")
                ts = item.get("timestamp_us", 0) // 1000
                if ts:
                    print(f"    when: {datetime.fromtimestamp(ts/1000, tz=timezone.utc)}")
    except HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}")


if __name__ == "__main__":
    main()
