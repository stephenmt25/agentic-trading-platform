# Session Handoff — Test-Strategy Rollout & Open Decisions

**Date:** 2026-06-13 · **Author:** Claude Code (handler: Stevo) · **Supersedes** `NEXT-SESSION-PLAN-2026-06-14.md` as the forward pointer (its EN-W3 content carries forward as Lane 2 below). **Branch:** `feat/snappy-honest-edge` (35+ commits ahead of `main`; every CI gate green and blocking).

---

## 0 · What this session did after the debt burn-down

1. **Closed the authorable-indicator gap (API).** The strategy DSL exposed only 12 of the 19 canonical indicators; `adx`, `obv`, `choppiness`, `bb.pct_b`, `bb.bandwidth`, `bb.upper`, `bb.lower` were computed everywhere but `POST /profiles` rejected them. Extended `_UserIndicatorName` + `_INDICATOR_USER_TO_CANONICAL` (`libs/core/schemas.py`) to all 19 and aligned both frontend selectors (`StrategyEvalForm.tsx`, `NewProfileModal.tsx`, which were tighter still at 5). Parity is now pinned by `tests/unit/test_long_short.py::TestIndicatorSurfaceParity`. **All 19 indicators are now authorable via the API and the UI.** (Registry RESOLVED row + DECISIONS 2026-06-13.)
2. **Recorded the indicator-vs-constant DSL limitation** as a known design boundary (registry OPEN row, MEDIUM/L): no indicator-to-indicator, price-relative, or crossover comparison; no stateful/sequence/multi-timeframe logic; price-scale indicators are footguns under a universe-wide scalar threshold. Not a defect — a roadmap decision if a strategy family needs it.
3. **Produced three architect briefs** (md + PDF in `docs/`, regenerable via `scripts/build_md_pdf.py`):
   - `EXECUTION-BRIEF-2026-06-13-DEBT-BURNDOWN` — what the burn-down did.
   - `PARTNER-DECISIONS-BRIEF-2026-06-13` — the 6 open decisions, reasoning + options + recommendations.
   - `TEST-STRATEGY-PORTFOLIO-2026-06-13` — the 26-strategy capability/learning suite (Lane 1 below).

---

## 1 · LANE 1 (primary, ready now) — deploy the test-strategy portfolio

This is the most directly actionable lane and serves the standing goal: paper-trade diverse strategies, surface issues, and feed the freshly-reset meta-learner a varied decision-trace substrate. The full design, configs, coverage, issues watch-list, and rationale are in `docs/TEST-STRATEGY-PORTFOLIO-2026-06-13.md`. **The API extension above means all 26 strategies (including the 7 formerly canonical-only) are now creatable via `POST /profiles` — no DB hand-writing needed.**

**Execute the rollout plan (§7 of that doc):**

1. **Create paused.** `POST /profiles` with the owner token (`user_id 6322b6fa-d425-51d7-a818-088c19275228`), `is_active=false`, small `max_allocation_pct` (3–10%) so the ~20-profile aggregate can't crowd the soak or the portfolio gross budget.
2. **Activate in waves** (so an issue is attributable): **A** sanity (authorable long mean-reversion/trend) → **B** shorts + risk-lifecycle stressors → **C** adversarial + multifactor → **D** the 7 newly-authorable indicators (adx/obv/choppiness/bb.*). Watch one full cycle per wave.
3. **Add the `COV-ATR-VWAP` filler** (TEST-STRATEGY doc §4) so authorable-indicator coverage is genuinely complete (the suite as designed skips `atr`/`vwap` in actual rules).
4. **Watch, every wave** — the prioritized issues list (§5 of that doc). Highest value:
   - **Spot-short correctness** (#1): does `entry_short` open a real short paper position on a spot venue? Verify PnL sign (profits when price falls), short SL/TP precedence (SL above entry, TP below), protective-stop side, reconciliation.
   - `closed_trades.pnl_pct` `NUMERIC(10,6)` precision/overflow under tight churn (already a logged row).
   - Circuit-breaker `int()` micro-counter under-count + in-process-vs-Redis reset desync across restart/UTC rollover.
   - `close_reason` attribution under SL→TP→time precedence; never-firing/always-colliding profiles wasting CPU; ReentryGate per-(profile,symbol) isolation; correlation-cluster cap engaging with both MAJORS open.
5. **Meta-learning:** confirm the EWMA weights begin moving off `AGENT_DEFAULTS` once the OR-firehose profile clears `MIN_SAMPLES=10`; the short probes are the only SELL-side outcome source.

**Guardrails (hard):** additive only — never touch soak profile `a05adba2`; any exploratory backtest uses `profile_id=""` (latest-wins baseline); kill-switch `STOP_OPENING` is the brake (never `FLATTEN` — it would hit the soak); tear down via `is_active=false` + `deleted_at` when objectives are met.

---

## 2 · LANE 2 (strategic, partner-gated) — open decisions + EN-W3

Six decisions await the architect — full reasoning/options/recommendations in `docs/PARTNER-DECISIONS-BRIEF-2026-06-13.md`. The recommended order:

1. **Merge (6) + branch protection (4)** — merge `feat/snappy-honest-edge` → `main` via a recorded `--no-ff` PR; enable required-status-checks on the now-green `main`. Unblocks everything (main green, gates real). The one question that orders it: can the architect be a real GitHub approver?
2. **EN-W2 verdicts sign-off (2)** — accept 3, MACD kill provisional pending one coarse-timeframe re-test.
3. **Capital/fees (5)** — confirm $10k @ VIP0 (ratifies what the code does) + bundle the simulator net-of-fees fix into the first EN-W4 PR.
4. **Kill-switch operators (3)** — configure the allowlist (closes the live cross-user FLATTEN hole; prerequisite for any automated NEUTRALIZE).
5. **EN-W3 priority (1) — the big one.** Recommendation is **not** the plan-of-record substrate-first: pull EN-W4 auto-deprecation forward (cheap, the honest response to the negative-edge headline), lead EN-W3 with a **funding-carry shadow backtest**, and commit the expensive perp/multi-leg substrate (migration 025, Tokyo VM) only once that shadow shows positive net-of-cost edge. EN-W3 detail carries forward from `NEXT-SESSION-PLAN-2026-06-13.md`.

Lane 1 (test-strategy rollout) does **not** wait on these — it runs today and produces exactly the diverse, honestly-negative decision-trace substrate EN-W4's auto-deprecation machinery will need to be validated against.

---

## 3 · LANE 3 (deferred) — DSL expressiveness

The indicator-vs-constant limitation (registry 2026-06-13) is recorded, not scheduled. Revisit only when a concrete strategy family needs crossover / indicator-to-indicator / stateful logic — at which point it's a real design effort (a relational operator, per-indicator threshold normalization, stateful conditions), sequenced like any roadmap item.

---

## 4 · Verified environment facts (carry forward)

- **All 19 indicators are now authorable** via `POST /profiles` and the UI (this session). Authorable names: `rsi, atr, macd_line, macd_signal, macd_histogram, vwap, keltner.upper/middle/lower, rvol, z_score, hurst, adx, obv, choppiness, bb.pct_b, bb.bandwidth, bb.upper, bb.lower`. Comparisons: `above/below/at_or_above/at_or_below/equals`.
- **Universe:** BTC/USDT, ETH/USDT — spot only. No perp/funding/multi-leg (EN-W3). A profile trades the whole universe; scope to one symbol via the `blacklist` (exclude the others). No symbol allowlist.
- **5 regimes:** TRENDING_UP / TRENDING_DOWN / RANGE_BOUND / HIGH_VOLATILITY / CRISIS (CRISIS short-circuits to no-trade). `preferred_regimes` gates evaluation.
- **Risk limits** (bounded): `stop_loss_pct`, `take_profit_pct` ∈ (0,1]; `max_holding_hours` > 0; `max_allocation_pct`, `max_drawdown_pct`, `circuit_breaker_daily_loss_pct` ∈ (0,1]. Exit precedence SL→TP→time. Only SL/TP/time close positions.
- **Gates are BLOCKING:** mypy 0/275, ESLint 0/0, 24 integration tests, guards, black/isort/ruff, tsc, vitest. New code must stay typed + lint-clean (pre-commit mirrors). CI runs mypy via poetry for local parity.
- **Soak:** profile `a05adba2` ACTIVE and cycling (RSI<35 BUY). Health = "cycling", not a position count (the 4-OPEN baseline is obsolete). EWMA state was clean-reset; `agent:weights:*` repopulate at `AGENT_DEFAULTS` after the first new close.
- **Infra:** Redis is **DB 1** (`docker exec deploy-redis-1 redis-cli -a changeme_redis_dev --no-auth-warning -n 1 …`); TimescaleDB `docker exec deploy-timescaledb-1 psql -U postgres -d praxis_trading`. `positions.status` is UPPERCASE (`'OPEN'`). Prod FE verification on **:3000** (CORS now also allows :3002). `next dev` :3001 has a pre-existing Turbopack panic (prod path unaffected).
- **gh CLI:** `C:\Program Files\GitHub CLI\gh.exe`; token via `git credential fill`. Owner user_id `6322b6fa-d425-51d7-a818-088c19275228`. Mint a gateway JWT locally with PyJWT + `settings.SECRET_KEY` (claims: `sub`, `exp`).
- **Migration 025 RESERVED** for EN-W3 netting/margin — no migrations land before it.

---

## 5 · State of the tree

| Item | State |
|---|---|
| `feat/snappy-honest-edge` | API extension + briefs landed; every gate green/blocking; ~36 commits ahead of `main` |
| `main` | `ddf9db1` — behind; goes green at the merge (Lane 2 decision 6/4) |
| All 19 indicators authorable | **Yes** (this session) — API + UI + tests |
| Test-strategy suite | designed, ready to deploy (Lane 1) — 26 profiles, all API-authorable |
| Partner decisions | 6 pending architect (Lane 2) |
| Briefs | 3 in `docs/` (md committed; PDFs regenerable) |

## 6 · First concrete action for the next session

Start Lane 1, Wave A: create the API-authorable mean-reversion + trend-long profiles from `TEST-STRATEGY-PORTFOLIO-2026-06-13.md` §3 via `POST /profiles` (`is_active=false`, small allocation), activate, and watch one cycle for the spot-short and ledger behaviors. It needs no partner input and directly advances the test-the-system-and-let-it-learn goal.

---

*Companion docs (all 2026-06-13): the debt-burndown execution brief, the partner-decisions brief, the test-strategy portfolio.*
