"""Redis schema invariant scanner.

Continuous-checking infrastructure that catches the producer/consumer
schema drift class of bug — the same root cause behind ``acb25ae`` (analyst
tracker bytes-vs-str), ``f583ffb`` (pnl summary string-vs-hash), and the
sentiment cache poisoning observed 2026-05-05.

Approach:
- Declarative schema registry below (`SCHEMAS`). Each entry pins a key
  pattern to its expected Redis type and (for hashes/streams) its required
  field set.
- ``scan(redis)`` walks every schema's pattern with ``SCAN``, type-checks
  each matched key, and for hashes/streams pulls the most recent value
  to verify the field set.
- Returns ``list[RedisInvariantViolation]`` — empty when healthy. Caller
  is responsible for routing violations through the alerter and/or
  surfacing them on a health endpoint.

The scanner is bounded: at most ``MAX_KEYS_PER_PATTERN`` keys per pattern,
and only the most-recent stream entry per stream — so wall-clock cost is
predictable on a Redis with millions of keys.

Adding a schema entry costs nothing at runtime; missing schemas mean
unknown keys silently pass. Plan: add entries as new keys are introduced
in ``libs/messaging/channels.py`` / ``libs/core/agent_registry.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from libs.observability import get_logger

logger = get_logger("observability.redis_invariants")


@dataclass(frozen=True)
class KeySchema:
    """Declarative schema for a Redis key/stream pattern."""
    pattern: str                                # SCAN MATCH pattern (glob)
    expected_type: str                          # 'hash'|'stream'|'string'|'zset'|'set'|'list'
    required_fields: tuple[str, ...] = ()       # for hashes / streams; empty = no check
    notes: str = ""


@dataclass(frozen=True)
class RedisInvariantViolation:
    key: str
    pattern: str
    expected: str
    actual: str
    severity: str = "MEDIUM"  # 'HIGH' | 'MEDIUM' | 'LOW'


# ---------------------------------------------------------------------------
# Schema registry
# ---------------------------------------------------------------------------

# Single source of truth for the format-string keys lives in
# ``libs/core/agent_registry.py`` (WEIGHTS_KEY, etc.); the patterns here
# are the SCAN-glob equivalents.
SCHEMAS: tuple[KeySchema, ...] = (
    KeySchema(
        pattern="agent:weights:*",
        expected_type="hash",
        notes="Per-symbol agent weights. Field names are agent identifiers "
              "(ta/sentiment/debate). Field values are stringified floats.",
    ),
    KeySchema(
        pattern="agent:tracker:*",
        expected_type="hash",
        required_fields=("ewma_accuracy", "sample_count", "last_updated"),
        notes="Per (symbol, agent) EWMA tracker state. Bytes-vs-str on these "
              "fields was the acb25ae class of bug — verify field names match "
              "what consumers look up.",
    ),
    KeySchema(
        pattern="agent:outcomes:*",
        expected_type="stream",
        required_fields=("agent", "direction", "score", "timestamp"),
        notes="Stream of agent score snapshots taken at order-execution time. "
              "Producer is libs/core/agent_registry.py::record_agent_scores; "
              "no live consumer — kept as an audit trail. Field is `score` "
              "(stringified float in [0, 1]), not `price` — the original plan "
              "doc had this wrong.",
    ),
    KeySchema(
        pattern="agent:closed:*",
        expected_type="stream",
        required_fields=("position_id", "outcome", "pnl_pct", "agents_json", "timestamp"),
        notes="Stream of closed-trade outcomes consumed by the EWMA "
              "learning loop in AgentPerformanceTracker.recompute_weights.",
    ),
    KeySchema(
        pattern="pnl:daily:*",
        expected_type="hash",
        required_fields=("date", "total_pct_micro"),
        notes="Daily realised-PnL counter. f583ffb was a producer/consumer "
              "type mismatch on this key — the counter is a hash, not a JSON "
              "string. CircuitBreaker reads total_pct_micro / 1e6.",
    ),
    KeySchema(
        pattern="praxis:kill_switch",
        expected_type="string",
        notes="Kill switch flag. Value is 'on' or 'off'.",
    ),
    KeySchema(
        pattern="agent:position_scores:*",
        expected_type="string",
        notes="JSON-encoded snapshot {agents, regime} written by execution "
              "at order placement time. PnL closer reads this on close.",
    ),
    # Deliberately not registered:
    #   - agent:archive:* (post-hoc archives from reset_clean_baseline.py — schema-free)
    #   - regime:*, indicators:*, sentiment:*:latest (informal caches; add when
    #     we want to enforce shape there too)
)

# Bounds — keep scan time predictable on a large Redis.
MAX_KEYS_PER_PATTERN = 50
STREAM_SAMPLE_COUNT = 1


def _decode(v):
    return v.decode() if isinstance(v, (bytes, bytearray)) else v


async def _check_hash(redis, key: str, schema: KeySchema) -> list[RedisInvariantViolation]:
    raw = await redis.hgetall(key)
    decoded = {_decode(k): _decode(v) for k, v in raw.items()}
    if not schema.required_fields:
        return []
    missing = [f for f in schema.required_fields if f not in decoded]
    if missing:
        return [RedisInvariantViolation(
            key=key, pattern=schema.pattern,
            expected=f"hash with required fields {list(schema.required_fields)}",
            actual=f"missing: {missing}; present: {sorted(decoded.keys())}",
            severity="HIGH",
        )]
    return []


async def _check_stream(redis, key: str, schema: KeySchema) -> list[RedisInvariantViolation]:
    if not schema.required_fields:
        return []
    entries = await redis.xrevrange(key, count=STREAM_SAMPLE_COUNT)
    if not entries:
        # Empty stream — no schema to validate. Treat as healthy.
        return []
    violations = []
    for entry_id, fields in entries:
        decoded = {_decode(k): _decode(v) for k, v in fields.items()}
        missing = [f for f in schema.required_fields if f not in decoded]
        if missing:
            violations.append(RedisInvariantViolation(
                key=key, pattern=schema.pattern,
                expected=f"stream entry with fields {list(schema.required_fields)}",
                actual=f"latest entry id={_decode(entry_id)} missing: {missing}; "
                       f"present: {sorted(decoded.keys())}",
                severity="HIGH",
            ))
    return violations


async def scan(redis, schemas: Sequence[KeySchema] = SCHEMAS) -> list[RedisInvariantViolation]:
    """Walk every schema's pattern; return a list of violations.

    Empty list = no violations found (healthy). Failures while reading a
    specific key are logged and recorded as a LOW-severity violation, never
    raised — the scanner must never take down the host service.
    """
    violations: list[RedisInvariantViolation] = []
    for schema in schemas:
        sampled = 0
        try:
            async for raw_key in redis.scan_iter(match=schema.pattern, count=200):
                key = _decode(raw_key)
                sampled += 1
                if sampled > MAX_KEYS_PER_PATTERN:
                    break
                try:
                    actual_type = _decode(await redis.type(key))
                except Exception as e:
                    violations.append(RedisInvariantViolation(
                        key=key, pattern=schema.pattern,
                        expected=schema.expected_type,
                        actual=f"type lookup failed: {e}",
                        severity="LOW",
                    ))
                    continue

                if actual_type != schema.expected_type:
                    violations.append(RedisInvariantViolation(
                        key=key, pattern=schema.pattern,
                        expected=f"type={schema.expected_type}",
                        actual=f"type={actual_type}",
                        severity="HIGH",
                    ))
                    continue

                try:
                    if schema.expected_type == "hash":
                        violations.extend(await _check_hash(redis, key, schema))
                    elif schema.expected_type == "stream":
                        violations.extend(await _check_stream(redis, key, schema))
                except Exception as e:
                    violations.append(RedisInvariantViolation(
                        key=key, pattern=schema.pattern,
                        expected=schema.expected_type,
                        actual=f"field check failed: {e}",
                        severity="LOW",
                    ))
        except Exception as e:
            logger.exception("Scan failed for pattern", pattern=schema.pattern, error=str(e))
    return violations
