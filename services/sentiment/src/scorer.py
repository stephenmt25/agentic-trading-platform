import json
import httpx
from dataclasses import dataclass
from typing import Optional

from libs.observability import get_logger

logger = get_logger("sentiment.scorer")


@dataclass
class SentimentResult:
    score: float       # -1.0 (bearish) to 1.0 (bullish)
    confidence: float  # 0.0 to 1.0
    source: str


class LLMSentimentScorer:
    """Real LLM-based sentiment scoring (replaces random.uniform mock)."""

    def __init__(self, llm_key: str = "", cache_client=None, cache_ttl: int = 900):
        self._llm_key = llm_key
        self._cache = cache_client
        self._cache_ttl = cache_ttl

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

        # 3. Call LLM for real scoring
        if not self._llm_key:
            return SentimentResult(score=0.0, confidence=0.5, source="no_key_fallback")

        llm_result = await self._call_llm(symbol, headlines)

        # 4. Cache result
        if self._cache and llm_result:
            cache_data = json.dumps({
                "score": llm_result.score,
                "confidence": llm_result.confidence,
                "source": llm_result.source,
            })
            await self._cache.set(
                f"sentiment:{symbol}:latest", cache_data, ex=self._cache_ttl
            )

        return llm_result

    async def _call_llm(self, symbol: str, headlines: list[str]) -> SentimentResult:
        """Call Claude API for sentiment analysis."""
        prompt = (
            f"Analyze the market sentiment for {symbol} based on these headlines:\n"
            + "\n".join(f"- {h[:200]}" for h in headlines[:5])
            + "\n\nRespond with ONLY a JSON object: "
            '{\"score\": <float -1.0 to 1.0>, \"confidence\": <float 0.0 to 1.0>}'
        )

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self._llm_key,
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
                    text = data["content"][0]["text"]
                    parsed = json.loads(text)
                    return SentimentResult(
                        score=max(-1.0, min(1.0, float(parsed["score"]))),
                        confidence=max(0.0, min(1.0, float(parsed["confidence"]))),
                        source="llm",
                    )
        except Exception as e:
            logger.error("LLM sentiment call failed", error=str(e), symbol=symbol)

        return SentimentResult(score=0.0, confidence=0.5, source="llm_error")
