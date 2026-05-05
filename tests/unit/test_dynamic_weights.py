"""Tests for Phase 2: Dynamic Agent Weighting.

Tests the AgentPerformanceTracker EWMA logic and the updated AgentModifier
with dynamic weights. Uses a FakeRedis-like in-memory mock.
"""

import pytest
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from libs.core.agent_registry import (
    AgentPerformanceTracker, AGENT_DEFAULTS, MIN_WEIGHT, MAX_WEIGHT,
    EWMA_ALPHA, MIN_SAMPLES, WEIGHTS_KEY, CLOSED_KEY, TRACKER_KEY,
)
from services.hot_path.src.agent_modifier import AgentModifier
from services.hot_path.src.strategy_eval import SignalResult
from libs.core.enums import SignalDirection


# ---------------------------------------------------------------------------
# Fake Redis for unit testing
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal async Redis mock supporting get/set/hset/hgetall/xadd/xrevrange/pipeline/expire/delete."""

    def __init__(self):
        self._store = {}
        self._streams = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ex=None):
        self._store[key] = value

    async def delete(self, key):
        self._store.pop(key, None)

    async def hset(self, key, mapping=None, **kwargs):
        if key not in self._store:
            self._store[key] = {}
        if mapping:
            self._store[key].update(mapping)
        self._store[key].update(kwargs)

    async def hgetall(self, key):
        return self._store.get(key, {})

    async def expire(self, key, seconds):
        pass  # No-op for tests

    async def xadd(self, key, entry, maxlen=None):
        if key not in self._streams:
            self._streams[key] = []
        msg_id = f"{len(self._streams[key])}-0"
        self._streams[key].append((msg_id, entry))
        return msg_id

    async def xrevrange(self, key, count=None):
        entries = self._streams.get(key, [])
        result = list(reversed(entries))
        if count:
            result = result[:count]
        return result

    def pipeline(self, transaction=False):
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, redis):
        self._redis = redis
        self._commands = []

    def get(self, key):
        self._commands.append(("get", key))
        return self

    def hgetall(self, key):
        self._commands.append(("hgetall", key))
        return self

    async def execute(self):
        results = []
        for cmd, key in self._commands:
            if cmd == "get":
                results.append(await self._redis.get(key))
            elif cmd == "hgetall":
                results.append(await self._redis.hgetall(key))
        self._commands = []
        return results


class BytesFakeRedis(FakeRedis):
    """FakeRedis variant that returns bytes-keyed/-valued hash dicts.
    Matches the default decode_responses=False behaviour of redis-py, which
    is what the shared RedisClient uses in production."""
    async def hgetall(self, key):
        d = self._store.get(key, {})
        return {
            (k.encode() if isinstance(k, str) else k):
            (v.encode() if isinstance(v, str) else v)
            for k, v in d.items()
        }


# ---------------------------------------------------------------------------
# AgentPerformanceTracker tests
# ---------------------------------------------------------------------------

class TestAgentPerformanceTracker:

    @pytest.fixture
    def redis(self):
        return FakeRedis()

    @pytest.fixture
    def tracker(self, redis):
        return AgentPerformanceTracker(redis)

    @pytest.mark.asyncio
    async def test_record_agent_scores(self, tracker, redis):
        await tracker.record_agent_scores("BTC/USDT", {
            "ta": {"direction": "BUY", "score": 0.7},
            "sentiment": {"direction": "BUY", "score": 0.3},
        })
        stream_key = "agent:outcomes:BTC/USDT"
        assert stream_key in redis._streams
        assert len(redis._streams[stream_key]) == 2

    @pytest.mark.asyncio
    async def test_record_position_close(self, tracker, redis):
        await tracker.record_position_close(
            symbol="BTC/USDT",
            position_id="pos-123",
            outcome="win",
            pnl_pct=0.05,
            agent_scores={"ta": {"direction": "BUY", "score": 0.7}},
        )
        stream_key = "agent:closed:BTC/USDT"
        assert stream_key in redis._streams
        assert len(redis._streams[stream_key]) == 1
        entry = redis._streams[stream_key][0][1]
        assert entry["outcome"] == "win"

    @pytest.mark.asyncio
    async def test_recompute_weights_no_outcomes_keeps_defaults(self, tracker, redis):
        await tracker.recompute_weights("BTC/USDT")
        # No outcomes → no weights written (stays at defaults)
        weights_key = "agent:weights:BTC/USDT"
        assert weights_key not in redis._store

    @pytest.mark.asyncio
    async def test_recompute_weights_with_outcomes(self, tracker, redis):
        # Record enough closed outcomes to exceed MIN_SAMPLES
        for i in range(15):
            outcome = "win" if i % 3 != 0 else "loss"  # ~66% win rate
            await tracker.record_position_close(
                symbol="BTC/USDT",
                position_id=f"pos-{i}",
                outcome=outcome,
                pnl_pct=0.02 if outcome == "win" else -0.01,
                agent_scores={"ta": {"direction": "BUY", "score": 0.5}},
            )

        await tracker.recompute_weights("BTC/USDT", agent_names=["ta"])

        weights_key = "agent:weights:BTC/USDT"
        assert weights_key in redis._store
        ta_weight = float(redis._store[weights_key]["ta"])
        assert MIN_WEIGHT <= ta_weight <= MAX_WEIGHT

    @pytest.mark.asyncio
    async def test_recompute_weights_below_min_samples_uses_defaults(self, tracker, redis):
        # Only 3 outcomes — below MIN_SAMPLES
        for i in range(3):
            await tracker.record_position_close(
                symbol="ETH/USDT",
                position_id=f"pos-{i}",
                outcome="win",
                pnl_pct=0.01,
                agent_scores={"ta": {"direction": "BUY", "score": 0.5}},
            )

        await tracker.recompute_weights("ETH/USDT", agent_names=["ta"])

        weights_key = "agent:weights:ETH/USDT"
        assert weights_key in redis._store
        ta_weight = float(redis._store[weights_key]["ta"])
        assert ta_weight == AGENT_DEFAULTS["ta"]

    @pytest.mark.asyncio
    async def test_get_weights_returns_defaults_when_empty(self, redis):
        weights = await AgentPerformanceTracker.get_weights(redis, "BTC/USDT")
        assert weights == AGENT_DEFAULTS

    @pytest.mark.asyncio
    async def test_get_weights_reads_from_redis(self, redis):
        await redis.hset("agent:weights:BTC/USDT", mapping={
            "ta": "0.30", "sentiment": "0.10",
        })
        weights = await AgentPerformanceTracker.get_weights(redis, "BTC/USDT")
        assert weights["ta"] == 0.30
        assert weights["sentiment"] == 0.10
        # Debate not in Redis → filled with default
        assert weights["debate"] == AGENT_DEFAULTS["debate"]

    @pytest.mark.asyncio
    async def test_get_weights_clamps_values(self, redis):
        await redis.hset("agent:weights:BTC/USDT", mapping={
            "ta": "5.0",  # above MAX
            "sentiment": "0.001",  # below MIN
        })
        weights = await AgentPerformanceTracker.get_weights(redis, "BTC/USDT")
        assert weights["ta"] == MAX_WEIGHT
        assert weights["sentiment"] == MIN_WEIGHT

    @pytest.mark.asyncio
    async def test_recompute_advances_last_ts_with_bytes_keyed_tracker(self):
        """Regression: tracker hash from real Redis returns bytes keys/values.
        recompute_weights must decode them, otherwise last_ts/sample_count read
        as defaults every iteration and the EWMA path reprocesses the entire
        stream window from scratch each pass (manifests as agent_weight_history
        rows showing samples=0 even though many trades have closed)."""
        bytes_redis = BytesFakeRedis()
        tracker = AgentPerformanceTracker(bytes_redis)
        # First pass: write enough wins for MIN_SAMPLES, plus one loss
        for i in range(11):
            await tracker.record_position_close(
                symbol="BTC/USDT",
                position_id=f"pos-a-{i}",
                outcome="win",
                pnl_pct=0.02,
                agent_scores={"ta": {"direction": "BUY", "score": 0.5}},
            )
        await tracker.recompute_weights("BTC/USDT", agent_names=["ta"])
        first_pass = bytes_redis._store["agent:tracker:BTC/USDT:ta"]
        first_samples = int((first_pass[b"sample_count"]
                             if isinstance(list(first_pass.keys())[0], bytes)
                             else first_pass["sample_count"]))
        assert first_samples == 11, f"expected 11 samples after first pass, got {first_samples}"

        # Second pass with no new outcomes: sample_count must NOT regress
        # (if last_ts is decoded properly, no entries match ts > last_ts)
        await tracker.recompute_weights("BTC/USDT", agent_names=["ta"])
        second_pass = bytes_redis._store["agent:tracker:BTC/USDT:ta"]
        # Tracker hash should be unchanged (no new outcomes processed)
        assert second_pass == first_pass, (
            "second recompute mutated tracker despite no new outcomes — "
            "indicates last_ts is being read as the default 0 instead of the "
            "stored bytes value")


# ---------------------------------------------------------------------------
# AgentModifier dynamic weight tests
# ---------------------------------------------------------------------------

class TestAgentModifierDynamic:

    @pytest.fixture
    def redis(self):
        return FakeRedis()

    def _make_signal(self, direction=SignalDirection.BUY, confidence=0.5):
        return SignalResult(direction=direction, confidence=confidence, rule_matched=True)

    @pytest.mark.asyncio
    async def test_uses_default_weights_when_no_dynamic(self, redis):
        """When no dynamic weights exist, modifier should use AGENT_DEFAULTS."""
        # Set TA score only
        await redis.set("agent:ta_score:BTC/USDT", json.dumps({"score": 1.0}))
        modifier = AgentModifier(redis)
        signal = self._make_signal()

        result = await modifier.apply("BTC/USDT", signal)
        # Default TA weight is 0.20, score=1.0 aligned with BUY → +0.20
        assert result.confidence == pytest.approx(0.7, abs=0.01)

    @pytest.mark.asyncio
    async def test_uses_dynamic_weights(self, redis):
        """When dynamic weights exist, modifier should use them."""
        await redis.set("agent:ta_score:BTC/USDT", json.dumps({"score": 1.0}))
        await redis.hset("agent:weights:BTC/USDT", mapping={"ta": "0.40"})
        modifier = AgentModifier(redis)
        signal = self._make_signal()

        result = await modifier.apply("BTC/USDT", signal)
        # Dynamic TA weight is 0.40, score=1.0 → +0.40
        assert result.confidence == pytest.approx(0.9, abs=0.01)

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_agents(self, redis):
        """When no agent data exists, signal is unchanged."""
        modifier = AgentModifier(redis)
        signal = self._make_signal(confidence=0.6)

        result = await modifier.apply("BTC/USDT", signal)
        assert result.confidence == 0.6

    @pytest.mark.asyncio
    async def test_multiple_agents(self, redis):
        """Multiple agents contribute additively."""
        await redis.set("agent:ta_score:BTC/USDT", json.dumps({"score": 0.5}))
        await redis.set("agent:sentiment:BTC/USDT", json.dumps({"score": 0.8, "confidence": 1.0}))
        modifier = AgentModifier(redis)
        signal = self._make_signal(confidence=0.5)

        result = await modifier.apply("BTC/USDT", signal)
        # TA: 0.5 * 0.20 = +0.10, Sentiment: 0.8*1.0 * 0.15 = +0.12
        assert result.confidence > 0.5
        assert result.confidence < 1.0

    @pytest.mark.asyncio
    async def test_sell_direction_negates_scores(self, redis):
        """For SELL signals, positive agent scores become negative adjustments."""
        await redis.set("agent:ta_score:BTC/USDT", json.dumps({"score": 1.0}))
        modifier = AgentModifier(redis)
        signal = self._make_signal(direction=SignalDirection.SELL, confidence=0.5)

        result = await modifier.apply("BTC/USDT", signal)
        # TA score=+1.0 with SELL → negated → -0.20
        assert result.confidence == pytest.approx(0.3, abs=0.01)

    @pytest.mark.asyncio
    async def test_confidence_clamped_0_1(self, redis):
        """Confidence should never go below 0 or above 1."""
        # Max positive: all agents agree strongly
        await redis.set("agent:ta_score:BTC/USDT", json.dumps({"score": 1.0}))
        await redis.set("agent:sentiment:BTC/USDT", json.dumps({"score": 1.0, "confidence": 1.0}))
        await redis.set("agent:debate:BTC/USDT", json.dumps({"score": 1.0, "confidence": 1.0}))
        modifier = AgentModifier(redis)

        signal = self._make_signal(confidence=0.9)
        result = await modifier.apply("BTC/USDT", signal)
        assert result.confidence <= 1.0

        signal = self._make_signal(confidence=0.1)
        # With opposing direction
        result_sell = await modifier.apply("BTC/USDT",
            self._make_signal(direction=SignalDirection.SELL, confidence=0.1))
        assert result_sell.confidence >= 0.0

    @pytest.mark.asyncio
    async def test_debate_agent_included(self, redis):
        """Debate agent score is picked up when present."""
        await redis.set("agent:debate:BTC/USDT", json.dumps({"score": 0.9, "confidence": 0.8}))
        modifier = AgentModifier(redis)
        signal = self._make_signal(confidence=0.5)

        result = await modifier.apply("BTC/USDT", signal)
        # Debate: 0.9 * 0.8 * 0.25 = +0.18
        assert result.confidence > 0.5
