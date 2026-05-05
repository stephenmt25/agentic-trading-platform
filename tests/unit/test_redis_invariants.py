"""Tests for the Redis schema invariant scanner."""

from __future__ import annotations

import fnmatch

import pytest

from libs.observability.redis_invariants import (
    KeySchema,
    RedisInvariantViolation,
    SCHEMAS,
    scan,
)


# ---------------------------------------------------------------------------
# Lightweight fake Redis for testing the scanner without external services.
# Matches the real client's decode_responses=False contract — every read
# returns bytes, every write accepts str-or-bytes.
# ---------------------------------------------------------------------------

class FakeRedis:
    """Minimal in-memory Redis stub. Supports the methods scan() needs:
    scan_iter, type, hgetall, xrevrange.

    Layout:
        types: {key: 'hash'|'stream'|'string'|'list'|'set'|'zset'|'none'}
        hashes: {key: {field: value}}
        strings: {key: value}
        streams: {key: [(entry_id, {field: value}), ...]}  (newest first)
    """

    def __init__(self):
        self.types: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.strings: dict[str, str] = {}
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}

    def set_hash(self, key: str, fields: dict[str, str]):
        self.types[key] = "hash"
        self.hashes[key] = fields

    def set_string(self, key: str, value: str):
        self.types[key] = "string"
        self.strings[key] = value

    def set_stream(self, key: str, entries: list[tuple[str, dict[str, str]]]):
        self.types[key] = "stream"
        # Internal order is newest-first to match xrevrange semantics.
        self.streams[key] = list(entries)

    def set_wrong_type(self, key: str, t: str):
        """Force a key to claim it's of type `t` (e.g. for type-mismatch tests)."""
        self.types[key] = t

    async def scan_iter(self, match: str, count: int = 200):
        for k in list(self.types.keys()):
            if fnmatch.fnmatchcase(k, match):
                yield k.encode()

    async def type(self, key: str):
        return self.types.get(key, "none").encode()

    async def hgetall(self, key: str):
        d = self.hashes.get(key, {})
        return {k.encode(): str(v).encode() for k, v in d.items()}

    async def xrevrange(self, key: str, count: int = 1):
        return [
            (eid.encode(), {k.encode(): str(v).encode() for k, v in fields.items()})
            for eid, fields in self.streams.get(key, [])[:count]
        ]


# ---------------------------------------------------------------------------
# Type-mismatch detection
# ---------------------------------------------------------------------------

class TestTypeChecks:
    @pytest.mark.asyncio
    async def test_clean_redis_no_violations(self):
        """Empty redis should report no violations — empty patterns are fine."""
        r = FakeRedis()
        v = await scan(r)
        assert v == []

    @pytest.mark.asyncio
    async def test_string_where_hash_expected_flags_high(self):
        """f583ffb-class bug: producer wrote hash, key is string."""
        r = FakeRedis()
        r.set_string("pnl:daily:abc-123", "{\"net_pnl\": 100}")
        v = await scan(r)
        assert any(
            x.pattern == "pnl:daily:*"
            and x.expected.startswith("type=hash")
            and x.actual == "type=string"
            and x.severity == "HIGH"
            for x in v
        ), v

    @pytest.mark.asyncio
    async def test_hash_where_string_expected_flags_high(self):
        """Inverse — kill switch is a string, finding a hash there is bad."""
        r = FakeRedis()
        r.set_hash("praxis:kill_switch", {"on": "yes"})
        v = await scan(r)
        assert any(
            x.key == "praxis:kill_switch"
            and x.expected == "type=string"
            and x.actual == "type=hash"
            for x in v
        )

    @pytest.mark.asyncio
    async def test_correct_type_no_violation_when_no_field_constraints(self):
        """agent:weights:* has no required_fields — type-correct alone passes."""
        r = FakeRedis()
        r.set_hash("agent:weights:BTC/USDT", {"ta": "0.20"})
        v = await scan(r)
        assert v == []


# ---------------------------------------------------------------------------
# Hash field checks
# ---------------------------------------------------------------------------

class TestHashFields:
    @pytest.mark.asyncio
    async def test_tracker_missing_required_field_flags_high(self):
        """acb25ae-class bug: tracker hash missing the field consumers look up."""
        r = FakeRedis()
        r.set_hash("agent:tracker:BTC/USDT:ta", {
            # missing ewma_accuracy
            "sample_count": "10",
            "last_updated": "12345",
        })
        v = await scan(r)
        match = [x for x in v if x.key == "agent:tracker:BTC/USDT:ta"]
        assert len(match) == 1
        assert "ewma_accuracy" in match[0].actual
        assert match[0].severity == "HIGH"

    @pytest.mark.asyncio
    async def test_tracker_complete_no_violation(self):
        r = FakeRedis()
        r.set_hash("agent:tracker:BTC/USDT:ta", {
            "ewma_accuracy": "0.5",
            "sample_count": "10",
            "last_updated": "12345",
        })
        v = await scan(r)
        assert v == []

    @pytest.mark.asyncio
    async def test_pnl_daily_missing_date(self):
        r = FakeRedis()
        r.set_hash("pnl:daily:abc", {"total_pct_micro": "-25000"})  # missing date
        v = await scan(r)
        match = [x for x in v if x.pattern == "pnl:daily:*"]
        assert len(match) == 1
        assert "date" in match[0].actual


# ---------------------------------------------------------------------------
# Stream entry checks
# ---------------------------------------------------------------------------

class TestStreamEntries:
    @pytest.mark.asyncio
    async def test_closed_stream_with_complete_entry_passes(self):
        r = FakeRedis()
        r.set_stream("agent:closed:BTC/USDT", [
            ("1700000000-0", {
                "position_id": "p1",
                "outcome": "win",
                "pnl_pct": "0.012",
                "agents_json": '{"ta": {"score": 0.5}}',
                "timestamp": "1700000000",
            })
        ])
        v = await scan(r)
        assert v == []

    @pytest.mark.asyncio
    async def test_closed_stream_missing_field_flags(self):
        r = FakeRedis()
        r.set_stream("agent:closed:BTC/USDT", [
            ("1700000000-0", {
                "position_id": "p1",
                "outcome": "win",
                # missing pnl_pct, agents_json
                "timestamp": "1700000000",
            })
        ])
        v = await scan(r)
        match = [x for x in v if x.pattern == "agent:closed:*"]
        assert len(match) == 1
        assert "pnl_pct" in match[0].actual
        assert "agents_json" in match[0].actual

    @pytest.mark.asyncio
    async def test_empty_stream_no_violation(self):
        """An empty stream is a stream with no entries to validate — healthy."""
        r = FakeRedis()
        r.set_stream("agent:closed:BTC/USDT", [])
        v = await scan(r)
        assert v == []


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------

class TestBounds:
    @pytest.mark.asyncio
    async def test_scan_bounds_keys_per_pattern(self, monkeypatch):
        """When MAX_KEYS_PER_PATTERN is exceeded, scan stops sampling that pattern."""
        from libs.observability import redis_invariants
        monkeypatch.setattr(redis_invariants, "MAX_KEYS_PER_PATTERN", 3)

        r = FakeRedis()
        # 5 broken pnl:daily hashes — scan should report violations on at most 3.
        for i in range(5):
            r.set_hash(f"pnl:daily:profile-{i}", {})  # missing both required fields
        v = await scan(r)
        match = [x for x in v if x.pattern == "pnl:daily:*"]
        assert len(match) == 3


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

class TestRobustness:
    @pytest.mark.asyncio
    async def test_per_key_failure_does_not_abort_scan(self):
        """A single key's hgetall raising must not stop other patterns."""
        class FlakyRedis(FakeRedis):
            async def hgetall(self, key):
                if key == "pnl:daily:flaky":
                    raise RuntimeError("boom")
                return await super().hgetall(key)

        r = FlakyRedis()
        r.set_hash("pnl:daily:flaky", {})  # would-be violation, but raises
        r.set_hash("agent:tracker:BTC/USDT:ta", {})  # missing all 3 required fields
        v = await scan(r)

        # The flaky key gets a LOW-severity record; the other pattern is checked.
        assert any(x.key == "pnl:daily:flaky" and x.severity == "LOW" for x in v)
        assert any(x.pattern == "agent:tracker:*" and x.severity == "HIGH" for x in v)
