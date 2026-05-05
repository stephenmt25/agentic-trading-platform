# Execution Plan — Race Window + Cooldown + Position Caps (snapshot 2026-05-05)

> **Purpose:** close the residual decision-flow concurrency holes that the
> immediate pre-bump (commit landed alongside this plan) doesn't fully fix,
> and add the strategy-shape controls the operator wanted.
>
> **Trigger:** at 18:27 UTC, hot path approved 3 BUY decisions on
> ETH/USDT in 6 seconds, opening 3 positions with combined cost basis
> $21k against a $10k notional — a clear race in the RiskGate's view of
> open exposure (`PnlSync` polls every 5s; the cluster fit inside one
> poll window). The pre-bump in `services/hot_path/src/processor.py`
> right after `OrderApprovedEvent` publish removes the 5-second blind
> spot, but operator semantics like "one trade at a time per profile"
> or "no two trades within N seconds of each other" still need explicit
> rules.
>
> **Phases are independent.** Land them in any order in their own
> sessions. Recommended order: 1 → 2 → 3 (ascending blast radius).

---

## 0 · Pre-flight context (≤10 min, shared by all phases)

Read in this order:

1. `services/hot_path/src/processor.py` lines around the `OrderApprovedEvent`
   publish — that's where the pre-bump now lives, and where any new
   timer/counter has to slot in.
2. `services/hot_path/src/risk_gate.py` — the gate. Whatever new check we
   add wants to live here (or a sibling under the same gate-call site)
   so the trace columns line up.
3. `services/hot_path/src/state.py` — `ProfileState`. New per-profile
   counters / timestamps go on its `__slots__`.
4. `services/hot_path/src/pnl_sync.py` — the 5s reconciliation that
   already keeps `open_exposure_dollars` honest. New per-profile state
   the gate consumes should be hydrated here too.
5. `tests/unit/test_risk_wiring.py` — the unit-test pattern for new
   gate behaviours.
6. `docs/DECISIONS.md` — record rationale for any tunable threshold.

**Hard rules (from CLAUDE.md):**
- Financial math uses `Decimal`; never `float()` in financial paths.
- New Redis keys/streams are added to `libs/messaging/channels.py`
  first; `redis_invariants.py` schemas updated alongside.
- `bash run_all.sh` only — never start/stop services individually.

---

## Phase 1 — Cooldown timer per (profile, symbol)

**Severity:** MEDIUM · **Effort:** S (~½ day) · **Blast radius:** hot_path
gate logic + ProfileState fields.

### Problem

Even with the pre-bump, the hot path can approve a new entry the moment
any free capital opens up. For the demo profile that means: any time a
position closes (stop-loss, take-profit, time-exit, or manual), the next
matching tick can immediately re-enter. With a strategy that's in a
true-streak (e.g. RSI oversold sustained for 30 minutes), the engine
will roll right back into the same situation.

### Goal

Configurable per-profile cooldown: after any approved order on
`(profile_id, symbol)`, block further approvals on the same key for
`cooldown_s` seconds. Default off (cooldown_s = 0) so behaviour is
unchanged; per-profile opt-in via `risk_limits.cooldown_s`.

### Files to read first

- `services/hot_path/src/risk_gate.py` — see how `RiskGateResult` carries
  blocked + reason, and how the existing checks log against `state`.
- `libs/core/models.py` — `RiskLimits` dataclass.
- `libs/core/schemas.py` — `DEFAULT_RISK_LIMITS` (string-typed for
  Decimal-safety) and any payload validators.

### Files to change

| File | Change |
|------|--------|
| `services/hot_path/src/state.py` | Add `last_approved_at: dict[symbol, float]` to `ProfileState` slots — monotonic timestamp keyed by symbol. |
| `services/hot_path/src/processor.py` | After publishing `OrderApprovedEvent`, set `state.last_approved_at[tick.symbol] = time.monotonic()`. Single line, sits next to the pre-bump. |
| `services/hot_path/src/risk_gate.py` | New check before `exposure_at_notional`: `if cooldown_s > 0 and last_seen + cooldown_s > now: return RiskGateResult(blocked=True, reason="cooldown_active")`. |
| `libs/core/models.py` / `libs/core/schemas.py` | Add `cooldown_s: float` to `RiskLimits` (default 0.0). Update `DEFAULT_RISK_LIMITS`. |
| `services/hot_path/src/main.py:_parse_static_config` | Read `cooldown_s` from `risk_limits` JSONB, default 0.0. |
| `tests/unit/test_risk_wiring.py` | Two new cases: (a) `cooldown_s=0` → never blocks. (b) `cooldown_s=60` and `state.last_approved_at['BTC/USDT']` set 30s ago → blocks with reason. |
| `tests/e2e/scenarios.py` | New scenario `cooldown-active` — pre-set `state.last_approved_at` and assert pipeline returns `BLOCKED_COOLDOWN`. |
| `docs/DECISIONS.md` | Record default = 0 (off) and the rationale. |

### Acceptance

- Profiles with `risk_limits.cooldown_s = 0` see identical behaviour to today.
- A profile with `cooldown_s = 60` cannot approve more than one trade per
  60s on the same symbol; the blocked decisions show `reason=cooldown_active`
  in the trade-decisions trace.
- Synthetic trade harness (Phase 1 of the continuous-checking plan)
  passes both the `cooldown-active` scenario and the prior matrix.

### Commit

```
feat(hot_path): per-profile (profile, symbol) cooldown gate

risk_limits.cooldown_s controls minimum seconds between approved entries
on the same (profile, symbol). Default 0 (off) so no behavioural change
unless the profile opts in. Closes the race-after-close window where a
matching strategy true-streak immediately re-fires the moment a position
clears free capital.

Plan: race-and-cooldown-2026-05-05 phase 1
```

---

## Phase 2 — Max positions per (profile, symbol) cap in RiskGate

**Severity:** MEDIUM · **Effort:** S (≤½ day) · **Blast radius:** hot_path
gate logic.

### Problem

`RiskService.MAX_OPEN_POSITIONS_PER_PROFILE` exists but lives in the
*validation* service, which runs after `RiskGate`. By the time
validation rejects the order, the hot path has already incremented its
in-memory exposure. Until `PnlSync` reconciles, the gate's view of open
exposure is too high — fine for safety but it gives a confusing trace.

More importantly, "max N positions per (profile, symbol)" is a different
constraint than "max total cost basis ≤ notional". Two scenarios that
both pass the notional check but differ on intent:
- One $10k position vs ten $1k positions on ETH/USDT — same exposure,
  very different operational posture.
- Operator wants "no pyramiding": one open position on a symbol at a
  time, period.

### Goal

Per-profile `risk_limits.max_positions_per_symbol: int` (default
`unlimited` = `None`). When set, `RiskGate` consults
`state.open_exposure_dollars` AND `state.open_positions_count[symbol]`
and blocks with `reason=max_positions_reached` when the count would
exceed the cap.

### Files to change

| File | Change |
|------|--------|
| `services/hot_path/src/state.py` | Add `open_positions_count: dict[symbol, int]` slot. |
| `services/hot_path/src/pnl_sync.py:_poll_reconciliation` | Populate `state.open_positions_count` from `position_repo.get_open_positions(profile_id=pid)` (already queried for exposure — same loop). |
| `services/hot_path/src/processor.py` | Pre-bump the count next to the exposure pre-bump. |
| `services/hot_path/src/risk_gate.py` | Check after cooldown, before exposure check: `count >= max → block`. |
| `libs/core/models.py` / `libs/core/schemas.py` | `RiskLimits.max_positions_per_symbol: Optional[int]`. |
| Tests | Unit + e2e scenario `max-positions-reached`. |

### Acceptance

- Profile with `max_positions_per_symbol=1` opens one position, then every
  subsequent decision shows `reason=max_positions_reached` until the
  position closes.
- Profile without the cap behaves identically to today.

### Commit

```
feat(hot_path): max_positions_per_symbol cap in RiskGate

Per-profile per-symbol position-count cap, separate from notional-based
exposure. Defaults to None (no cap) so existing behaviour is preserved.
Useful for "no pyramiding" profiles where the operator wants one open
position per symbol regardless of remaining free capital.

Plan: race-and-cooldown-2026-05-05 phase 2
```

---

## Phase 3 — Strategy-level minimum-bars-between-trades

**Severity:** LOW · **Effort:** S (≤½ day) · **Blast radius:** strategy
compiler + StrategyEvaluator.

### Problem

A profile rule that's in a true-streak (e.g. RSI < 30 for 20 minutes
straight) will match on every tick. Cooldown (Phase 1) and the
position-count cap (Phase 2) protect the system from over-trading, but
they don't tell the strategy "this is the same setup, don't keep firing."
A bar-count gate on the strategy side is the natural home for that.

### Goal

`strategy_rules.min_bars_between_trades: int` (default 0). The
`StrategyEvaluator` skips evaluation entirely on the symbol's price
chart for `min_bars_between_trades` bars after the most recent approval
on that symbol.

### Files to change

| File | Change |
|------|--------|
| `services/strategy/src/compiler.py` | Add `min_bars_between_trades` to `CompiledRuleSet` with default 0. |
| `services/hot_path/src/strategy_eval.py` | Track `last_approved_bar` per symbol on `ProfileState`; in `evaluate`, skip when `current_bar - last_approved_bar < min_bars_between_trades`. |
| `services/hot_path/src/processor.py` | Update `last_approved_bar` next to the cooldown timestamp set. |
| `tests/unit/test_strategy_eval.py` | Two cases: 0 = always evaluate; 5 = skips first four bars after an approval. |

### Acceptance

- A profile with `min_bars_between_trades=10` produces approvals at
  most every 10 bars on a given symbol even if the strategy matches
  every bar.
- A profile with `min_bars_between_trades=0` (the default) behaves
  identically to today.

### Commit

```
feat(strategy): min_bars_between_trades skip in StrategyEvaluator

Per-profile setting on strategy_rules; evaluator returns no-signal for
N bars after each approval on a given symbol. Defaults to 0 (off)
preserving existing behaviour. Targets the case where a strategy rule
sits in a sustained true-streak and approves on every tick — cooldown
(time-based) is the gate's protection, this is the strategy's.

Plan: race-and-cooldown-2026-05-05 phase 3
```

---

## Out of scope for this plan

- "Pyramiding allowed up to N positions" with custom sizing per layer —
  the position-count cap (Phase 2) gives a binary version of this; full
  pyramiding semantics would need a separate strategy mode.
- Risk service rate-limiting (validation-side) — already exists, not
  in the hot path.
- Per-symbol exposure caps independent of notional — the existing
  notional gate is per-profile; if you want "max $5k in BTC, max $5k
  in ETH" out of a $10k profile, that's a fourth phase here, not built
  in.

---

## Reporting

After **each phase** write a short report
`docs/EXECUTION-REPORT-RACE-AND-COOLDOWN-phase<N>-<YYYY-MM-DD>.md`
summarising:
- The new gate / counter / timer added.
- Test command output proving the synthetic harness still passes.
- Any tangential findings, logged as new registry entries.
