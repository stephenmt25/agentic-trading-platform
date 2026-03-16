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

        # 3. Rule-based keyword sentiment scoring across headlines
        score, confidence = self._keyword_score(headlines)

        res = SentimentResult(score=score, confidence=confidence, source="keyword_rules")
        
        # 4. Cache hit mapping
        await self._cache.set(symbol, {
            "score": res.score,
            "confidence": res.confidence,
            "source": res.source
        })
        
        return res

    @staticmethod
    def _keyword_score(headlines: list) -> tuple:
        """Score sentiment using keyword frequency analysis. Returns (score, confidence)."""
        BULLISH = {
            "surge": 0.6, "rally": 0.5, "bullish": 0.7, "gains": 0.4, "soars": 0.6,
            "breakout": 0.5, "upgrade": 0.4, "adoption": 0.3, "partnership": 0.3,
            "record high": 0.6, "buy": 0.3, "momentum": 0.3, "recovery": 0.4,
            "accumulation": 0.3, "growth": 0.3, "positive": 0.3, "outperform": 0.4,
        }
        BEARISH = {
            "crash": -0.7, "plunge": -0.6, "bearish": -0.7, "losses": -0.4, "tumbles": -0.6,
            "sell-off": -0.6, "selloff": -0.6, "downgrade": -0.4, "ban": -0.5,
            "hack": -0.6, "fraud": -0.7, "lawsuit": -0.4, "collapse": -0.7,
            "fear": -0.3, "panic": -0.5, "negative": -0.3, "underperform": -0.4,
            "warning": -0.3, "risk": -0.2, "decline": -0.4, "drop": -0.3,
        }

        if not headlines:
            return 0.0, 0.5

        total_score = 0.0
        match_count = 0
        for headline in headlines:
            text = headline.lower() if isinstance(headline, str) else str(headline).lower()
            for keyword, weight in BULLISH.items():
                if keyword in text:
                    total_score += weight
                    match_count += 1
            for keyword, weight in BEARISH.items():
                if keyword in text:
                    total_score += weight
                    match_count += 1

        if match_count == 0:
            return 0.0, 0.3  # no signal, low confidence

        # Normalize score to [-1.0, 1.0]
        avg_score = total_score / match_count
        final_score = max(-1.0, min(1.0, avg_score))

        # Confidence scales with number of keyword matches (more matches = higher confidence)
        confidence = min(0.95, 0.4 + (match_count * 0.05))

        return round(final_score, 3), round(confidence, 2)
