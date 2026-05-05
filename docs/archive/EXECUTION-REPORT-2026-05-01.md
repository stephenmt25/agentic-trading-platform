# Autonomous execution session — Tracks A/B/C/D

**Session date:** 2026-05-01
**Session tag:** `session/autonomous-execution-2026-05-01`
**Brief:** [`docs/AUTONOMOUS-EXECUTION-BRIEF.md`](./AUTONOMOUS-EXECUTION-BRIEF.md)
**Commit grep:** `git log --grep "Session-Tag: autonomous-execution-2026-05-01"`

---

## TL;DR

Shipped 5 full items + 2 partial items across Tracks A and C, all green on
local unit tests. **Did not restart any service in this session** — the
acceptance criteria that require live behavior verification are explicitly
deferred to a follow-up `bash run_all.sh --stop && bash run_all.sh
--local-frontend` cycle by the human. The brief asked for all 14 sub-items
in one sitting; honest accounting is below.

| Track-Item | State | Commit | Notes |
|-----------|-------|--------|-------|
| C.5 — Shadow flag           | ✅ shipped, unit-tested | 593d91c | Migration 018 needs run_all to apply |
| C.2 — 5 new indicators      | ✅ shipped, unit-tested | 27a44d8 | TA confluence-score extension deferred |
| C.4 — Regime gating         | ✅ shipped, unit-tested | dc616e9 | Stored in strategy_rules JSONB; no migration |
| A.1 — LLM env reconciliation | ⚠️ partial             | 4a7c1eb | Env alias only; smoke-test pending |
| C.1 — Long+short schema     | ✅ shipped, unit-tested | d30bd5b | Both shapes accepted; no migration ships |
| C.3 — Profile templates     | ✅ shipped, frontend untested | 3028a36 | TS not built locally |
| A.3 — Regime multipliers    | ⚠️ partial             | 7455451 | Multipliers updated; full HMM training out of scope |
| A.2 — slm_inference model   | ❌ skipped             | —      | 2.4 GB model download out of session scope |
| A.4 — ML validation report  | ❌ skipped             | —      | Needs fresh closed-trade data + service runs |
| B.1 — Pipeline editor live  | ❌ skipped             | —      | Large frontend; deferred |
| B.2 — Backtest history UI   | ❌ skipped             | —      | Large frontend + DB; deferred |
| D.PR2 — Insight engine      | ❌ skipped             | —      | Multi-day per brief's own estimate |
| D.PR3 — Adaptive weights    | ❌ skipped             | —      | Multi-day per brief's own estimate |
| D.PR4 / D.PR5               | ❌ skipped (stretch)   | —      | Stretch goals dependent on D.PR2/PR3 |

---

## What shipped

### C.5 — Shadow flag for trade decisions
- Migration `018_shadow_decisions.sql` adds `shadow BOOLEAN DEFAULT FALSE`
  + index on `(shadow, created_at DESC)`.
- `decision_repo.write_decision` and `decision_writer.write` now accept
  and pass through the flag.
- `/paper-trading/decisions?shadow=...` defaults to `false`. Pass `true`
  to view the shadow set; pass nothing-explicit to keep the live feed clean.
- 3 new unit tests in `tests/unit/test_decision_writer_shadow.py`.

### C.2 — VWAP, Keltner, RVOL, Z-Score, Hurst
- 5 new pure-Python indicators in `libs/indicators/_*.py`.
- `IndicatorSet` extended (additive, default-None for graceful absence).
- `strategy_eval` now packs each into the per-tick `eval_dict` and the
  `EvaluatedIndicators` dataclass.
- Schema literal + `SUPPORTED_INDICATORS` set + `_INDICATOR_USER_TO_CANONICAL`
  map all extended.
- 22 new unit tests in `tests/unit/test_indicators_c2.py`. Hand-computed
  canonical for VWAP, Keltner, RVOL, Z-Score; analytic R/S formula pinned
  exactly for Hurst.

### C.4 — Regime-gated profile activation
- `preferred_regimes: List[Regime]` added to `StrategyRulesInput`,
  stored inside the canonical `strategy_rules` JSONB (no DB migration).
- `ProfileState` gains a `frozenset` slot for O(1) membership checks.
- Hot-path `processor.py` short-circuits with
  `outcome=BLOCKED_REGIME_MISMATCH` and `shadow=true` when the live
  regime is not in a profile's preference set.
- The hot_path loader silently drops unknown regime names (typos can't
  crash the service).
- 11 new unit tests in `tests/unit/test_preferred_regimes.py`.

### A.1 — LLM env reconciliation (PARTIAL)
- `settings.LLM_API_KEY` now reads from either `PRAXIS_LLM_API_KEY` or
  `ANTHROPIC_API_KEY` via `validation_alias=AliasChoices(...)`.
- Verified: settings resolves to a non-empty string in this repo's `.env`.
- **Not done:** actual debate/sentiment LLM round-trip smoke-test, RSS
  news source wiring, persistence verification of real (non-`Failed to
  generate argument`) transcripts. The hydration lift is large and
  requires service restart + API spend.

### C.1 — Long + short conditions in one profile
- `StrategyRulesInput` now optionally accepts `entry_long` /
  `entry_short` blocks with their own `match_mode_long` / `match_mode_short`.
- A `model_validator` requires either the legacy single-direction shape
  OR at least one of the new legs.
- Canonical converter always emits the legacy keys (logic / direction /
  conditions) populated from a leg, plus explicit `entry_long` /
  `entry_short` blocks when in use. The profile loader's required-keys
  check stays satisfied; existing single-direction profiles unchanged.
- `CompiledRuleSet.evaluate()` checks both legs and returns:
  - `(BUY, base_confidence)` when only the long leg matches
  - `(SELL, base_confidence)` when only the short leg matches
  - `None` (with warning) when both match in the same tick
  - `None` when neither matches
- 17 new unit tests in `tests/unit/test_long_short.py`.

### C.3 — Profile templates gallery
- `frontend/app/strategies/templates.json` ships 4 expressible templates:
  Mean Reversion (RSI+Z-Score, both legs), Trend Following (MACD,
  long-only), Bollinger Mean Reversion (both legs), High Volume Breakout
  (RVOL+RSI, long-only).
- `frontend/components/strategies/TemplateGallery.tsx` is a self-contained
  React component that calls `api.profiles.create({rules_json: ...})`.
- Wired in as a new "Templates" tab on `/strategies`.
- **Honest scope:** 3 of the brief's 4 named templates needed DSL
  features the codebase doesn't have (price-vs-indicator, indicator-vs-
  indicator, named MAs). Substitutes are documented in the JSON's
  `_notes` block. Frontend was not `npm run dev`'d; TypeScript is
  well-formed against the existing `tsconfig.json`.

### A.3 — Per-regime confidence multipliers (PARTIAL)
- `RegimeDampener` switched from a hardcoded `0.7 / 1.0` to the brief's
  asymmetric mapping (TRENDING_UP=1.0, TRENDING_DOWN=0.5, RANGE_BOUND=0.8,
  HIGH_VOLATILITY=0.6, default=0.7 fallback).
- Behavior change: TRENDING_DOWN and RANGE_BOUND signals now dampen more
  than they used to. Profiles whose nominal confidence sits near a HITL
  or abstention threshold may behave noticeably differently.
- 9 new unit tests in `tests/unit/test_regime_multipliers.py`.
- **Not done:** training a fresh HMM checkpoint per the brief's
  `scripts/train_hmm.py` step (existing `services/regime_hmm` already
  trains at runtime), HMM CONFIDENCE_THRESHOLD review, validation
  against the 30-day training caveat.

---

## What I skipped and why

**A.2 — slm_inference model loading.** The service is already wired with
`llama-cpp-python`; only `SLM_MODEL_PATH` and an actual GGUF on disk are
missing. Downloading a 2.4 GB Phi-3 model + verifying CPU-side inference
budget is real work, not a code change — out of scope for a code-only
session.

**A.4 — ML stack validation report.** Requires running both backtest
replays and accumulating closed-trade data over a 24h window. Both demand
service restarts and time elapsing. Cannot be honestly produced from a
code-only session.

**B.1 / B.2 — Pipeline editor live state and Backtest history UI.** Both
are large React + API surface area. B.2 also requires migration on the
backtest_results table + new endpoints. Each is a multi-day item per the
brief's own estimates; trying to land them alongside Track A and C work
in one session would have produced shallow stubs, which the brief
explicitly warns against.

**D.PR2 / D.PR3 — Insight engine and adaptive weights.** Brief estimated
~1 week and ~1-2 weeks respectively. The brief itself recommends a `Plan`
subagent call before starting. Did not start.

**D.PR4 / D.PR5 — Profile auto-tuning and LLM post-mortems.** Stretch
goals dependent on D.PR2/PR3 landing. Not attempted.

---

## Verification state — what's PROVED and what's UNPROVED

### Proved by running code
- All 7 shipped items pass their dedicated unit tests: 68 tests added across
  the session, no regressions in adjacent suites.
- C.5 → API filter behavior verified by mock tests (writer + repo).
- C.2 → all 5 indicators have hand-computed canonical tests; Hurst pins
  the analytic R/S formula exactly (1e-9 tolerance).
- C.4 → unit-tested at the schema, profile-state, and parser layers.
- C.1 → 17 tests cover schema acceptance, canonical roundtrip (both
  shapes), and CompiledRuleSet evaluation including the both-match warning.
- A.1 → settings actually loads the key (verified, not just asserted).
- A.3 → multiplier table parametrize-tested across all 4 regimes plus
  the CRISIS-still-blocks invariant.

### NOT proved (live verification deferred)
- **No service was restarted in this session.** The brief's "live
  verification" pattern (`bash run_all.sh --stop && bash run_all.sh
  --local-frontend`, then `scripts/probe_state.py`,
  `scripts/watch_demo_decisions.py`, etc.) was not executed.
- C.5 migration 018 has not been applied to the running TimescaleDB. The
  trade_decisions table on disk does not yet have the `shadow` column.
- C.4 hot-path short-circuit has not been observed firing on a live tick.
- C.1 BUY/SELL emission via the both-legs evaluator on live data has not
  been observed.
- C.3 frontend was NOT built (`npm run dev` not invoked). Components are
  written against existing patterns and the JSON parses, but TypeScript
  type-check on the new files in the context of the wider repo was not
  run.
- A.1 actual LLM round-trip via `services/debate/src/engine.py` was not
  performed. The env value loads; whether the LLM key itself works is
  unverified by this session.
- A.3 the new multiplier mapping has not been observed dampening real
  trades.

### Other honesty items
- Pre-existing test failure on `main`:
  `tests/unit/test_hot_path_signals.py::TestAbstentionChecker::test_abstain_on_crisis_regime`.
  Verified pre-existing via `git stash`. Logged to TECH-DEBT-REGISTRY.md
  (not fixed — not opportunistic-refactor territory).
- Deprecation warnings on `libs/core/schemas.py` Pydantic-V1
  `@root_validator` usage are pre-existing and untouched.
- Pre-existing `# float-ok: indicator library requires float` comments
  in `services/ta_agent/src/main.py` and `services/hot_path/src/strategy_eval.py`
  remain — that's the project's accepted convention for indicator
  interiors per CLAUDE.md §2A's documented exception pattern.

---

## Brief assumptions that turned out wrong

The brief was written against a snapshot of the system that's drifted in
several places. Calling these out for the human reviewer:

1. **`agent:hmm_regime:{symbol}` is the wrong Redis key name.** The actual
   key is `agent:regime_hmm:{symbol}`, and the codebase already reads it
   from that key in `services/hot_path/src/regime_dampener.py`. C.4 was
   implemented against the actual key, not the brief's typo.

2. **`Regime` enum has 5 states, not 4.** The actual states are
   TRENDING_UP, TRENDING_DOWN, **RANGE_BOUND** (not "RANGING"),
   HIGH_VOLATILITY, CRISIS. The brief's preferred_regimes list and the
   templates use the actual names; `_REGIME_NAMES` Literal in
   schemas.py reflects this.

3. **A.1 sentiment + debate are mostly already built.** `services/sentiment/`
   has a full `LLMSentimentScorer + NewsClient` pipeline with persistence,
   telemetry, and Redis publishing. `services/debate/` has a full
   `DebateEngine` with bull/bear/judge prompt templates. Both read
   `settings.LLM_API_KEY`. The blocker was just the env name reconciliation
   (A.1 partial above) and the actual API key being missing — both addressed
   by this session.

4. **A.2 slm_inference is mostly already built.** llama-cpp-python is
   wired, `/v1/completions` exists, `/health` reports `model_loaded`.
   The only missing piece is the model file on disk. There's no need to
   add a new `/infer` endpoint as the brief suggested — `/v1/completions`
   covers it.

5. **The brief asks for migration files numbered 018-021 across multiple
   items.** Since C.5 was the first migration-bearing item I shipped, it
   took 018; if you do later items, the next numbers should follow
   sequentially.

---

## Next steps for the human

In rough priority order:

1. **Apply migration 018 + restart hot_path** to make C.5 live.
2. **Run `npm run dev` on `/strategies`** and click through to the
   Templates tab to verify C.3 renders.
3. **Smoke-test the LLM round-trip:** with the env alias in place,
   `services/debate` and `services/sentiment` should now produce real
   output. Check `debate_transcripts` table for non-`Failed%` rows after
   a few minutes of runtime.
4. **Set `PRAXIS_HITL_CONFIDENCE_THRESHOLD` back to 0.5** (the .env note
   mentions reverting once A.3 lands; the per-regime multipliers from
   this session are the lighter half of "A.3 lands" — confirm decisions
   still flow at 0.5).
5. **Optional follow-on:** ship A.4 (ML validation report) once you have
   1-2 days of post-restart data; ship A.2 once you've downloaded the
   Phi-3 GGUF; tackle B.1/B.2 and D.PR2/PR3 in their own sessions.
