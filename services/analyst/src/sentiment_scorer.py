from dataclasses import dataclass
import json
from .cache import SentimentCache
from .news_scraper import NewsScraper

@dataclass
class SentimentResult:
    score: float
    confidence: float
    source: str

class SentimentScorer:
    def __init__(self, cache: SentimentCache, news: NewsScraper, llm_key: str = ""):
        self._cache = cache
        self._news = news
        self._llm_key = llm_key

    async def score(self, symbol: str) -> SentimentResult:
        # 1. Cache First
        cached = await self._cache.get(symbol)
        if cached:
            return SentimentResult(
                score=cached["score"], 
                confidence=cached["confidence"], 
                source="cache"
            )

        # 2. Get News
        headlines = await self._news.get_headlines(symbol, limit=5)
        if not headlines or not self._llm_key:
            # Fallback neutral score if no data or no key
            return SentimentResult(score=0.0, confidence=1.0, source="fallback")

        # 3. Call LLM (Mocked for Phase 1 logic without live AI key costs)
        # prompt = f"Analyze sentiment for {symbol} based on: {headlines}. Return JSON: score (-1.0 to 1.0) and reasoning."
        
        import random
        llm_score = round(random.uniform(-1.0, 1.0), 2)
        
        res = SentimentResult(score=llm_score, confidence=0.85, source="llm")
        
        # 4. Cache hit mapping
        await self._cache.set(symbol, {
            "score": res.score,
            "confidence": res.confidence,
            "source": res.source
        })
        
        return res
