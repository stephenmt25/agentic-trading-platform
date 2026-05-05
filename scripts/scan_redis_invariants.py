"""One-shot Redis schema invariant scan against the live system.

Useful for operators to verify the rails are clean without booting
services/logger. The same scan runs in services/logger every
REDIS_INVARIANT_INTERVAL_S seconds in production.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.config import settings  # noqa: E402
from libs.storage import RedisClient  # noqa: E402
from libs.observability.redis_invariants import scan  # noqa: E402


async def main() -> int:
    r = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    violations = await scan(r)
    if not violations:
        print("redis_invariants: 0 violations — schema-clean")
        return 0
    print(f"redis_invariants: {len(violations)} violations")
    for v in violations:
        print(f"  [{v.severity}] {v.key}")
        print(f"    pattern: {v.pattern}")
        print(f"    expected: {v.expected}")
        print(f"    actual:   {v.actual}")
    # Exit 1 so this can gate CI / operator scripts.
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
