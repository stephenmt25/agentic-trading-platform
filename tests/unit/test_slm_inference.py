"""Tests for SLM Inference service: completion and sentiment endpoints."""

import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from services.slm_inference.src.main import app, _generate


# ---------------------------------------------------------------------------
# _generate tests (mock mode — no model loaded)
# ---------------------------------------------------------------------------

class TestGenerateMock:
    def test_mock_returns_json(self):
        """When _llm is None (no model), _generate returns mock JSON."""
        text, tokens = _generate("test prompt")
        parsed = json.loads(text)
        assert "score" in parsed
        assert "confidence" in parsed
        assert tokens == 10


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestCompletionsEndpoint:
    def setup_method(self):
        self.client = TestClient(app)

    def test_completions_success(self):
        resp = self.client.post("/v1/completions", json={
            "prompt": "What is Bitcoin?",
            "max_tokens": 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "text" in data
        assert "tokens_used" in data
        assert "latency_ms" in data

    def test_completions_default_params(self):
        resp = self.client.post("/v1/completions", json={"prompt": "test"})
        assert resp.status_code == 200

    def test_completions_missing_prompt(self):
        resp = self.client.post("/v1/completions", json={})
        assert resp.status_code == 422


class TestSentimentEndpoint:
    def setup_method(self):
        self.client = TestClient(app)

    def test_sentiment_with_headlines(self):
        resp = self.client.post("/v1/sentiment", json={
            "symbol": "BTC/USDT",
            "headlines": ["Bitcoin hits new all-time high"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert -1.0 <= data["score"] <= 1.0
        assert 0.0 <= data["confidence"] <= 1.0
        assert "latency_ms" in data

    def test_sentiment_empty_headlines(self):
        resp = self.client.post("/v1/sentiment", json={
            "symbol": "BTC/USDT",
            "headlines": [],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 0.0
        assert data["confidence"] == 0.1

    def test_sentiment_missing_symbol(self):
        resp = self.client.post("/v1/sentiment", json={
            "headlines": ["test"],
        })
        assert resp.status_code == 422


class TestHealthEndpoint:
    def setup_method(self):
        self.client = TestClient(app)

    def test_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "model_loaded" in data
