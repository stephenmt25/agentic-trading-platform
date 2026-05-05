import asyncio
import json
import re
import time
import httpx
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from libs.config import settings
from libs.observability import get_logger

logger = get_logger("sentiment.scorer")

_JSON_OBJECT_RE = re.compile(r'\{[^{}]*"score"\s*:\s*[-\d.]+[^{}]*"confidence"\s*:\s*[-\d.]+[^{}]*\}')


@dataclass
class SentimentResult:
    score: float       # -1.0 (bearish) to 1.0 (bullish)
    confidence: float  # 0.0 to 1.0
    source: str


# ---------------------------------------------------------------------------
# LLM Backend Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class LLMBackend(Protocol):
    async def complete(self, prompt: str, grammar: Optional[str] = None) -> Optional[str]:
        """Send a prompt to the LLM and return the response text, or None on failure.

        If grammar (GBNF) is provided, the local backend constrains output to match
        it. Cloud backends ignore grammar (Anthropic doesn't support GBNF).
        """
        ...


class CloudLLMBackend:
    """Claude API backend (original implementation)."""

    MAX_RETRIES = 2
    MIN_CALL_INTERVAL_S = 2.0

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._last_call_time: float = 0.0

    async def complete(self, prompt: str, grammar: Optional[str] = None) -> Optional[str]:
        # grammar is ignored — Anthropic API doesn't support GBNF.
        if not self._api_key:
            return None

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            elapsed = time.monotonic() - self._last_call_time
            if elapsed < self.MIN_CALL_INTERVAL_S:
                await asyncio.sleep(self.MIN_CALL_INTERVAL_S - elapsed)

            try:
                self._last_call_time = time.monotonic()
                async with httpx.AsyncClient() as client:
                    res = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": self._api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": "claude-haiku-4-5-20251001",
                            "max_tokens": 100,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                        timeout=10.0,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        return data["content"][0]["text"]
                    last_error = f"HTTP {res.status_code}"
            except Exception as e:
                last_error = str(e)

            logger.warning("Cloud LLM attempt failed", attempt=attempt + 1, error=last_error)

        return None


class LocalLLMBackend:
    """Local SLM inference service backend."""

    def __init__(self, base_url: str = None):
        self._base_url = base_url or settings.SLM_INFERENCE_URL

    async def complete(self, prompt: str, grammar: Optional[str] = None) -> Optional[str]:
        try:
            async with httpx.AsyncClient() as client:
                payload: dict = {"prompt": prompt, "max_tokens": 100, "temperature": 0.1}
                if grammar:
                    payload["grammar"] = grammar
                res = await client.post(
                    f"{self._base_url}/v1/completions",
                    json=payload,
                    timeout=180.0,
                )
                if res.status_code == 200:
                    data = res.json()
                    return data.get("text", "")
                logger.warning("Local SLM returned error", status=res.status_code)
        except Exception as e:
            logger.warning("Local SLM unreachable", error=str(e))
        return None


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------

def create_backend(llm_key: str = "") -> list[LLMBackend]:
    """Create ordered list of backends based on config. First success wins."""
    mode = settings.LLM_BACKEND  # "cloud", "local", or "auto"
    backends: list[LLMBackend] = []

    if mode == "local":
        backends.append(LocalLLMBackend())
    elif mode == "cloud":
        backends.append(CloudLLMBackend(llm_key))
    elif mode == "auto":
        # Try local first, fall back to cloud
        backends.append(LocalLLMBackend())
        backends.append(CloudLLMBackend(llm_key))
    else:
        # Default to cloud
        backends.append(CloudLLMBackend(llm_key))

    return backends


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class LLMSentimentScorer:
    """LLM-based sentiment scoring with configurable backend and fallback chain."""

    def __init__(self, llm_key: str = "", cache_client=None, cache_ttl: int = 900,
                 backends: list[LLMBackend] = None):
        self._cache = cache_client
        self._cache_ttl = cache_ttl
        self._backends = backends or create_backend(llm_key)

    async def score(self, symbol: str, headlines: list[str]) -> SentimentResult:
        # 1. Check cache
        if self._cache:
            cached = await self._cache.get(f"sentiment:{symbol}:latest")
            if cached:
                data = json.loads(cached) if isinstance(cached, (str, bytes)) else cached
                return SentimentResult(
                    score=data["score"],
                    confidence=data["confidence"],
                    source="cache",
                )

        # 2. No headlines → neutral
        if not headlines:
            return SentimentResult(score=0.0, confidence=1.0, source="fallback")

        # 3. Build prompt
        prompt = (
            f"Analyze the market sentiment for {symbol} based on these headlines:\n"
            + "\n".join(f"- {h[:200]}" for h in headlines[:5])
            + "\n\nYou MUST respond with ONLY raw valid JSON (no markdown, no extra text).\n"
            + 'Respond with exactly: {"score": <float -1.0 to 1.0>, "confidence": <float 0.0 to 1.0>}'
        )

        # 4. Try backends in order (fallback chain)
        result = None
        source = "fallback"
        for backend in self._backends:
            text = await backend.complete(prompt)
            if text is not None:
                parsed = self._extract_json(text)
                if parsed is not None:
                    source = "local" if isinstance(backend, LocalLLMBackend) else "cloud"
                    result = SentimentResult(
                        score=max(-1.0, min(1.0, float(parsed["score"]))),
                        confidence=max(0.0, min(1.0, float(parsed["confidence"]))),
                        source=source,
                    )
                    break

        if result is None:
            logger.error("All LLM backends failed", symbol=symbol)
            result = SentimentResult(score=0.0, confidence=0.5, source="llm_error")

        # 5. Cache only successful, real results. Caching llm_error or fallback
        # propagated stale failures for the entire 15-min TTL — every read
        # came back as source="cache" with score=0.0, indistinguishable from
        # a real neutral sentiment. See agent:closed:{symbol} stream
        # contamination logged in the tech-debt registry (2026-05-05).
        if self._cache and result.source not in ("llm_error", "fallback"):
            cache_data = json.dumps({
                "score": result.score,
                "confidence": result.confidence,
                "source": result.source,
            })
            await self._cache.set(
                f"sentiment:{symbol}:latest", cache_data, ex=self._cache_ttl
            )

        return result

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        """Extract a JSON object from LLM response text with regex fallback."""
        try:
            parsed = json.loads(text.strip())
            if "score" in parsed and "confidence" in parsed:
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

        match = _JSON_OBJECT_RE.search(text)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, TypeError):
                pass

        return None
