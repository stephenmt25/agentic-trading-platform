# Risk-Truth Hardening — Decision Brief

> **For:** architecture review (partner sign-off)
> **From:** Claude Code, via Stevo
> **Date:** 2026-06-02
> **Purpose:** Verify `docs/algo-strategy-signal-taxonomy.md` against the actual codebase, surface discrepancies, and frame the decisions we need to make together before writing code.
> **Companion docs:** `docs/algo-strategy-signal-taxonomy.md` (the audited doc), `docs/PLATFORM_VIABILITY_PLAN_2026-05-18.md` (the active roadmap), `docs/STRATEGY_GAP_ANALYSIS.md`, `docs/risk-management.md`.
> **Stance:** This *complements* the Viability Plan — it does not replace it. The Viability Plan is strategy-first (cloud → primitives → Yield Harvester → Mean Reverter). This brief defines the **risk-truth layer** that should land *before any strategy goes live*, and which also makes paper-trading honest enough to learn from.

---

## 0 · TL;DR (read this if nothing else)

We verified the federated-architecture document against the code with 16 parallel investigators, each finding adversarially re-checked by a second agent with file:line evidence. The doc is **directionally right but written for a generic naive monolith**. Three things matter:

1. **The doc's headline assumption is inverted.** It warns your most dangerous line is `if drawdown: close_all()` (an over-eager market dump). **That line does not exist.** The real problem is the opposite and was never anticipated by the doc: **when a position "closes," it only updates the database — it never sends a closing order to the exchange.** In paper mode this is invisible. In live mode, every stop-loss/take-profit/time-exit would be a *phantom close*: our books say flat, the exchange still holds the position. This is the single most important finding. *(File: `services/pnl/src/closer.py:53-133`.)*

2. **Two things the doc tells us to build are already done** — the LLM/agent tier is already strictly below the deterministic risk floor (Tier 0.3 ✅), and regime gating is already weight-based, not on/off (the hard part of Tier 2.11 ✅). We should not re-solve these.

3. **It's all paper trading right now — zero real money at risk.** That reframes urgency: the taxonomy doc's "money-at-risk first" tier-0 isn't "your account is about to blow up," it's **"these gaps block a safe live launch AND corrupt the learning data you're trying to collect."** Given our goal (a system that learns from honest ground-truth and goes live only when proven), the risk-truth layer is *also* a data-quality investment, not just a safety one.

The ask: agree the **Risk-Truth Hardening** slice below, decide the **flatten-authority policy** (the one genuine open architecture question for an autonomous system), and pick the **branch/CI model**.

---

## 1 · How we verified

- Read `algo-strategy-signal-taxonomy.md` in full (11 parts, Tier 0–3 correction roadmap).
- Decomposed it into 16 claim-clusters (each Tier item + the signal taxonomy + the federation structure).
- For each: one agent investigated the *actual code* and returned a verdict; a second agent **adversarially re-checked** it (default to disproving "already done" claims; hunt for where "missing" things actually live). Every verifier agreed with its investigator, with only minor refinements.
- Cross-checked against the existing in-repo audits (`STRATEGY_GAP_ANALYSIS.md`, `risk-management.md`) — and in two places the code proved *those* docs wrong too (noted below).

---

## 2 · Findings — the full map

Verdict legend: ✅ already done · ◐ partial · ✗ missing · ⚠︎ doc mischaracterizes current state.
Severity is rated **at live trading** (today, in paper mode, the at-risk dollar amount is zero).

| Doc item (Tier) | Verdict | Sev @ live | What's actually true | Evidence |
|---|---|---|---|---|
| **0.1** Tiered kill-switch verbs (vs binary `close_all`) | ⚠︎ | High | Kill switch is binary **but stop-opening only** — it blocks *new* orders and never flattens. No `close_all()` exists. No tiered verbs, no liquidity-aware (TWAP) flatten. | `hot_path/kill_switch.py:34-79`; `processor.py:121-127` |
| **0.2** Exchange-level loss caps / reduce-only / pre-placed stops | ✗ | **Critical** | All risk is software-only and pre-trade. `place_order` hardcodes `type='limit'` with no `reduceOnly`/`stopLoss`/bracket params; the adapter contract can't even express an exchange-side protective order. | `_binance.py:237-249`; `_base.py:77-80` |
| **0.3** Agent/LLM strictly below the deterministic risk floor | ✅ | Low | Already true. Agents only nudge confidence within a clamped band; all hard gates (kill switch, circuit breaker, risk gate, validation) run agent-independently. *(One bounded nuance: an agent confidence boost can suppress the discretionary HITL review trigger — but HITL is off by default and isn't a hard rail.)* | `agent_modifier.py:70-92`; `risk_gate.py:42-69` |
| **0.4** Stress-correlation portfolio limits + per-venue caps | ✗ | High | No correlation model of any kind. Concentration is a flat 25% cap evaluated **per symbol, per profile, in isolation** — N correlated alts each at ~24% all pass. `positions` doesn't even store venue. | `risk/src/__init__.py:87-102` |
| **0.5** Net-of-cost accounting (fees + funding + slippage) | ◐ | High | Fees *are* subtracted from realized PnL — but they're **estimated from a 3-row hardcoded table**, not read from the exchange. **Funding is entirely absent** (0 hits repo-wide). Slippage is baked into paper fills, never attributed. No per-strategy net rollup; nothing auto-kills a net-negative strategy. | `pnl/calculator.py:33-42`; `executor.py:26-31,296` |
| **1.6** Single position book + continuous exchange reconciliation + drift alarms | ◐ | High | `BalanceReconciler` exists and is genuinely **balance-based** (not order-based as `STRATEGY_GAP_ANALYSIS.md:116` wrongly claims) — but it's **dead-wired**: constructed with `profile_repo=None`, so it early-returns on every 5-min tick. Drift-alarm publish is also gated on a `None` pubsub. Position truth = the `positions` DB table, mirrored in PnL's in-memory cache. No exchange-side reconciliation runs. | `execution/reconciler.py:37-41`; `execution/main.py:52` |
| **1.7** Tag positions by horizon/lineage; forbid cross-horizon netting | ✗ (premise N/A) | Medium | No lineage/horizon tag. But the doc's "silent netting" fear doesn't apply today: `ReentryGate` **hard-blocks** a 2nd position on a symbol, and it's one strategy per profile — so "short-horizon flattens long-horizon" can't happen. Becomes real only with multi-strategy-per-symbol. | `reentry_gate.py:22-27`; migration `001:45-57` |
| **1.8** Isolate leveraged engine into a sub-account | ⚠︎ | Low | System is **100% spot** — no leverage, margin, or sub-accounts exist anywhere; `max_leverage` is dead config. The doc's contagion fix is explicitly leverage-conditional, so it's *not-yet-applicable*, not wrong. | `_binance.py:39-45`; grep leverage/margin = 0 |
| **1.9** Decide & document flatten-authority | ✗ | Medium | The root `DECISIONS.md` is an empty template. The taxonomy doc's open question (auto-flatten unattended vs human-only) is unrecorded. **This is a decision, not code — and it's squarely an architecture call (see §6).** | `DECISIONS.md:1-8` |
| **2.11** Regime = weight-based **+ hysteresis** | ◐ | High | Weight-based dampening **is implemented** (the doc's prescribed fix — continuous per-regime multipliers, CRISIS as the only hard stop). **Hysteresis is absent**: regime classifiers use single hard thresholds with no prior-state memory → boundary thrash, exactly what the doc warns about. | `regime_dampener.py:28-76`; `regime_mapper.py:43-56` |
| **2.12** Macro overlay / gross-exposure budget | ✗ | High | Sizing is strictly per-profile; there is no portfolio-wide gross-exposure budget or risk-on/off bias. | `risk_gate.py:34-70`; `state.py:55-60` |
| **2.13** Separate latency vs patient execution paths | ✗ | Medium | One `stream:orders`, one executor consumer group, one `place_order` call site. No fast/slow split, no maker/taker or TWAP routing. | `executor.py:198,279`; `channels.py:9-19` |
| **3.14** Decay detection / live-vs-backtest / walk-forward | ✗ | High | Backtester is pure in-sample (sweeps reuse one window — textbook overfit). No walk-forward, no look-ahead/survivorship guards, no live-vs-backtest comparison, no auto-deprecation. The "shadow decision" flag is recorded but **nothing consumes it** (its intended PR is unbuilt). | `vectorbt_runner.py:351-396`; `processor.py:302-320` |
| **3.15** Capital allocator (strategic, risk-adjusted) | ✗ | Low | Capital per profile = manual `allocation_pct × $10k` constant. No cross-strategy allocator. | `notional.py:21,68` |
| **Part 1** Signal-family coverage (A–K) | ◐ | Medium | A (trend) + B (mean-reversion) solid; C (vol) + D (volume) thin; **E/F/H/I/J have no data plane** (no orderbook-derived signal, no arb, no on-chain, no funding/OI, no seasonality); G (sentiment) + K (ML/regime) partial. Notably, regime-awareness — the column the doc says everyone omits — is our **strongest** axis. | `indicators/__init__.py`; `strategy_eval.py:73-103` |
| **Part 2** Federation (3 engines) | ◐ | Low | Pure monolith decision core (single `HotPathProcessor` loop). Only the **E2 (Tactical)** role exists; E1 (microstructure) and E3 (positioning/macro) are absent/aspirational. | `processor.py:161-460`; `run_all.sh:229-263` |

### Two in-repo docs the code proved wrong (worth fixing while we're here)
- `STRATEGY_GAP_ANALYSIS.md:116` calls `reconciler.py` an *order* reconciler. It's actually a *balance* reconciler — just dead-wired.
- `CLAUDE.md` Service Map says **"strategy → pub `stream:orders`"**. False — the strategy service is a 60s compile-loop (`strategy/main.py:55-131`); the real order emitter is `hot_path`. Also `oracle` (a 20th service, port 8097) is missing from CLAUDE.md's "19 services" list.

---

## 3 · The finding that needs your eyes first — "phantom close"

`PositionCloser.close()` does only: update the DB row to `CLOSED`, compute PnL at the exit price *passed in by the caller*, write the `closed_trades` audit row, bump the daily-PnL counter. **It calls no exchange adapter.** The API route is candid about it (`positions.py:233-237`): *"in live mode the real position on the exchange remains open and must be flattened separately."*

Why this is the priority:

- **It blocks safe live trading outright.** A stop-loss that doesn't actually sell is not a stop-loss.
- **It corrupts the learning substrate** — which is the part that matters for *our* goal. Realized PnL is computed against a price we chose, not a fill we got. If the system is meant to learn from ground-truth, phantom closes feed it fiction.
- **It's silent.** Paper mode hides it completely; it would only reveal itself the first time real money is on the line.

This is exactly the class of nuance that's hard to catch when a codebase is built conversationally — the *happy path* (open → mark-to-market → DB close) looks complete, and the missing exchange leg only matters in a mode we haven't run yet.

**Design choices for the fix (architect input welcome):** route closes through the existing execution service / OMS as a `reduce-only` order (preferred — one order path, reconcilable), vs. a dedicated flattener. Paper/testnet stays a simulated fill; live emits a real reduce-only order; the DB close happens *on fill confirmation*, not before.

---

## 4 · How this complements the Viability Plan

The Viability Plan (2026-05-18) is the spine and stays intact. Its **Phase 3 ("risk + ops maturity, before any strategy goes live")** already names three of our items: a portfolio-risk aggregator, a defense-in-depth kill-switch check in the executor, and a balance reconciler. This brief does three things to that:

1. **Fills Phase 3 out** with what the taxonomy doc adds: the phantom-close fix, tiered kill-switch verbs + stress-correlation limits + funding-aware cost + regime hysteresis + decay tracking.
2. **Promotes the phantom-close + reconciler-wiring earlier**, because they corrupt paper fidelity *now* (Phase 0/1 measurement), not just live readiness.
3. **Explicitly defers** the federation structure, sub-accounts, and capital allocator to Phase 2 (they're low severity and premature for single-engine spot).

No conflict with the strategy phases — this is the safety/fidelity layer they're meant to sit on.

---

## 5 · Proposed slice — "Risk-Truth Hardening"

Each row is one reviewable PR. Ordered by (a) impact on paper-fidelity/learning and (b) live-safety. All keep `Decimal`, honor existing CLAUDE.md conventions, and are paper-safe by default.

| PR | Title | Closes | Why now |
|----|-------|--------|---------|
| **0** | SDLC scaffolding | — | Branch, PR template, CODEOWNERS, CONTRIBUTING/branch-strategy, `.pre-commit-config.yaml` mirroring CI, consolidate `DECISIONS.md`. Reusable for the next project. |
| **1** | Real exchange close (kill phantom close) | 0.2 (partial), fidelity | Route `PositionCloser` through the OMS as reduce-only; DB close on fill. **The critical fix.** |
| **2** | Wire `BalanceReconciler` + live drift alarms | 1.6 | Inject `profile_repo`+`pubsub`; run on testnet; alarm on drift. |
| **3** | Tiered kill-switch verbs + record flatten-authority decision | 0.1, 1.9 | stop-opening → de-risk → (policy-gated) flatten; document the §6 decision in `DECISIONS.md`. |
| **4** | Aggregate/portfolio risk + stress-correlation concentration | 0.4, 2.12 | Cross-profile gross-exposure budget; correlation-aware concentration. Merges the Viability Plan's "portfolio risk aggregator". |
| **5** | Funding-aware, per-strategy net-of-cost accounting | 0.5 | Add funding accrual + realized-slippage attribution; per-strategy net rollup → the honest number the learning loop needs. |
| **6** | Regime hysteresis | 2.11 | Separate enter/exit thresholds + prior-state memory to stop boundary thrash. |
| **7** | Live-vs-backtest decay tracking | 3.14 | Consume the existing shadow flag; compare live vs backtest; surface decay. Backtester realism (SL/TP/time exits — open tech-debt row 43) folds in here. |

**Definition of "safe enough to go live" (proposed exit checklist — for the architect to bless or reshape):**
- [ ] Closes reach the exchange and reconcile (PR 1–2).
- [ ] A tiered halt exists with a *documented* flatten-authority policy (PR 3).
- [ ] Portfolio-level (not just per-profile) exposure + correlation limits (PR 4).
- [ ] Realized PnL is net of fees **and** funding **and** slippage, per strategy (PR 5).
- [ ] At least one exchange-side protective order (reduce-only / stop) as defense-in-depth (extends PR 1).
- [ ] Live-vs-paper PnL delta measured and within tolerance (ties to Viability Plan Phase 1).

---

## 6 · Decisions we need to make together

The earlier three questions, refined with the scope/readiness context. **Bring your partner's read on each.**

### Decision 1 — Confirm the slice & the "safe to go live" bar
Do we adopt the §5 Risk-Truth Hardening slice as the complement to the Viability Plan (slotting into/expanding its Phase 3, with PR 1–2 pulled earlier for fidelity)? And does the §5 exit checklist match the architect's definition of "safe enough to try live"? *(Recommendation: yes — it's the smallest set that makes both live-safety and paper-fidelity real, and it's mostly independent of the strategy work.)*

### Decision 2 — Flatten authority for an autonomous system *(the real architecture call)*
The taxonomy doc's open question, and the most consequential one given we want **autonomy**: **should the automated layer ever flatten positions unattended, or only de-risk — reserving "flatten" for human authorization?**
- **Auto-flatten unattended** → faster tail protection on a 24/7 book, but risks false-positive self-harm, and (per the doc's "reliability inversion") the kill switch is least able to execute exactly when it's most needed.
- **De-risk-only, human-confirm flatten** → safe against our own kill switch, but a true tail can outrun a human between check-ins.
- For an *autonomous* system the honest framing is a **third option: tiered + graduated authority** — automate the cheap/reversible verbs (stop-opening, de-risk, neutralize), gate the irreversible one (full flatten) behind either human confirmation *or* a very high, multi-signal threshold. *(Recommendation: tiered authority; document the exact threshold in `DECISIONS.md`.)* This is the decision that most defines "safe AND autonomous," so it's the one we most want the architect to own.

### Decision 3 — Branch model + reproducible CI
Given you want CI you can **reuse on the next project** and a clean Claude-Code workflow:
- **Integration branch + PR gates** (recommended): one long-lived `feat/risk-truth-hardening` off `main`; small PRs squash-merge into it; merge to `main` only when the whole slice is green + verified. Add PR template, CODEOWNERS, CONTRIBUTING, and a `.pre-commit-config.yaml` that mirrors the CI lint gates so style/types never slip locally.
- **Permanent `develop` branch** (GitFlow-lite): CI already targets `develop`; better if multiple parallel efforts (incl. the redesign branch) are ongoing.
- **Trunk-based + feature flags**: fastest, relies on flags to keep `main` shippable.
- *Portability note:* whichever we pick, the CI + pre-commit + PR-template + CODEOWNERS set is designed to be copy-pasteable into the next repo.

---

## 7 · SDLC / CI proposal (PR 0 detail)

What exists today: real CI (`.github/workflows/ci.yml`: lint → unit → integration → security-scan → frontend-lint → docker-build), Poetry, ruff/mypy-strict/black/isort, pytest, an append-only `docs/DECISIONS.md`, and local `.claude/hooks`. What's missing for a "reusable, healthy" process:

- **`.pre-commit-config.yaml`** mirroring the CI lint gates (black, isort, ruff, mypy) so the same checks run locally before commit — kills the "CI fails on formatting" loop.
- **PR template** (`.github/PULL_REQUEST_TEMPLATE.md`): what/why, risk tier, financial-precision checklist (CLAUDE.md §5B), test evidence, rollback.
- **CODEOWNERS**: route `services/{execution,pnl,risk}/**` and `libs/core/**` to require architect review.
- **CONTRIBUTING / branch-strategy doc**: the chosen Decision-3 model, written down once.
- **DECISIONS.md consolidation**: the root file is a stale empty template referencing CLAUDE.md sections that no longer exist; `docs/DECISIONS.md` is the live one. Merge to one.
- **(Optional) a portable CI starter**: extract the lint+test+pre-commit set into a documented, copy-pasteable baseline for the next project.

---

## 8 · Explicitly NOT doing now (deferred, with reasons)

- **Federation split into 3 engines** (Part 2 / Tier 2.10) — premature; single-engine spot doesn't pay for the overhead yet. The doc agrees ("build as few as constraints force").
- **Sub-account isolation / margin model** (Tier 1.8) — no leverage exists; becomes relevant only when perps land (which is the Viability Plan's Yield Harvester work).
- **Capital allocator** (Tier 3.15) — meaningful only with multiple strategies competing for capital.
- **Microstructure/arb/on-chain signal families** (Part 1 E/F/H/I/J) — large data-plane builds; tracked by the Viability Plan + `STRATEGY_GAP_ANALYSIS.md`, not this safety layer.

---

*Questions, pushback, or "re-verify claim X" all welcome — every row above is anchored to a file:line your partner can open and check.*
