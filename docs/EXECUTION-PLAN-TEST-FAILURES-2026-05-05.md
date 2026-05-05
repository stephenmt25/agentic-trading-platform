# Execution Plan — 18 pre-existing unit-test failures (snapshot 2026-05-05)

> **Purpose:** Self-contained brief for fresh Claude Code sessions to clear
> the 18 unit-test failures that have been failing on `main` since at least
> 2026-05-01 (verified pre-existing by `git stash` during the
> 2026-05-05 tech-debt session). Each phase is independent and can run in
> a separate session. Recommended order is by ascending risk: test-only
> fixes first (Phases 1, 2, 4), real production-bug fix last (Phase 3).

After running these phases, `poetry run pytest tests/unit/ -q` should report
zero failures (currently: 18 failed / 440 passed).

---

## 0 · Pre-flight context (≤10 min, shared by all phases)

Read in this order:

1. `CLAUDE.md` — financial precision (Decimal everywhere), hooks, anti-patterns
2. The current failure inventory (run once and tail to confirm scope hasn't shifted):
   ```
   poetry run pytest tests/unit/test_debate.py \
                     tests/unit/test_position_closer_ledger.py \
                     tests/unit/test_risk_service.py \
                     tests/unit/test_risk_wiring.py --tb=short -q
   ```
3. `libs/core/models.py` — note `price: Price` where `Price = Decimal` in `libs/core/types.py`
4. `libs/core/types.py` — type aliases (`Price`, `Quantity` etc. are all `Decimal`)

**Hard rules (from CLAUDE.md):**
- Financial values use `Decimal`; never `float()` in financial paths
- New Redis keys/streams must be added to `libs/messaging/channels.py` first (none of the phases below add new ones)
- The `stale-read-guard.sh` hook blocks edits to files not Read in this session
- Don't fix unrelated tech debt opportunistically — append to the registry

**Commit message convention:**
```
fix(<service-or-tests>): <subject>

[body — what changed and why]

Test-Failure-Cluster: <cluster letter>/<short-tag>
```

---

## Phase 1 — Update debate test mocks for the `grammar` kwarg

**Severity:** LOW (test-only) · **Effort:** S (≤30 min) · **Blast radius:** test file only

### Problem

`services/debate/src/engine.py:23-24` defines:
```python
class LLMBackend(Protocol):
    async def complete(self, prompt: str, grammar: Optional[str] = None) -> Optional[str]:
```

The `grammar` keyword was added to the protocol when GBNF-grammar-constrained
generation was wired in (engine.py lines 150, 162, 187 all call `complete(...,
grammar=_ARGUMENT_GBNF)` or `_JUDGE_GBNF`). The 11 mock backends in
`tests/unit/test_debate.py` (`MockBackend`, `FailingBackend`, `GarbageBackend`,
`ExtremeBackend`, …) still define `async def complete(self, prompt)` without
the `grammar` kwarg, so every test invocation crashes with:

```
TypeError: <Mock>.complete() got an unexpected keyword argument 'grammar'
```

This is a **mock-drift** issue, not a production bug — the real backends already
implement the new signature.

### Files to read

- `services/debate/src/engine.py` — confirm the protocol signature (lines 23-24) and confirm the 3 call sites all pass `grammar=...` as a kwarg
- `tests/unit/test_debate.py` — full file. Each mock backend class has its own `complete` definition; count them. Expected ~5–6 distinct mocks across 11 tests.
- Find at least one production backend implementation (`grep -rn "def complete" services/ | grep -v test`) to confirm the signature being mirrored. If multiple production backends agree on `complete(self, prompt: str, grammar: Optional[str] = None)`, that's the contract to mirror.

### Files to change

| File | Change |
|------|--------|
| `tests/unit/test_debate.py` | For every nested mock backend class with `async def complete(self, prompt)`, change to `async def complete(self, prompt, grammar=None)`. The test logic doesn't need to use `grammar` — accepting and ignoring is fine for these tests. If any test specifically wants to verify grammar is passed (search for `assert grammar` or similar), add explicit `grammar` capture. Likely none do. |

### Acceptance

- `poetry run pytest tests/unit/test_debate.py -v` passes 11 tests
- No other test newly fails: `poetry run pytest tests/unit/ -q` shows -11 failures from baseline (i.e. baseline 18 → 7)

### Commit

```
fix(tests): debate mocks accept grammar kwarg

LLMBackend.Protocol added grammar: Optional[str] = None when GBNF-constrained
generation was wired in (services/debate/src/engine.py:23-24, 150, 162, 187).
The mock backends in tests/unit/test_debate.py still defined complete(self,
prompt) — every call from engine.run() raised TypeError. Updated all 5–6
mock classes to accept the kwarg.

Test-Failure-Cluster: A/debate-grammar-kwarg
```

---

## Phase 2 — Reconcile `test_closed_trade_repo_failure_does_not_raise` with day-rollover branch

**Severity:** LOW (test-only) · **Effort:** S (≤30 min) · **Blast radius:** test file only

### Problem

`tests/unit/test_position_closer_ledger.py:196` asserts
`redis_client.delete.assert_awaited_once()`. Currently fails:
```
AssertionError: Expected delete to have been awaited once. Awaited 2 times.
```

Production code `services/pnl/src/closer.py` calls `self._redis.delete` in
**two** distinct paths:

1. Line 134 — `await self._redis.delete(f"agent:position_scores:{position.position_id}")` after every close (snapshot cleanup)
2. Line 186 — `await self._redis.delete(key)` inside `_bump_daily_realised_pnl` when the stored `date` field doesn't match today (day-rollover counter reset)

The day-rollover branch was added after the test was written. In tests where
`redis_client.hget(key, "date")` returns `None` (default `AsyncMock`), the
code interprets that as a date mismatch and fires the second `delete`.

### Files to read

- `services/pnl/src/closer.py` — full file, focus on lines 96-104 and 160-195 to understand the daily-counter flow
- `tests/unit/test_position_closer_ledger.py` — full `TestCloseEndToEnd::test_closed_trade_repo_failure_does_not_raise` (and the surrounding two tests at lines 145-160 and 185-215 that have similar setups). Note the AsyncMock fixture for `redis_client`.

### Files to change

| File | Change |
|------|--------|
| `tests/unit/test_position_closer_ledger.py` | Two compatible options — pick one and apply consistently across all three TestCloseEndToEnd tests that use `redis_client.delete.assert_awaited_once()` (if multiple): **(a)** pre-seed `redis_client.hget.return_value = today_iso_string` so the day-rollover branch is skipped, then keep `assert_awaited_once`; **(b)** change the assertion to `assert redis_client.delete.await_count == 2` (snapshot key + daily-counter key) and add an `assert_any_await(call(f"agent:position_scores:{pid}"))` to verify the snapshot cleanup specifically still happened. Option (b) is more honest about current behaviour; option (a) is closer to the test's original intent. |

### Acceptance

- `poetry run pytest tests/unit/test_position_closer_ledger.py -v` passes
- No other test newly fails: `poetry run pytest tests/unit/ -q` shows -1 failure from prior phase

### Commit

```
fix(tests): account for day-rollover delete in closer ledger tests

services/pnl/src/closer.py now calls redis.delete twice in the close path —
once for the position-scores snapshot (line 134) and once inside
_bump_daily_realised_pnl when the stored date != today (line 186). The day-
rollover branch was added after the test was written, so assert_awaited_once
no longer matches reality. Updated the assertion to match production
behaviour.

Test-Failure-Cluster: B/closer-double-delete
```

---

## Phase 3 — Reconcile notional-per-allocation constants between `risk` and `pnl`

**Severity:** MEDIUM (real cross-service drift) · **Effort:** M (~1 hour) · **Blast radius:** production code in two services

### Problem

`tests/unit/test_risk_service.py::TestRiskService::test_rejects_on_concentration_limit`
fails with `assert True is False`. The test seeds:
- profile `allocation_pct = "1.0"`
- one open BTC position worth $2,000 (qty=0.04, entry=$50,000)
- new order for $2,000

…and asserts the resulting concentration triggers the 25% block. The check
fails because the production code currently treats `allocation_pct = 1.0` as
**$100,000** of portfolio value (`services/risk/src/__init__.py:60`):
```python
portfolio_value = Decimal(str(profile.get("allocation_pct", 1.0))) * Decimal("100000")
```

So new exposure $4,000 / portfolio $100,000 = 4%, well under the 25% limit.

But `services/pnl/src/closer.py:33-35` documents and uses **$10,000**:
```python
# Notional capital per allocation unit. Mirrors services/risk/__init__.py:60
# (allocation_pct × 10,000) — keep in sync if that constant moves.
_NOTIONAL_PER_ALLOC_UNIT = Decimal("10000")
```

The closer's comment claims it mirrors risk, but the constants disagree by a
factor of 10. **One of these two services is wrong** about how much real
capital the user actually has — that affects:
- the daily-loss circuit breaker (closer writes `total_pct_micro` against
  $10k notional; risk's check uses $100k portfolio — mismatch in unit)
- concentration limits
- max-allocation-per-trade caps

### Files to read

1. `services/risk/src/__init__.py` — full file; pay attention to line 60 and how `portfolio_value` is used downstream (allocation cap line 67-72; concentration line 86-101)
2. `services/pnl/src/closer.py:33-189` — confirm the $10k constant is used to compute `equity_fraction` for the circuit-breaker counter
3. `services/hot_path/src/state.py:32` (referenced in risk's comment) — find where notional is derived in the hot-path's `ProfileState.notional`. This is the third candidate source of truth.
4. `tests/unit/test_risk_service.py::TestRiskService::test_rejects_on_concentration_limit` lines 79-99 — note the test comment says "$10k portfolio". The test was written when the constant was $10k.
5. `git log -p services/risk/src/__init__.py` for the line that became `* Decimal("100000")` — find the commit that changed the constant and read its message for original justification.

### Decision: which value is correct?

Three viable resolutions:

**Option A — keep risk at $100k, fix closer + test.** Pick this if `git log` shows the change to $100k was deliberate (e.g. a sprint where the team simulated a larger account). Update closer.py's constant and comment to $100k; update the test's expectation.

**Option B — revert risk to $10k.** Pick this if the change to $100k was unintentional or undocumented. Closer.py's comment becomes truthful again, the test passes without modification.

**Option C — derive notional from a single shared source** (e.g. `state.notional` already exists in hot_path). Highest correctness, biggest scope. Defer unless the `git log` reveals real disagreement about what value is intended.

Recommend **B** unless the `git log` shows otherwise — the closer's comment and the test both anchor at $10k, suggesting that was the design and the risk-side constant drifted. Document the choice in `DECISIONS.md` either way.

### Files to change (Option B path; Option A is the inverse)

| File | Change |
|------|--------|
| `services/risk/src/__init__.py:60` | Replace `Decimal("100000")` with `Decimal("10000")`. |
| `tests/unit/test_risk_service.py` | No change. The test was already correct. |
| `docs/DECISIONS.md` | Append: "2026-05-XX — risk service notional-per-allocation reverted from $100k to $10k to match services/pnl/src/closer.py and the documented contract. The $100k value was undocumented drift." |

If `git log` mandates **Option A** instead, change `services/pnl/src/closer.py:35` to `Decimal("100000")` and update the test's expected concentration calculation, plus the closer.py:33-35 comment to reference 100,000.

### Acceptance

- `poetry run pytest tests/unit/test_risk_service.py -v` passes
- `poetry run pytest tests/unit/test_pnl.py -v` still passes (the closer's daily-counter math)
- `poetry run pytest tests/unit/ -q` shows -1 failure from prior phase
- `DECISIONS.md` records the chosen option

### Commit

```
fix(risk): align notional-per-allocation with closer.py contract

services/risk/src/__init__.py:60 used Decimal("100000") while
services/pnl/src/closer.py:35 used Decimal("10000") — the closer's comment
explicitly claimed it mirrored risk. Reconciled to $10k as the documented
value. Affected: concentration check now blocks at the documented 25%
threshold; circuit-breaker total_pct_micro and risk's portfolio_value now
share a unit.

Test-Failure-Cluster: C/notional-drift
```

---

## Phase 4 — Convert `RiskGate` test fixtures to Decimal

**Severity:** LOW (test-only) · **Effort:** S (≤30 min) · **Blast radius:** test file only

### Problem

5 `TestRiskGate` cases fail with:
```
TypeError: unsupported operand type(s) for /: 'decimal.Decimal' and 'float'
  at services/hot_path/src/risk_gate.py:69 — qty = trade_dollars / price
```

`trade_dollars` is `Decimal` (computed from `Decimal`-typed risk-limit fields).
`price` comes from `tick.price`. The production `NormalisedTick.price` is
typed `Price` which is `Decimal` per `libs/core/types.py`. But the test
fixture `_make_tick()` at `tests/unit/test_risk_wiring.py:43-46` builds the
tick with `price=50000.0` (a Python float). Python dataclass without
validators happily accepts the float; the type mismatch only manifests when
production code actually does Decimal arithmetic on it.

### Files to read

- `tests/unit/test_risk_wiring.py:43-46` — the `_make_tick()` fixture
- `libs/core/models.py:19-23` — `NormalisedTick` dataclass definition
- `libs/core/types.py` — confirm `Price = Decimal`
- `services/hot_path/src/risk_gate.py:69` — confirm `trade_dollars` is computed from Decimal-typed inputs

### Files to change

| File | Change |
|------|--------|
| `tests/unit/test_risk_wiring.py:43-46` | Change `price=50000.0` to `price=Decimal("50000")` and `volume=1.0` to `volume=Decimal("1")` (per `Quantity = Decimal`). Add `from decimal import Decimal` if not already imported (it is, line 5). |

### Acceptance

- `poetry run pytest tests/unit/test_risk_wiring.py -v` passes (5 tests that use `_make_tick()` plus all `TestCircuitBreaker` ones)
- `poetry run pytest tests/unit/ -q` shows zero failures (assuming all prior phases applied)

### Commit

```
fix(tests): _make_tick uses Decimal for price/volume

NormalisedTick.price/volume are typed Decimal (libs/core/types.py). The test
fixture in tests/unit/test_risk_wiring.py:43-46 was passing Python floats,
which the dataclass silently accepted. The mismatch only surfaced once
RiskGate.check started doing Decimal arithmetic with tick.price (qty =
trade_dollars / price at services/hot_path/src/risk_gate.py:69), causing
TypeError on every TestRiskGate case.

Test-Failure-Cluster: D/risk-gate-tick-decimal
```

---

## Reporting

After **each phase** (not at the end of all four), write a short
`docs/EXECUTION-REPORT-TEST-FAILURES-<phase>-<YYYY-MM-DD>.md` with:

- TL;DR table — cluster resolved, commit SHA, lines changed
- Test-count delta — `<before> failed → <after> failed`
- Any tangential findings logged as new registry entries (don't fix them)

If a phase reveals the failure is something other than what's described
(e.g. Phase 3 `git log` shows the $100k value was deliberately documented
elsewhere), note that and adjust the resolution rather than blindly applying
the recommended option.

---

## Out of scope for this plan

- The 5 Pydantic deprecation warnings about `@root_validator` and `Field(..., example=...)`. Real but harmless until Pydantic v3.
- The `datetime.utcnow()` deprecation warnings in `tests/conftest.py:256`.
- New test coverage for the analyst weight engine, frontend, or any other untested path. This plan only fixes existing failures.

---

## Final acceptance (after all four phases)

```
$ poetry run pytest tests/unit/ -q
…
458 passed, 11 warnings in <30s>
```

(Baseline 2026-05-05: 440 passed, 18 failed.)
