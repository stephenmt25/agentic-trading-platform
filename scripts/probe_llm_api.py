"""One-shot probe of the Anthropic API to diagnose the smoke-test failure."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from libs.config import settings  # noqa: E402


async def go() -> None:
    print("KEY len:", len(settings.LLM_API_KEY or ""))
    print("KEY prefix:", (settings.LLM_API_KEY or "")[:8])
    async with httpx.AsyncClient() as c:
        res = await c.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.LLM_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Respond with just OK"}],
            },
            timeout=15.0,
        )
        print("STATUS:", res.status_code)
        print("BODY:", res.text)


if __name__ == "__main__":
    asyncio.run(go())
