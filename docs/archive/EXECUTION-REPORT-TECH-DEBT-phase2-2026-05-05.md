# Execution Report — Phase 2 (Analyst weight engine)

**Date:** 2026-05-05
**Plan:** `docs/EXECUTION-PLAN-TECH-DEBT-2026-05-05.md` Phase 2

## TL;DR

| Entry | Commit | Files changed |
|-------|--------|---------------|
| `analyst/weights-stuck-at-min` (HIGH) | `acb25ae` | `libs/core/agent_registry.py`, `services/analyst/src/main.py`, `libs/messaging/channels.py`, `tests/unit/test_dynamic_weights.py` |

## Plan accuracy

The plan's premise was inverted. It claimed the producer for `agent:closed:{symbol}` was missing and described the work as "wire the producer". Live diagnosis on the running system disproved both halves of that claim:

- **Producer is fully wired and emitting.** `services/execution/src/executor.py:243` calls `_record_agent_scores`, which seeds `agent:position_scores:{position_id}` and pushes onto `agent:outcomes:{symbol}`. On position close, `services/pnl/src/closer.py:108` calls `record_position_close`, which `XADD`s onto `agent:closed:{symbol}`.
- **Live evidence at fix time** (DB 1, Redis):
  - `XLEN agent:closed:BTC/USDT` → **3,689**
  - `XLEN agent:closed:ETH/USDT` → **956**
  - Outcome distribution on BTC stream: **9 wins / 3,680 losses / 0 breakeven** (≈0.24% win rate)
  - `agent:tracker:BTC/USDT:ta` → `ewma_accuracy ≈ 9e-24, sample_count = 497`
  - `agent:weights:BTC/USDT` → all three at 0.05

So the 0.05 weight is the **correct** EWMA result given that win rate: `weight = default × (ewma/0.5)` collapses to ~0, then clamps to `MIN_WEIGHT = 0.05`.

## Real root cause for `agent_weight_history` showing `sample_count=0`

`libs/storage/_redis_client.py` does **not** set `decode_responses=True`, so `await redis.hgetall(key)` returns `{bytes: bytes}`. Two call sites looked up fields by string name against this dict and silently fell through to the default:

- `services/analyst/src/main.py:53-54`:
  ```python
  tr = await redis_conn.hgetall(tk)
  "samples": int(tr.get("sample_count", 0)),  # always 0
  "ewma": float(tr.get("ewma_accuracy", 0)),  # always 0
  ```
  This is the **direct** cause of `agent_weight_history.sample_count=0` in persisted snapshots.

- `libs/core/agent_registry.py:124-126` (`recompute_weights`):
  ```python
  ewma = float(tracker_raw.get("ewma_accuracy", "0.5"))  # always 0.5
  sample_count = int(tracker_raw.get("sample_count", "0"))  # always 0
  last_ts = float(tracker_raw.get("last_updated", "0"))  # always 0
  ```
  Less harmful, but `last_ts=0` means every recompute pass reprocesses the entire 500-entry stream window from scratch — the EWMA still converges, just wastefully. The tracker hash gets overwritten with a fresh `sample_count = (entries-in-window)` each pass (which is why we observed 497–500 there even though analyst snapshots wrote 0).

### Fix

Added `_decode_hash` helper to `libs/core/agent_registry.py` and applied it at both call sites. `_decode_hash` returns a dict with str keys and str values; safe to call on dicts that already have str keys (idempotent).

### Other changes

- **`libs/messaging/channels.py`** — added re-exports of agent registry keys for documentation parity (per plan):
  - `AGENT_WEIGHTS = WEIGHTS_KEY`
  - `AGENT_OUTCOMES = OUTCOMES_KEY`
  - `AGENT_CLOSED_OUTCOMES = CLOSED_KEY`
  - `AGENT_TRACKER = TRACKER_KEY`

  Single source of truth stays in `agent_registry.py`; channels.py just exposes them under the project's standard "well-known channels and keys" registry.

- **`tests/unit/test_dynamic_weights.py`** — added `BytesFakeRedis` subclass that makes `hgetall` return bytes keys/values, and added `test_recompute_advances_last_ts_with_bytes_keyed_tracker`. Without the fix, this test fails because the second recompute pass with no new outcomes still mutates the tracker (it reads `last_ts=0` and reprocesses the whole stream).

## Registry diff

```
- | analyst | …weights stuck at 0.05, sample_count=0… | HIGH | M | 2026-05-05 | OPEN |
+ | analyst | …weights stuck at 0.05, sample_count=0… | HIGH | M | 2026-05-05 | **RESOLVED** (2026-05-05) — Plan premise was inverted. … 0.05 is the correct EWMA outcome … sample_count=0 was a bytes-vs-string-keys bug … Fixed _decode_hash applied at both call sites. Regression test added. |
```

## Acceptance evidence

```
$ poetry run pytest tests/unit/test_dynamic_weights.py -v
…
tests/unit/test_dynamic_weights.py::TestAgentPerformanceTracker::test_recompute_advances_last_ts_with_bytes_keyed_tracker PASSED [ 56%]
…
======================= 16 passed, 5 warnings in 1.12s ========================

$ poetry run pytest tests/unit/ -q --ignore=…  (excluding 4 pre-existing-fail files)
406 passed, 11 warnings in 19.89s
```

The plan's quantitative acceptance check (`redis-cli XLEN agent:closed:BTC/USDT ≥ 1` after a forced close) was already satisfied before the work began (XLEN was 3,689 at start). The qualitative acceptance — `agent_weight_history` rows showing `sample_count > 0` after the next recompute interval — will be observable on the next service restart, since the analyst service is currently running with the pre-fix code. Restart isn't part of this scope.

## Tangential findings

The 0.24% win rate is a strategy/data-quality concern, not tech debt. Possible contributors include:

- The data accumulated under the disabled CRISIS short-circuit fixed in Phase 1 — i.e., trades during high-volatility regimes that production policy says to abstain from. Forward-looking win rate may improve.
- The `sentiment` and `debate` agents are recorded with `score=0.0` for every entry (sample stream entry shows `"sentiment": {"direction": "BUY", "score": 0.0}`). If the upstream agents are stubbed/empty, the EWMA on those agents has no signal to learn from. **Could be worth a follow-up registry entry** if not already known. Not adding one in this session — out of plan scope.

## Out of scope (explicitly per plan)

- Resetting historical `agent_weight_history` rows. Plan §"Out of scope" says these are accurate audit history of what the system computed at the time and should remain.
- Restarting the analyst service to verify the live snapshot. Service-level restarts go through `bash run_all.sh`, not individual restarts.
