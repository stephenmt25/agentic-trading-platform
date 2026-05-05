"""Tests for Sentiment service: LLM scorer, JSON extraction, fallback chain."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.sentiment.src.scorer import (
    LLMSentimentScorer, SentimentResult,
    CloudLLMBackend, LocalLLMBackend, create_backend,
)


# ---------------------------------------------------------------------------
# JSON extraction tests
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_clean_json(self):
        text = '{"score": 0.5, "confidence": 0.8}'
        result = LLMSentimentScorer._extract_json(text)
        assert result is not None
        assert result["score"] == 0.5

    def test_json_with_whitespace(self):
        text = '  {"score": -0.3, "confidence": 0.9}  '
        result = LLMSentimentScorer._extract_json(text)
        assert result is not None
        assert result["score"] == -0.3

    def test_json_embedded_in_text(self):
        text = 'Here is the result: {"score": 0.7, "confidence": 0.6} as requested.'
        result = LLMSentimentScorer._extract_json(text)
        assert result is not None
        assert result["score"] == 0.7

    def test_invalid_json_returns_none(self):
        assert LLMSentimentScorer._extract_json("not json at all") is None

    def test_missing_score_field(self):
        text = '{"confidence": 0.8}'
        assert LLMSentimentScorer._extract_json(text) is None

    def test_missing_confidence_field(self):
        text = '{"score": 0.5}'
        assert LLMSentimentScorer._extract_json(text) is None


# ---------------------------------------------------------------------------
# LLMSentimentScorer tests
# ---------------------------------------------------------------------------

class TestLLMSentimentScorer:
    @pytest.mark.asyncio
    async def test_cached_result_returned(self):
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=json.dumps({
            "score": 0.5, "confidence": 0.8, "source": "cloud",
        }))
        scorer = LLMSentimentScorer(cache_client=cache, backends=[])
        result = await scorer.score("BTC/USDT", ["headline"])
        assert result.score == 0.5
        assert result.source == "cache"

    @pytest.mark.asyncio
    async def test_no_headlines_returns_neutral(self):
        scorer = LLMSentimentScorer(backends=[])
        result = await scorer.score("BTC/USDT", [])
        assert result.score == 0.0
        assert result.confidence == 1.0
        assert result.source == "fallback"

    @pytest.mark.asyncio
    async def test_backend_success(self):
        backend = AsyncMock()
        backend.complete = AsyncMock(return_value='{"score": 0.6, "confidence": 0.85}')
        scorer = LLMSentimentScorer(backends=[backend])
        result = await scorer.score("BTC/USDT", ["Bitcoin surging"])
        assert result.score == 0.6
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_backend_failure_falls_through(self):
        bad_backend = AsyncMock()
        bad_backend.complete = AsyncMock(return_value=None)
        good_backend = AsyncMock()
        good_backend.complete = AsyncMock(return_value='{"score": 0.3, "confidence": 0.7}')
        scorer = LLMSentimentScorer(backends=[bad_backend, good_backend])
        result = await scorer.score("BTC/USDT", ["headline"])
        assert result.score == 0.3

    @pytest.mark.asyncio
    async def test_all_backends_fail_returns_error(self):
        bad = AsyncMock()
        bad.complete = AsyncMock(return_value=None)
        scorer = LLMSentimentScorer(backends=[bad])
        result = await scorer.score("BTC/USDT", ["headline"])
        assert result.source == "llm_error"
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_score_clamped_to_bounds(self):
        backend = AsyncMock()
        backend.complete = AsyncMock(return_value='{"score": 5.0, "confidence": 2.0}')
        scorer = LLMSentimentScorer(backends=[backend])
        result = await scorer.score("BTC/USDT", ["headline"])
        assert result.score == 1.0
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_result_cached_after_scoring(self):
        backend = AsyncMock()
        backend.complete = AsyncMock(return_value='{"score": 0.4, "confidence": 0.7}')
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        scorer = LLMSentimentScorer(cache_client=cache, cache_ttl=900, backends=[backend])
        await scorer.score("BTC/USDT", ["headline"])
        cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_error_result_is_not_cached(self):
        """All-backends-fail must NOT poison the cache. Caching the
        SentimentResult(0.0, 0.5, 'llm_error') made every read for the
        next 15 min return source='cache' with neutral fake values —
        contaminated 4,645+ closed-trade entries before being noticed."""
        bad = AsyncMock()
        bad.complete = AsyncMock(return_value=None)
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        scorer = LLMSentimentScorer(cache_client=cache, cache_ttl=900, backends=[bad])
        result = await scorer.score("BTC/USDT", ["headline"])
        assert result.source == "llm_error"
        cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_headlines_fallback_is_not_cached(self):
        """Fallback (no headlines) is also a degraded path — don't cache."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        scorer = LLMSentimentScorer(cache_client=cache, cache_ttl=900, backends=[])
        result = await scorer.score("BTC/USDT", [])
        assert result.source == "fallback"
        cache.set.assert_not_called()


# ---------------------------------------------------------------------------
# create_backend tests
# ---------------------------------------------------------------------------

class TestCreateBackend:
    @patch("services.sentiment.src.scorer.settings")
    def test_cloud_mode(self, mock_settings):
        mock_settings.LLM_BACKEND = "cloud"
        backends = create_backend("test-key")
        assert len(backends) == 1
        assert isinstance(backends[0], CloudLLMBackend)

    @patch("services.sentiment.src.scorer.settings")
    def test_local_mode(self, mock_settings):
        mock_settings.LLM_BACKEND = "local"
        mock_settings.SLM_INFERENCE_URL = "http://localhost:8095"
        backends = create_backend()
        assert len(backends) == 1
        assert isinstance(backends[0], LocalLLMBackend)

    @patch("services.sentiment.src.scorer.settings")
    def test_auto_mode_both(self, mock_settings):
        mock_settings.LLM_BACKEND = "auto"
        mock_settings.SLM_INFERENCE_URL = "http://localhost:8095"
        backends = create_backend("test-key")
        assert len(backends) == 2
        assert isinstance(backends[0], LocalLLMBackend)
        assert isinstance(backends[1], CloudLLMBackend)
