# Execution Report — Phase 1 (Synthetic trade end-to-end harness, slim slice)

**Date:** 2026-05-05
**Plan:** `docs/EXECUTION-PLAN-CONTINUOUS-CHECKING-2026-05-05.md` Phase 1

## TL;DR

| Deliverable | Files |
|-------------|-------|
| In-process pipeline runner mirroring HotPathProcessor's gate sequence | `tests/e2e/_pipeline.py` (new) |
| Parameterised scenario matrix incl. CRISIS regression | `tests/e2e/scenarios.py` (new) |
| Replaced `assert True` placeholders with the matrix | `tests/e2e/test_happy_path.py`, `tests/e2e/test_circuit_breaker.py` |

Test count delta: e2e went from `2 placeholder passes (assert True)` → `9 real assertions across 8 scenarios`. Unit suite: `18 → 17` failed (Phase 1 of the test-failures plan removed one); no new failures introduced by this work.

## Scope reduction vs the plan

The plan estimated ~2 days for a fully-booted live-stack harness backed by
`run_all.sh --test-db`, with `pytest` fixtures booting the entire system,
nightly CI workflows, and live Redis/Timescale assertions. That scope
needs at least `run_all.sh --test-db` to exist (it doesn't yet) and a
working CI sandbox that can boot the stack — multi-session work.

This slice instead delivers an **in-process gate harness** that mirrors the
production processor's pre-validation sequence and asserts the decision at
each stage. Trade-off:

- **What's covered.** Wiring of AbstentionChecker, RegimeDampener,
  CircuitBreaker, BlacklistChecker, RiskGate. Any change that breaks one
  of these gates' short-circuit logic for a covered scenario fails the
  test immediately.
- **What's not covered.** Gates that require external systems —
  `KillSwitch` (Redis flag), `AgentModifier` (Redis weights), `HITLGate`
  (Redis approval flow), `ValidationClient` (HTTP fast-gate). Also no
  assertion on what flows out of the publisher onto Redis streams. Future
  follow-up when `run_all.sh --test-db` lands.

## Why this still catches `a08d576`

`a08d576` was the `AbstentionChecker` CRISIS short-circuit being commented
out and silently shipping. The harness has explicit `crisis-buy-abstain`
and `crisis-sell-abstain` scenarios that assert
`outcome.decision == "BLOCKED_ABSTENTION"` and
`outcome.reason contains "crisis_regime"`. If the CRISIS branch is removed
from abstention again:

- The CRISIS scenarios skip past abstention into the dampener.
- The dampener's CRISIS short-circuit (regime_dampener.py:72-73) only
  fires when the *rule-based regime indicator* returns CRISIS; in the
  harness `state.indicators` is a `MagicMock`, so `update()` returns a
  `MagicMock` that is `!= Regime.CRISIS` and the dampener treats it as a
  benign regime (multiplier 0.7).
- The pipeline progresses through the remaining gates and lands on
  `APPROVED` for benign-regime + healthy-ATR scenarios.
- Both CRISIS scenarios fail with `expected BLOCKED_ABSTENTION but got
  APPROVED`.

## Acceptance evidence

```
$ poetry run pytest tests/e2e/ -v
…
tests/e2e/test_happy_path.py::test_pipeline_scenario[crisis-buy-abstain] PASSED
tests/e2e/test_happy_path.py::test_pipeline_scenario[crisis-sell-abstain] PASSED
tests/e2e/test_happy_path.py::test_pipeline_scenario[low-atr-abstain] PASSED
tests/e2e/test_happy_path.py::test_pipeline_scenario[signal-abstain-direction] PASSED
tests/e2e/test_happy_path.py::test_pipeline_scenario[circuit-breaker-trip] PASSED
tests/e2e/test_happy_path.py::test_pipeline_scenario[blacklist-block] PASSED
tests/e2e/test_happy_path.py::test_pipeline_scenario[exposure-saturated] PASSED
tests/e2e/test_happy_path.py::test_pipeline_scenario[bull-buy-approved] PASSED
tests/e2e/test_circuit_breaker.py::test_circuit_breaker_blocks_when_daily_loss_exceeds_threshold PASSED
========================= 9 passed, 5 warnings in 0.71s =========================

$ poetry run pytest tests/unit/ -q
…
17 failed, 442 passed, 11 warnings in 29.91s
```

The 17 unit failures are the pre-existing 18 minus 1 (the Phase 1 notional
drift fix removed `test_rejects_on_concentration_limit`). All 17 are listed
in `EXECUTION-PLAN-TEST-FAILURES-2026-05-05.md` and remain out-of-scope.

## Bug-history audit (per the plan's reporting requirement)

Mapping `git log --since="90 days ago" --grep="fix("` against this harness:

| Commit | Bug | Caught by harness? |
|--------|-----|---|
| `a08d576` | AbstentionChecker CRISIS disabled | **Yes** — explicit scenarios |
| `f583ffb` | pnl_summary WRONGTYPE | No — out-of-pipeline (api_gateway) |
| `acb25ae` | Analyst tracker bytes/str | No — out-of-pipeline (analyst) |
| `bd506a4` | run_all.sh exit on empty 3000 | No — operational, out of scope |
| `8962a78` | UI dark chips | No — frontend |

1 of 5 last-90-days bugs would have been caught by this harness. The other
4 are correctly out-of-scope for a hot-path pipeline test. Severity reads:
the harness is the right shape for its scope; broader coverage (Redis
schema, learning-state drift) belongs to Phases 2–4 of the plan.

## Out of scope (deferred to follow-ups)

- `tests/e2e/_probes.py` — declarative Redis/DB probes for a future
  live-stack harness. Not built in this slice; the plan describes
  `assert_decision_written`, `assert_validation_response`, etc. but these
  need a real Redis/Timescale session to be useful.
- `tests/e2e/conftest.py` — `run_all.sh --test-db` boot fixture.
  `--test-db` flag does not exist yet on `run_all.sh`; adding it is its own
  effort.
- `.github/workflows/e2e-nightly.yml` and the `e2e-smoke` job in
  `ci.yml` — wiring on a real CI runner that can boot the stack.
- `KillSwitch`, `AgentModifier`, `HITLGate`, `ValidationClient` gate
  coverage — needs the live-stack harness above.
- Full regime × direction matrix — the current scenario set covers the
  named regression (`a08d576`) and one happy path; expanding to all five
  regimes × two directions is a follow-up session.

These are tracked as "Phase 1b" of the continuous-checking plan and can be
landed independently when the boot infrastructure exists.

## Tangential findings

- The dampener's `RegimeDampener.check()` overwrites `state.regime` based
  on a stateful indicator's update. This means tests that pre-set
  `state.regime` only affect AbstentionChecker — the dampener computes
  its own regime. Documented in `_pipeline.py`'s docstring; tests that
  want to control the dampener's perceived regime will need to mock
  `state.indicators.regime` rather than `state.regime`.
- `RegimeDampener.check()` is async even when no Redis/HMM is configured.
  Could be made sync-when-no-redis as a small ergonomic win, but not in
  scope for this work.
