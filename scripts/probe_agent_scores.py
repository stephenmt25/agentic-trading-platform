"""One-shot probe: read live agent score keys for the open registry investigation.

Used by docs/EXECUTION-REPORT-CONTINUOUS-CHECKING (sentiment+debate score=0.0).
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.config import settings  # noqa: E402
from libs.storage import RedisClient  # noqa: E402


async def main() -> int:
    r = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    print("=== live agent scores ===")
    for sym in settings.TRADING_SYMBOLS:
        for kind in ("sentiment", "debate", "ta_score"):
            v = await r.get(f"agent:{kind}:{sym}")
            if v is None:
                print(f"  agent:{kind}:{sym}  MISSING")
                continue
            if isinstance(v, bytes):
                v = v.decode()
            try:
                obj = json.loads(v)
                summary = {k: obj.get(k) for k in ("score", "confidence", "source")}
                print(f"  agent:{kind}:{sym}  {summary}")
            except Exception:
                print(f"  agent:{kind}:{sym}  raw={v[:200]}")
        print()

    print("=== relevant settings ===")
    print(f"  LLM_BACKEND:         {getattr(settings, 'LLM_BACKEND', None)!r}")
    print(f"  LLM_API_KEY set:     {bool(getattr(settings, 'LLM_API_KEY', ''))}")
    print(f"  SLM_INFERENCE_URL:   {getattr(settings, 'SLM_INFERENCE_URL', None)!r}")
    print(f"  NEWS_API_KEY set:    {bool(getattr(settings, 'NEWS_API_KEY', ''))}")
    print(f"  TRADING_SYMBOLS:     {getattr(settings, 'TRADING_SYMBOLS', None)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
