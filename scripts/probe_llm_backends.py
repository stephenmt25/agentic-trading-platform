"""Independent probe of both LLM backends: local Phi-3 SLM and cloud Anthropic.

Used to verify whether the LLM is actually failing or whether the failure
is upstream (cache poisoning, request shape, etc.).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.config import settings  # noqa: E402


async def test_slm() -> None:
    print("=== Local SLM (Phi-3 via /v1/completions) ===")
    url = f"{settings.SLM_INFERENCE_URL}/v1/completions"
    payload = {
        "prompt": (
            "You MUST respond with ONLY raw valid JSON.\n"
            'Respond with exactly: {"score": <-1.0..1.0>, "confidence": <0.0..1.0>}\n'
            "Sentiment for BTC: bullish.\n"
        ),
        "max_tokens": 60,
        "temperature": 0.1,
    }
    async with httpx.AsyncClient() as c:
        try:
            r = await c.post(url, json=payload, timeout=180.0)
            print(f"  POST {url}  ->  HTTP {r.status_code}")
            if r.status_code == 200:
                text = r.json().get("text", "")
                print(f"  text: {text!r}")
            else:
                print(f"  body: {r.text[:200]}")
        except Exception as e:
            print(f"  EXCEPTION: {type(e).__name__}: {e}")


async def test_anthropic() -> None:
    print("\n=== Cloud Anthropic API ===")
    key = settings.LLM_API_KEY
    if not key:
        print("  LLM_API_KEY not set — skipping")
        return
    print(f"  key length: {len(key)}  (first 8: {key[:8]}…)")
    async with httpx.AsyncClient() as c:
        try:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Reply with the word OK and nothing else."}],
                },
                timeout=15.0,
            )
            print(f"  POST  ->  HTTP {r.status_code}")
            if r.status_code == 200:
                d = r.json()
                print(f"  reply: {d['content'][0]['text']!r}")
            else:
                print(f"  body: {r.text[:300]}")
        except Exception as e:
            print(f"  EXCEPTION: {type(e).__name__}: {e}")


async def main() -> int:
    await test_slm()
    await test_anthropic()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
