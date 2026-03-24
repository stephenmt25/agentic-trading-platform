"""Tests for Phase 4: SLM Backend Protocol and Fallback Chain.

Tests the LLMBackend protocol, CloudLLMBackend, LocalLLMBackend,
fallback chain, and the refactored LLMSentimentScorer.
"""

import pytest
import json
from unittest.mock import patch
from typing import Optional

from services.sentiment.src.scorer import (
    LLMBackend,
    CloudLLMBackend,
    LocalLLMBackend,
    LLMSentimentScorer,
    SentimentResult,
    create_backend,
)


# ---------------------------------------------------------------------------
# Test backends
# ---------------------------------------------------------------------------

class SuccessBackend:
    """Always returns a valid sentiment JSON response."""
    def __init__(self, score: float = 0.5, confidence: float = 0.8):
        self.score = score
        self.confidence = confidence
        self.call_count = 0

    async def complete(self, prompt: str) -> Optional[str]:
        self.call_count += 1
        return json.dumps({"score": self.score, "confidence": self.confidence})


class FailBackend:
    """Always returns None (simulates failure)."""
    def __init__(self):
        self.call_count = 0

    async def complete(self, prompt: str) -> Optional[str]:
        self.call_count += 1
        return None


class GarbageBackend:
    """Returns non-JSON text (simulates malformed response)."""
    def __init__(self):
        self.call_count = 0

    async def complete(self, prompt: str) -> Optional[str]:
        self.call_count += 1
        return "I think the market is bullish but I cannot give you JSON sorry"


class FakeCache:
    def __init__(self):
        self._store = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ex=None):
        self._store[key] = value


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestLLMBackendProtocol:
    def test_success_backend_implements_protocol(self):
        assert isinstance(SuccessBackend(), LLMBackend)

    def test_fail_backend_implements_protocol(self):
        assert isinstance(FailBackend(), LLMBackend)

    def test_cloud_backend_implements_protocol(self):
        assert isinstance(CloudLLMBackend("fake-key"), LLMBackend)

    def test_local_backend_implements_protocol(self):
        assert isinstance(LocalLLMBackend("http://localhost:8095"), LLMBackend)


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------

class TestCreateBackend:
    @patch('services.sentiment.src.scorer.settings')
    def test_cloud_mode(self, mock_settings):
        mock_settings.LLM_BACKEND = "cloud"
        mock_settings.SLM_INFERENCE_URL = "http://localhost:8095"
        backends = create_backend("test-key")
        assert len(backends) == 1
        assert isinstance(backends[0], CloudLLMBackend)

    @patch('services.sentiment.src.scorer.settings')
    def test_local_mode(self, mock_settings):
        mock_settings.LLM_BACKEND = "local"
        mock_settings.SLM_INFERENCE_URL = "http://localhost:8095"
        backends = create_backend()
        assert len(backends) == 1
        assert isinstance(backends[0], LocalLLMBackend)

    @patch('services.sentiment.src.scorer.settings')
    def test_auto_mode_has_fallback(self, mock_settings):
        mock_settings.LLM_BACKEND = "auto"
        mock_settings.SLM_INFERENCE_URL = "http://localhost:8095"
        backends = create_backend("test-key")
        assert len(backends) == 2
        assert isinstance(backends[0], LocalLLMBackend)
        assert isinstance(backends[1], CloudLLMBackend)


# ---------------------------------------------------------------------------
# Scorer with backend chain
# ---------------------------------------------------------------------------

class TestLLMSentimentScorer:

    @pytest.mark.asyncio
    async def test_single_backend_success(self):
        backend = SuccessBackend(score=0.7, confidence=0.9)
        scorer = LLMSentimentScorer(backends=[backend])

        result = await scorer.score("BTC/USDT", ["Bitcoin hits new high"])
        assert result.score == 0.7
        assert result.confidence == 0.9
        assert result.source == "cloud"  # SuccessBackend is not LocalLLMBackend
        assert backend.call_count == 1

    @pytest.mark.asyncio
    async def test_fallback_to_second_backend(self):
        fail = FailBackend()
        success = SuccessBackend(score=-0.3, confidence=0.6)
        scorer = LLMSentimentScorer(backends=[fail, success])

        result = await scorer.score("ETH/USDT", ["Ethereum drops"])
        assert result.score == -0.3
        assert fail.call_count == 1
        assert success.call_count == 1

    @pytest.mark.asyncio
    async def test_all_backends_fail_returns_neutral(self):
        fail1 = FailBackend()
        fail2 = FailBackend()
        scorer = LLMSentimentScorer(backends=[fail1, fail2])

        result = await scorer.score("BTC/USDT", ["Some headline"])
        assert result.score == 0.0
        assert result.confidence == 0.5
        assert result.source == "llm_error"

    @pytest.mark.asyncio
    async def test_garbage_response_skipped_to_fallback(self):
        garbage = GarbageBackend()
        success = SuccessBackend(score=0.4, confidence=0.7)
        scorer = LLMSentimentScorer(backends=[garbage, success])

        result = await scorer.score("BTC/USDT", ["Market update"])
        assert result.score == 0.4
        assert garbage.call_count == 1
        assert success.call_count == 1

    @pytest.mark.asyncio
    async def test_no_headlines_returns_neutral(self):
        backend = SuccessBackend()
        scorer = LLMSentimentScorer(backends=[backend])

        result = await scorer.score("BTC/USDT", [])
        assert result.score == 0.0
        assert result.confidence == 1.0
        assert result.source == "fallback"
        assert backend.call_count == 0  # Should not call backend

    @pytest.mark.asyncio
    async def test_cache_hit_skips_backends(self):
        cache = FakeCache()
        await cache.set("sentiment:BTC/USDT:latest", json.dumps({
            "score": 0.8, "confidence": 0.95, "source": "cache",
        }))
        backend = SuccessBackend()
        scorer = LLMSentimentScorer(backends=[backend], cache_client=cache)

        result = await scorer.score("BTC/USDT", ["headline"])
        assert result.score == 0.8
        assert result.source == "cache"
        assert backend.call_count == 0

    @pytest.mark.asyncio
    async def test_result_cached_after_scoring(self):
        cache = FakeCache()
        backend = SuccessBackend(score=0.6, confidence=0.85)
        scorer = LLMSentimentScorer(backends=[backend], cache_client=cache)

        await scorer.score("BTC/USDT", ["headline"])
        cached = await cache.get("sentiment:BTC/USDT:latest")
        assert cached is not None
        data = json.loads(cached)
        assert data["score"] == 0.6

    @pytest.mark.asyncio
    async def test_score_clamped(self):
        """Scores outside [-1, 1] should be clamped."""
        class ExtremeBackend:
            async def complete(self, prompt):
                return json.dumps({"score": 5.0, "confidence": 2.0})

        scorer = LLMSentimentScorer(backends=[ExtremeBackend()])
        result = await scorer.score("BTC/USDT", ["headline"])
        assert result.score == 1.0
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_local_backend_source_label(self):
        """LocalLLMBackend results should be labeled as 'local'."""
        class FakeLocalBackend(LocalLLMBackend):
            async def complete(self, prompt):
                return json.dumps({"score": 0.5, "confidence": 0.7})

        scorer = LLMSentimentScorer(backends=[FakeLocalBackend("http://fake")])
        result = await scorer.score("BTC/USDT", ["headline"])
        assert result.source == "local"


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_valid_json(self):
        result = LLMSentimentScorer._extract_json('{"score": 0.5, "confidence": 0.8}')
        assert result == {"score": 0.5, "confidence": 0.8}

    def test_json_with_surrounding_text(self):
        result = LLMSentimentScorer._extract_json(
            'Here is my analysis: {"score": -0.3, "confidence": 0.6} I hope this helps.'
        )
        assert result is not None
        assert result["score"] == -0.3

    def test_no_json(self):
        result = LLMSentimentScorer._extract_json("The market looks bullish")
        assert result is None

    def test_json_missing_score(self):
        result = LLMSentimentScorer._extract_json('{"confidence": 0.5}')
        assert result is None
