# Execution Report — Phase 3 (Notional-per-allocation drift)

**Date:** 2026-05-05
**Plan:** `docs/EXECUTION-PLAN-TEST-FAILURES-2026-05-05.md` Phase 3

## TL;DR

| Cluster | Files changed |
|---------|---------------|
| `C/notional-drift` (MEDIUM) | `services/risk/src/__init__.py`, `services/hot_path/src/state.py`, `services/pnl/src/closer.py` (comment only), `docs/DECISIONS.md` (new) |

Test count delta: **6 failed → 5 failed** in the four files I ran against
(`test_pnl.py`, `test_position_closer_ledger.py`, `test_hot_path_signals.py`,
`test_risk_wiring.py`). The 5 remaining failures are Phases 2 + 4 of the
test-failures plan, untouched here.

## Plan accuracy

The plan recommended **Option B (revert risk to $10k)** with the caveat
"unless `git log` shows otherwise." I went with B but for a different
reason than the plan stated.

The plan framed the $100k value as undocumented drift. `git log` showed it
was the opposite: a deliberate session-bridge in `ddb68e5` (2026-05-01)
that bumped *two* call sites (`state.py:33`, `risk/__init__.py:60`) and
explicitly said "Revert alongside `services/risk/src/__init__.py:60` once
the session ends and either positions close or notional becomes
profile-scaled."

But the bump *missed* two other call sites:
- `services/hot_path/src/main.py:132` — the **per-profile loader** that
  computes `notional = alloc_pct × $10,000` and overrides `state.py`'s
  default. This is the binding value for hot_path's RiskGate exposure-
  at-notional check — i.e. the gate the bump was *trying* to relax.
- `services/pnl/src/closer.py:35` — the daily-realised-PnL counter
  denominator that the CircuitBreaker reads.

So the running system used **$10k for the binding RiskGate and the daily-
loss counter** but **$100k for RiskService's pre-trade concentration
check** — a 10× unit mismatch in the production code.

Revert restores internal consistency; bumping the missing two would have
also worked but would re-introduce a known regression (decision-flow
freezes when open exposure saturates the profile's notional). The
session that motivated the bump has long since ended (3,689 closed BTC
trades since), so the original justification has expired.

## Implementation

- `services/risk/src/__init__.py:60` — `Decimal("100000")` → `Decimal("10000")`; dropped the "session-bridge" trailing comment.
- `services/hot_path/src/state.py:33` — default arg `Decimal("100000")` → `Decimal("10000")`. Replaced the multi-line session-bridge comment with a single-line cross-reference comment listing the other three call sites.
- `services/pnl/src/closer.py:33-35` — value unchanged ($10k was already correct); rewrote the comment to reference all three other call sites and flag the long-term fix (derive notional from `profile.allocation_pct` alone).
- `docs/DECISIONS.md` (new) — full context, trade-off, and long-term fix path. The file did not exist; created with the standard "decisions log" preamble.

## Acceptance evidence

```
$ poetry run pytest tests/unit/test_risk_service.py -v
…
tests/unit/test_risk_service.py::TestRiskService::test_rejects_on_concentration_limit PASSED [ 55%]
…
======================== 9 passed, 5 warnings in 0.60s ========================

$ poetry run pytest tests/unit/test_pnl.py tests/unit/test_position_closer_ledger.py \
                    tests/unit/test_hot_path_signals.py tests/unit/test_risk_wiring.py -q
…
6 failed, 32 passed, 11 warnings in 2.92s
```

Pre-existing failures by file (all out-of-scope per the plan):
- `test_position_closer_ledger.py::test_closed_trade_repo_failure_does_not_raise` — Phase 2 of the plan (day-rollover delete)
- `test_risk_wiring.py::TestRiskGate::*` × 5 — Phase 4 of the plan (`_make_tick` Decimal/float mismatch)

`test_risk_service.py::test_rejects_on_concentration_limit` is no longer in
the failing set.

## Tangential findings

- The hardcoded `$10,000` constant exists in **four** places, not the two
  the plan cited. `services/hot_path/src/main.py:132` is the binding one
  in production — the `state.py:33` default fires only if no profile is
  loaded (effectively dead code). Worth a single-source helper before
  the next constant tweak; logged in DECISIONS.md as the long-term fix.
- The bump comment claimed the freeze was caused by the risk gate's
  `exposure_at_notional` check. That check lives in hot_path/RiskGate
  and reads `state.notional` from `main.py:132` (always $10k, both
  before and after the bump). The bump *did not* affect the freeze it
  claimed to fix; it only relaxed the validation service's pre-trade
  concentration check. This is a finding, not actionable here.

## Out of scope (per plan)

- Profile-scaled notional (the long-term fix) — separate effort.
- Phases 2 and 4 of the test-failures plan — independent, can land in any session.
