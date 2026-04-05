"""Tests for Analyst service: sentiment scoring via keyword matching."""

import json
from unittest.mock import AsyncMock

import pytest

from services.analyst.src.sentiment_scorer import SentimentScorer, SentimentResult


# ---------------------------------------------------------------------------
# SentimentScorer._keyword_score tests
# ---------------------------------------------------------------------------

class TestKeywordScoring:
    def test_bullish_keywords_positive_score(self):
        score, confidence = SentimentScorer._keyword_score(["Bitcoin rally continues", "Massive adoption surge"])
        assert score > 0.0
        assert 0.0 <= confidence <= 1.0

    def test_bearish_keywords_negative_score(self):
        score, confidence = SentimentScorer._keyword_score(["Market crash imminent", "Massive fraud exposed"])
        assert score < 0.0

    def test_neutral_headlines_zero(self):
        score, confidence = SentimentScorer._keyword_score(["Regular market update today"])
        assert score == 0.0
        assert confidence == 0.3  # no keyword matches → low confidence

    def test_empty_headlines(self):
        score, confidence = SentimentScorer._keyword_score([])
        assert score == 0.0
        assert confidence == 0.5

    def test_score_bounded(self):
        headlines = ["surge rally bullish adoption breakout gains soars"] * 10
        score, confidence = SentimentScorer._keyword_score(headlines)
        assert -1.0 <= score <= 1.0

    def test_confidence_grows_with_matches(self):
        _, conf_few = SentimentScorer._keyword_score(["rally"])
        _, conf_many = SentimentScorer._keyword_score(["rally surge bullish adoption breakout gains soars momentum recovery growth"])
        assert conf_many > conf_few


# ---------------------------------------------------------------------------
# SentimentScorer.score integration tests
# ---------------------------------------------------------------------------

class TestSentimentScorer:
    @pytest.mark.asyncio
    async def test_returns_cached_result(self):
        cache = AsyncMock()
        cache.get = AsyncMock(return_value={
            "score": 0.5, "confidence": 0.8, "source": "keyword_rules",
        })
        news = AsyncMock()
        scorer = SentimentScorer(cache=cache, news=news)
        result = await scorer.score("BTC/USDT")
        assert result.score == 0.5
        assert result.source == "cache"

    @pytest.mark.asyncio
    async def test_no_cache_uses_headlines(self):
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        news = AsyncMock()
        news.get_headlines = AsyncMock(return_value=["Bitcoin rally"])

        scorer = SentimentScorer(cache=cache, news=news, llm_key="test-key")
        result = await scorer.score("BTC/USDT")
        assert isinstance(result, SentimentResult)
        assert result.source == "keyword_rules"
        cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_headlines_returns_fallback(self):
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        news = AsyncMock()
        news.get_headlines = AsyncMock(return_value=[])

        scorer = SentimentScorer(cache=cache, news=news, llm_key="test-key")
        result = await scorer.score("BTC/USDT")
        assert result.score == 0.0
        assert result.source == "fallback"

    @pytest.mark.asyncio
    async def test_no_llm_key_returns_fallback(self):
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        news = AsyncMock()
        news.get_headlines = AsyncMock(return_value=["headline"])

        scorer = SentimentScorer(cache=cache, news=news, llm_key="")
        result = await scorer.score("BTC/USDT")
        assert result.source == "fallback"
