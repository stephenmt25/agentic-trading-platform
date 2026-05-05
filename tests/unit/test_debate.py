"""Tests for Phase 5: Adversarial Bull/Bear Debate Engine.

Tests the debate engine rounds, prompt rendering, JSON extraction,
fallback logic, and result structure.
"""

import pytest
import json
from typing import Optional

from services.debate.src.engine import (
    DebateEngine, DebateResult, DebateRound, MarketContext,
    _extract_json, _render, _load_template,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_context(symbol="BTC/USDT"):
    return MarketContext(
        symbol=symbol, price=50000.0, rsi=45.0, macd_histogram=0.002,
        adx=28.0, bb_pct_b=0.6, atr=500.0, regime="TRENDING_UP",
        ta_score=0.35, sentiment_score=0.2,
    )


class MockBackend:
    """Returns canned JSON responses for bull, bear, and judge prompts."""

    def __init__(self, bull_score=0.7, bear_score=0.6, judge_score=0.3, judge_conf=0.75):
        self.bull_score = bull_score
        self.bear_score = bear_score
        self.judge_score = judge_score
        self.judge_conf = judge_conf
        self.prompts_received: list[str] = []

    async def complete(self, prompt: str, grammar: Optional[str] = None) -> Optional[str]:
        self.prompts_received.append(prompt)
        if "BULL advocate" in prompt:
            return json.dumps({
                "argument": "RSI is oversold, MACD turning positive, strong buy signal.",
                "conviction": self.bull_score,
            })
        elif "BEAR advocate" in prompt:
            return json.dumps({
                "argument": "High volatility and overbought conditions suggest reversal.",
                "conviction": self.bear_score,
            })
        elif "impartial JUDGE" in prompt:
            return json.dumps({
                "score": self.judge_score,
                "confidence": self.judge_conf,
                "reasoning": "Bull case slightly stronger due to momentum indicators.",
            })
        return None


class FailingBackend:
    """Always returns None."""
    async def complete(self, prompt: str, grammar: Optional[str] = None) -> Optional[str]:
        return None


class GarbageBackend:
    """Returns non-JSON text."""
    async def complete(self, prompt: str, grammar: Optional[str] = None) -> Optional[str]:
        return "I cannot make a determination at this time."


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_valid_json(self):
        result = _extract_json('{"score": 0.5, "confidence": 0.8}')
        assert result["score"] == 0.5

    def test_json_with_preamble(self):
        result = _extract_json('Here is my response: {"score": -0.3, "confidence": 0.6}')
        assert result is not None
        assert result["score"] == -0.3

    def test_no_json(self):
        assert _extract_json("No JSON here") is None

    def test_none_input(self):
        assert _extract_json(None) is None

    def test_empty_string(self):
        assert _extract_json("") is None


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

class TestRender:
    def test_renders_context(self):
        ctx = _make_context()
        template = "Symbol: {{symbol}}, Price: {{price}}, RSI: {{rsi}}"
        result = _render(template, ctx)
        assert "BTC/USDT" in result
        assert "50000.00" in result
        assert "45.0" in result

    def test_renders_extra_vars(self):
        ctx = _make_context()
        template = "{{symbol}} — {{transcript}}"
        result = _render(template, ctx, transcript="BULL: buy, BEAR: sell")
        assert "BULL: buy" in result


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------

class TestLoadTemplate:
    def test_load_bull(self):
        t = _load_template("bull")
        assert "BULL advocate" in t
        assert "{{symbol}}" in t

    def test_load_bear(self):
        t = _load_template("bear")
        assert "BEAR advocate" in t

    def test_load_judge(self):
        t = _load_template("judge")
        assert "impartial JUDGE" in t


# ---------------------------------------------------------------------------
# Debate engine
# ---------------------------------------------------------------------------

class TestDebateEngine:

    @pytest.mark.asyncio
    async def test_basic_debate_produces_result(self):
        backend = MockBackend()
        engine = DebateEngine(backend, num_rounds=2)
        ctx = _make_context()

        result = await engine.run(ctx)

        assert isinstance(result, DebateResult)
        assert result.symbol == "BTC/USDT"
        assert -1.0 <= result.score <= 1.0
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.rounds) == 2
        assert result.reasoning != ""

    @pytest.mark.asyncio
    async def test_result_has_unique_cycle_id_per_run(self):
        """Every debate cycle should have a fresh UUID for transcript persistence."""
        from uuid import UUID
        backend = MockBackend()
        engine = DebateEngine(backend, num_rounds=1)
        r1 = await engine.run(_make_context())
        r2 = await engine.run(_make_context())
        assert isinstance(r1.cycle_id, UUID)
        assert isinstance(r2.cycle_id, UUID)
        assert r1.cycle_id != r2.cycle_id

    @pytest.mark.asyncio
    async def test_rounds_have_arguments(self):
        backend = MockBackend()
        engine = DebateEngine(backend, num_rounds=2)
        result = await engine.run(_make_context())

        for rd in result.rounds:
            assert isinstance(rd, DebateRound)
            assert rd.bull_argument != ""
            assert rd.bear_argument != ""
            assert 0.0 <= rd.bull_conviction <= 1.0
            assert 0.0 <= rd.bear_conviction <= 1.0

    @pytest.mark.asyncio
    async def test_single_round(self):
        backend = MockBackend()
        engine = DebateEngine(backend, num_rounds=1)
        result = await engine.run(_make_context())

        assert len(result.rounds) == 1

    @pytest.mark.asyncio
    async def test_judge_score_used(self):
        backend = MockBackend(judge_score=0.8, judge_conf=0.9)
        engine = DebateEngine(backend, num_rounds=1)
        result = await engine.run(_make_context())

        assert result.score == 0.8
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_bearish_judge(self):
        backend = MockBackend(judge_score=-0.7, judge_conf=0.85)
        engine = DebateEngine(backend, num_rounds=1)
        result = await engine.run(_make_context())

        assert result.score == -0.7

    @pytest.mark.asyncio
    async def test_all_prompts_sent(self):
        backend = MockBackend()
        engine = DebateEngine(backend, num_rounds=2)
        await engine.run(_make_context())

        # 2 rounds * 2 (bull + bear) + 1 judge = 5 prompts
        assert len(backend.prompts_received) == 5

    @pytest.mark.asyncio
    async def test_failing_backend_uses_fallback(self):
        backend = FailingBackend()
        engine = DebateEngine(backend, num_rounds=1)
        result = await engine.run(_make_context())

        # Should not crash — uses conviction fallback
        assert isinstance(result, DebateResult)
        assert result.confidence == 0.3  # fallback confidence
        assert "fallback" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_garbage_backend_uses_fallback(self):
        backend = GarbageBackend()
        engine = DebateEngine(backend, num_rounds=1)
        result = await engine.run(_make_context())

        # Garbage text stored as argument, judge fallback used
        assert isinstance(result, DebateResult)
        assert result.rounds[0].bull_conviction == 0.5  # default

    @pytest.mark.asyncio
    async def test_score_clamped(self):
        class ExtremeBackend:
            async def complete(self, prompt, grammar: Optional[str] = None):
                if "JUDGE" in prompt:
                    return json.dumps({"score": 5.0, "confidence": 3.0, "reasoning": "extreme"})
                return json.dumps({"argument": "test", "conviction": 0.5})

        engine = DebateEngine(ExtremeBackend(), num_rounds=1)
        result = await engine.run(_make_context())
        assert result.score == 1.0
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_latency_tracked(self):
        backend = MockBackend()
        engine = DebateEngine(backend, num_rounds=1)
        result = await engine.run(_make_context())

        assert result.total_latency_ms >= 0
