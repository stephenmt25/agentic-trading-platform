# Partner Decisions — Reasoning, Impact & Recommendations

### 2026-06-13 debt burn-down session · six decisions awaiting architect sign-off

**Audience:** architect sign-off · **Author:** Claude Code (handler: Stevo) · **Companion to:** `docs/EXECUTION-BRIEF-2026-06-13-DEBT-BURNDOWN.md` (the what-happened brief). This document is the *why* — the reasoning, system impact, options, and a recommendation for each of the six decisions that brief surfaced.

Every claim here is grounded in the code as it stands on `feat/snappy-honest-edge` (`7b8361d`). File:line citations are listed per decision. Where a call is judgment rather than fact, it is marked as such.

---

## Executive summary

The debt burn-down made the platform's **measurement instrument honest** — every CI gate is now blocking and green, the safety surface is tiered and operator-gated, and the backtester shares exit logic with the live engine so its numbers mean something. The instrument now works. The uncomfortable thing it measures is that **no current signal family is profitable out-of-sample.** That single fact is the spine of these six decisions: five of them are cheap, mechanical, and unblock or de-risk the sixth, which is the expensive strategic one (what to build next when you have honesty but not edge).

The through-line recommendation: **resolve the five cheap decisions first — they are nearly free and each closes a standing risk or unblocks the next — then make the one strategic call (Decision 1) deliberately, gating the most expensive build on a measurement you do not yet have.** Concretely:

- **Decisions 6 + 4 (merge + branch protection)** are a pair and should move together: merge the green branch to `main` now via a recorded `--no-ff` PR, and enable required-status-checks on the now-green `main` immediately after — so the blocking gates the session built actually hold the line instead of resting on maintainer discipline. Full required-CODEOWNERS-review follows the moment the architect's real handle and review bandwidth are confirmed.
- **Decision 2 (EN-W2 verdicts)** is the evidence base for Decision 1: accept three verdicts now (soak bands frozen, convergence confirmed, baseline seeded) and mark the MACD kill *provisional* pending one cheap coarse-timeframe re-test.
- **Decision 5 (capital/fees)** is a one-line confirmation that ratifies what the code already does ($10k @ VIP0) and unblocks EN-W4's expected-value math — paired with a fix so that math is actually net-of-fees.
- **Decision 3 (kill-switch operators)** closes a live cross-user liquidation hole at zero engineering cost — configure the operator allowlist now; it must also precede any automated NEUTRALIZE wiring.
- **Decision 1 (EN-W3 priority)** is the real call. The recommendation is *not* the plan of record as written. It is to pull EN-W4's auto-deprecation forward (cheap, and the honest response to the edge headline), lead EN-W3 with a funding-carry **shadow backtest**, and commit the expensive perp/multi-leg substrate **only once that shadow shows positive net-of-cost edge** — measure the carry thesis with the honest instrument before building the substrate to run it on.

None of the six is new in kind; they are the standing partner inputs, now on the critical path because the engineering that surrounded each is done.

## Recommendations at a glance

| # | Decision | Recommendation | Cost to act | Cost of inaction |
|---|----------|----------------|-------------|------------------|
| 1 | EN-W3 vs EN-W4 vs edge-discovery | **Pull EN-W4 auto-deprecation forward; shadow-backtest funding carry; gate the full EN-W3 substrate on positive net-of-cost edge** | Re-sequencing only | EN-W3 substrate built on faith — the deploy-on-faith failure the honesty work exists to prevent |
| 2 | EN-W2 verdicts sign-off | **Accept 3 of 4 now; MACD kill provisional pending a coarse-timeframe re-test** | One script edit + worker passes | Unratified negative baseline live + unowned; MACD profiles in limbo |
| 3 | Kill-switch operator model | **Configure the explicit env allowlist now** (option b) | One env value + surface user_id | Any 2nd login can FLATTEN the whole book / clear halts (CWE-200 log leak) |
| 4 | CODEOWNERS + branch protection | **Required-status-checks now + real handle auto-request; full required-review when the architect can approve** | One settings change + handle | Green CI is a habit, not a control; money-path PRs merge unreviewed |
| 5 | Capital / fees ($10k @ VIP0) | **Confirm now + attach the simulator fee-subtraction fix; defer full parameterization to EN-W4** | One-line flip (ratifies reality) | EN-W4 EV math blocked; carries unconfirmed across 4+ session plans |
| 6 | Merge feat/snappy-honest-edge → main | **Merge now via a recorded `--no-ff` PR (not squash)** | One PR | `main` stays red; gates stay theoretical; diff grows; Decision 4 blocked behind it |

## Recommended sequencing

The dependency graph (detailed per-decision below) collapses to a clean order. Earlier steps unblock or de-risk later ones:

1. **Decide the self-merge policy (Decision 4's crux), then merge (Decision 6).** The one question that orders everything: *can the architect act as a real GitHub approver?* If yes — wire the real CODEOWNERS handle, enable branch protection, and let this merge be the first gated PR. If no (solo-maintainer reality) — merge now via a `--no-ff` PR, then enable required-status-checks on the green `main` so the *next* slice is gated. Either way, `main` goes green and the gates become real.
2. **Sign off the EN-W2 verdicts (Decision 2).** Three now, MACD kill provisional. This is the evidence base the strategic decision rests on.
3. **Confirm capital/fees (Decision 5).** One-line ratification of what the code already does; unblocks EN-W4 EV math.
4. **Configure the kill-switch operator allowlist (Decision 3).** Closes the live liquidation hole and is a prerequisite for any automated NEUTRALIZE wiring in the next step.
5. **Make the strategic call (Decision 1).** With the above settled: pull EN-W4 auto-deprecation forward (respecting the operator gate via a service-identity exemption), lead EN-W3 with a funding-carry shadow backtest, and gate the full substrate build on its result.

Steps 1–4 are hours-to-days of low-risk work. Step 5 is the multi-week commitment — and the recommendation is to spend it only after the cheap insurance in steps 1–4 is bought.

## Cross-dependency map

These decisions are not independent. The couplings that matter:

- **6 ↔ 4 (tightest):** branch protection should engage at the merge boundary. The CODEOWNERS placeholder must be replaced with a real handle *before* any required-review is switched on, or GitHub silently skips the review. The self-merge question (can a solo maintainer approve their own green slice?) decides whether the order is *merge-then-protect* or *protect-then-merge*.
- **2 → 1:** the EN-W2 verdicts (MACD killed, no re-band rescue, convergence confirmed) **are** the evidence base for the edge headline that forces Decision 1. Decide 2 first; 1 is downstream of it.
- **5 → 1:** the capital/fee tier is a direct input to the funding-carry EV math that Decision 1's recommendation hinges on. Confirm 5 before or alongside the shadow backtest — a strategy that is EV-positive at one fee tier can be EV-negative at VIP0.
- **3 → 1:** if EN-W4 auto-deprecation is pulled forward (the Decision 1 recommendation), its automated `KillSwitch.set_level(NEUTRALIZE)` call must respect the operator-authorization model from Decision 3 — it needs an explicit service-identity exemption or it will be 403-blocked. Resolve 3 before wiring auto-deprecation.
- **3 ↔ 4 (same question, two surfaces):** the operator allowlist is *runtime* 'who may do destructive things'; CODEOWNERS is *merge-time* 'who may change the code that does them.' Answer both with one consistent posture: single-operator/solo today, real roles when multi-user.
- **1 (the spine):** every other decision either feeds it (2, 5), constrains how it ships (3, 4), or gates the base it branches from (6).

> **Note on the word 'kill':** Decision 2's *MACD kill* is a profile deactivation (`is_active=false`) and is unrelated to Decision 3's runtime *kill switch* (the halt ladder). They share a word, nothing else.

---

## Decision 1 — EN-W3 / EN-W4 re-prioritization — what to build next

### Why this decision exists

The platform just crossed an inflection point. Three sessions of work (Risk-Truth Hardening PR0–PR7, FE-W2 snappy/honest pipeline, the EN-W1 backtest truth-pass, EN-W2 edge triage, and a full debt burn-down) have made the **measurement instrument honest**: mypy is 0/275 and blocking, ESLint 0/0 and blocking, 24 integration tests run against real Redis+Timescale, the kill switch is tiered and operator-gated, and the backtest sim shares its exit-decision logic with the live `ExitMonitor` so close-reason distributions converge (live 93/7 time/SL vs sim-OOS 90/5/5, `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:53-61`). The instrument now works. **What it measures is not profitable.** Every current signal family has negative out-of-sample edge on Apr–Jun 2026 data: the RSI mean-reversion soak profile prints OOS sharpe −4.00, and all three MACD variants print −2.7 to −8.2 with profit factors of 0.14–0.62 (`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:24-48`). MACD is killed (DECISIONS 2026-06-12). The exit-band re-banding rescue was tried and rejected — the swept result (−5.41) was *worse* OOS than the untouched bands (−4.00).

This forces a strategic decision because the plan of record (`NEXT-SESSION-PLAN-2026-06-13.md`) raises **EN-W3** — the Tokyo cloud substrate, the netting/margin schema (migration 025), and the Phase-A multi-leg/perp/funding primitives — to top priority. EN-W3 is *infrastructure to host MORE strategies*, specifically the Yield Harvester. But the honest reading of the edge numbers is uncomfortable: we are about to spend 2–3 weeks of build effort (plus a 60-day soak commitment in EN-W4) on a substrate for a new strategy family whose edge we have **not yet measured**, while the deprecation machinery that would automatically retire the strategies we *know* are unprofitable (EN-W4's `decay_tracker → KillSwitch.set_level(NEUTRALIZE)` wiring) is still a confirmed gap (`services/analyst/src/decay_tracker.py:105-111` only logs + AMBER-alerts; no `set_level` call exists).

What is fundamentally at stake is **sequencing under uncertainty about edge**. The honesty infrastructure was the right prerequisite — you cannot trust any strategy decision without it. But honesty is not edge. The question the architect must rule on is whether the next dollar of effort buys *capacity to deploy* (EN-W3 substrate), *discipline to stop deploying what fails* (EN-W4 auto-deprecation + capital allocator), or *the actual scarce resource — a profitable signal* (edge-discovery: new families, regimes, or the funding-rate edge that underpins the Yield Harvester thesis). The Yield Harvester is attractive precisely because its edge is *structural* (funding-rate carry) rather than *directional* (which is the exact thing the platform just proved it cannot find) — but that thesis is, per the Strategy Gap Analysis, explicitly un-cost-modeled and the $10k/VIP0 capital assumption that drives its EV math is still FLAGGED-unconfirmed (`NEXT-SESSION-PLAN-2026-06-13.md:77`).

### What the system does today

**The plan of record is EN-W3, and it is unambiguous.** `NEXT-SESSION-PLAN-2026-06-13.md:33-38` makes "Lane A (PRIORITY) — EN-W3 · Tokyo substrate + Phase-A primitives + migration 025" the headline lane; `NEXT-SESSION-PLAN-2026-06-14.md:3-4` confirms "The next session's directive is unchanged: EN-W3 Tokyo substrate + Phase-A primitives." FE-W3 is demoted to cleanup.

**EN-W3, concretely, is** (per master plan `NEXT-SESSION-PLAN-2026-06-10.md:142-149` and the 06-13 handoff §2):
- Migration 025 (RESERVED, not yet written — the migrations tree tops out at `024_trade_cost_attribution.sql`, verified): `accounts` + `position_groups` tables, `market_type` + `margin_mode` columns, a horizon partition key, all money columns NUMERIC. Schema-first; no dependent code before it is verified.
- Phase-A primitives: `OrderType/TimeInForce/MarginMode/MarketType` enums in `libs/core/enums.py` (verified absent today — grep returns no matches), `order_type/leg_group_id/leg_index` threaded through `place_order` + order events, funding-rate ingestion, perp-leg plumbing on ISOLATED margin.
- An AWS Tokyo VM (`ap-northeast-1`, locked DECISIONS 2026-06-11) for <10ms WS RTT, plus an APScheduler framework for compounding/funding-poller jobs.

The netting/margin policy that *binds* the 025 schema is already locked (DECISIONS 2026-06-11): horizon partitioning, never hard-veto, forbid cross-horizon netting, ISOLATED perp legs.

**EN-W4, concretely, is** (`NEXT-SESSION-PLAN-2026-06-10.md:151-160`, master plan Phase 5): the Yield Harvester (perp adapter, funding ingestion, `funding_rate` table, weekly compounding), the **auto-deprecation wiring** (`decay_tracker.py` → `KillSwitch.set_level(NEUTRALIZE)`, never FLATTEN), and a 60-day cloud soak. The auto-deprecation half is currently a gap: `decay_tracker.py:105-111` logs `strategy_decay_detected` and fires an AMBER alert but never calls the kill switch. The capital allocator is explicitly DEFERRED (`NEXT-SESSION-PLAN-2026-06-13.md:81`).

**The edge facts are not in dispute.** Every current signal family is negative-OOS (`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:64-69`; DECISIONS 2026-06-12 records the three verdicts). The honesty infrastructure that produced those numbers is green and blocking (head `7b8361d`, 35 commits ahead of `main`). The funding-rate edge that the Yield Harvester would harvest **has zero implementation today** (grep for `funding_rate|fetchFundingRate|defaultType.*future|PERP_USDM` across `libs/` returns no matches) — and critically, **it has never been measured** in this codebase; the Strategy Gap Analysis flags the 30–50% APY framing as un-cost-modeled bias (`docs/STRATEGY_GAP_ANALYSIS.md:39,100,123`).

### How each choice propagates through the system

**If EN-W3 proceeds as planned (substrate-first):** The blast radius is large and touches the core order model. Phase-A primitives extend `libs/core/enums.py`, `ExchangeAdapter.place_order` (`libs/exchange/_base.py:78`), and `OrderApprovedEvent`/`OrderExecutedEvent` (`libs/core/schemas.py`) — every downstream consumer (validation, execution, PnL, position-close) assumes one symbol/one side today, so widening the event model is the single most invasive change in the system (`docs/STRATEGY_GAP_ANALYSIS.md:72-77`). Migration 025 adds `accounts`/`position_groups` and a horizon partition key, restructuring the positions model. The gates are now blocking, so all of this must land typed and lint-clean. Default behavior for existing profiles stays unchanged (the plan is explicit on this), so the risk is *cost and scope*, not regression — but it is multi-week, money-path, schema-first work whose entire payoff is contingent on a strategy (Yield Harvester) whose edge is unverified.

**If EN-W4's auto-deprecation slice is pulled forward instead:** Small, surgical, and high-leverage *given the edge headline*. The change is localized to `services/analyst/src/decay_tracker.py:105-111` plus a `KillSwitch.set_level(NEUTRALIZE)` call (the tiered kill switch, operator gate, and FLATTEN safeguards already exist from PR3). It closes the loop between PR7 decay detection and PR3 tiered halt and means the *next* unprofitable strategy gets neutralized automatically rather than bleeding paper PnL. It does not require the Tokyo VM, migration 025, or the perp primitives. It directly operationalizes the only thing the platform has actually proven: that it can *detect* a decayed/edgeless strategy.

**If effort pivots to edge-discovery:** This is the highest-variance path and the least specified. The Yield Harvester funding edge is the most defensible candidate *in principle* (it is a structural carry edge, latency-insensitive — the opposite of the directional edge the platform just failed to find, and the opposite of the tri-arb/latency-exploiter family the Gap Analysis shows is negative-EV at retail tier, `docs/STRATEGY_GAP_ANALYSIS.md:95-99`). But realizing it *requires most of EN-W3 anyway* (perp adapter, funding ingestion, position_groups), so "pivot to funding edge" and "do EN-W3" are not cleanly separable. A cheaper edge-discovery move is a **funding-rate shadow capture** — ingest funding rates and historically backtest the carry edge *before* building the perp execution substrate, using the now-honest walk-forward machinery (`scripts/en_w2_edge_triage.py` is the worked template). That measures the Yield Harvester thesis for days of effort instead of weeks, and gates the EN-W3 substrate build on evidence rather than assumption.

### Options

#### Option A — Proceed with EN-W3 as planned (substrate-first)

*Build the Tokyo VM, migration 025, and Phase-A perp/funding/multi-leg primitives now, per the plan of record.*

**Pros:**

- Honors the locked decisions (region, netting/margin) and the existing dependency chain (EN-W0 policy → EN-W3 schema → EN-W4 strategy).
- Phase-A primitives are genuinely load-bearing — every Tier-2 strategy (Yield Harvester, Mean Reverter) needs them, so the work is not wasted regardless of which strategy lands first (docs/STRATEGY_GAP_ANALYSIS.md:299-307).
- Schema-first discipline is correct: building the schema before dependent code is a CLAUDE.md hard constraint, and 025 is the gating artifact.
- Tokyo substrate independently unblocks Viability Phase 1 (honest 24/7 measurement for hold-strategies — the laptop is a poor instrument for multi-day holds per PLATFORM_VIABILITY_PLAN §1).

**Cons:**

- Spends 2–3 weeks of money-path, maximum-blast-radius schema/event work on a substrate for a strategy whose edge is UNMEASURED — the exact mistake the honesty work was supposed to prevent.
- The Yield Harvester EV math depends on the $10k/VIP0 capital assumption that is still FLAGGED-unconfirmed (NEXT-SESSION-PLAN-2026-06-13.md:77); building the substrate before that input is confirmed risks a substrate sized for the wrong economics.
- Leaves the auto-deprecation gap open: the platform can detect a decayed strategy but cannot act on it (decay_tracker.py:105-111).
- Largest scope, largest regression surface, longest time-to-signal.

**Changes required:** Write migration 025 (accounts, position_groups, market_type, margin_mode, horizon key, NUMERIC). Add OrderType/TimeInForce/MarginMode/MarketType to libs/core/enums.py. Thread order_type/leg_group_id/leg_index through place_order + order events. Provision AWS Tokyo VM + Secrets Manager. Add APScheduler. All typed + lint-clean (blocking gates).

#### Option B — Pull EN-W4 auto-deprecation forward first, then EN-W3

*Close the decay→NEUTRALIZE loop now (small, localized), then proceed to the EN-W3 substrate.*

**Pros:**

- Operationalizes the one capability the platform has proven — detecting edgeless strategies — by making detection actually act.
- Tiny blast radius: one call in decay_tracker.py on top of the already-built PR3 tiered kill switch and PR7 decay tracker.
- Directly responsive to the headline: with negative-edge strategies confirmed, an automatic NEUTRALIZE (never FLATTEN) is the honest safety response.
- Does not block or delay EN-W3 meaningfully — it is days, not weeks — and it de-risks any future deployment on the new substrate.

**Cons:**

- Does not, by itself, create any new edge — it makes the platform better at *not losing*, not at *winning*.
- The auto-deprecation has limited bite today because the only active strategy is the soak profile, which is intentionally edgeless (an instrument-fidelity probe, not an edge bet) — so the wiring is partly insurance for future strategies.
- Mostly a sequencing tweak to the existing plan rather than a strategic redirection — the architect may view it as already in-scope for EN-W4.

**Changes required:** In services/analyst/src/decay_tracker.py:105, on assessment.decayed call KillSwitch.set_level(NEUTRALIZE) for that profile in addition to the existing log + AMBER alert. Target NEUTRALIZE never FLATTEN (DECISIONS 2026-06-10 flatten-authority). Add a test that a forced decayed=true sets the profile kill-switch level. No schema, no substrate.

#### Option C — Edge-discovery first: funding-rate shadow capture before any substrate

*Ingest + backtest the funding-rate carry edge using the honest walk-forward machinery, BEFORE building the perp execution substrate — measure the Yield Harvester thesis cheaply.*

**Pros:**

- Tests the actual Yield Harvester EV thesis (funding carry) for days of effort instead of committing to weeks of substrate build on an unmeasured assumption.
- Reuses the now-honest measurement instrument (walk-forward OOS, scripts/en_w2_edge_triage.py as the template) — the exact tool the honesty work built.
- Funding carry is the most defensible edge candidate: structural, latency-insensitive, orthogonal to the directional edge the platform just proved it lacks.
- Gates the expensive EN-W3 substrate on evidence; if funding edge is negative net-of-cost at VIP0, the whole Yield Harvester substrate is descoped before it is built — exactly the Phase-6 live-decision-gate discipline (PLATFORM_VIABILITY_PLAN §3 Phase 6) applied one phase earlier.

**Cons:**

- Funding-rate ingestion itself is part of Phase-A (some EN-W3 work happens anyway — they are not cleanly separable), so this is a re-ordering within EN-W3 rather than an avoidance of it.
- Backtesting funding carry without a perp execution model means the shadow capture measures gross carry, not net-of-execution — it is a screen, not a verdict; a positive screen still requires the substrate build to confirm.
- Requires building the funding data plane (poller + table + channel) which has zero implementation today (grep-confirmed) — non-trivial even as a screen.
- Higher uncertainty on timeline; edge-discovery is inherently variance-heavy and may return 'no edge here either.'

**Changes required:** Add funding-rate ingestion (fetchFundingRate poller + funding_rate table + pubsub channel) — a slice of Phase-A pulled forward. Build a funding-carry backtest using the walk-forward OOS machinery to estimate net-of-cost carry at the FLAGGED $10k/VIP0 assumption. Defer the perp execution adapter, position_groups, and migration 025's full scope until the screen passes.

### Recommendation

**Recommend a sequenced blend: B-then-C, with EN-W3's full substrate gated on C's result.** Concretely: (1) pull the EN-W4 auto-deprecation wiring forward as a fast, low-risk first move (Option B); (2) within EN-W3, lead with the funding-rate *data plane and shadow backtest* (Option C) rather than the perp execution substrate; (3) commit to the full EN-W3 substrate build (migration 025 perp/multi-leg primitives, Tokyo VM provisioning at full cost) only once the funding-carry shadow capture shows positive net-of-cost edge at the (confirmed) capital/fee tier.

The rationale is the headline itself. The platform's scarce resource is **edge**, not capacity-to-deploy and not detection. EN-W3 as written (Option A) spends the most expensive, highest-blast-radius effort the codebase can absorb — widening the single-symbol/single-side event model that every downstream service depends on — on a substrate for a strategy whose edge has *never been measured in this repo*. That is the precise failure mode the honesty work was built to prevent: deploying on faith. The Yield Harvester thesis is genuinely more promising than the dead directional families (a structural carry edge is a different animal from a directional indicator), but "more promising in principle" is exactly the kind of claim the EN-W2 triage just taught us to distrust. The Strategy Gap Analysis itself flags the 30–50% APY framing as un-cost-modeled bias (`docs/STRATEGY_GAP_ANALYSIS.md:123`). Measure the carry edge with the honest instrument *before* building the substrate to run it on.

Option B comes first because it is nearly free and is the honest response to the headline: a platform that has just proven it can detect edgeless strategies should wire detection to action (NEUTRALIZE) before it deploys anything new. It is days of work on top of already-shipped PR3/PR7 machinery, and it de-risks every future deployment.

**The recommendation flips to straight Option A (substrate-first) under three conditions, any one of which is sufficient:** (1) the architect confirms the Yield Harvester / Tokyo move is being justified primarily by **measurement honesty for hold-strategies** (Viability Phase 1) rather than by edge — in which case the substrate is a prerequisite for honest measurement, not a bet on unverified edge, and building it first is correct; (2) the $10k/VIP0 capital/fee assumption is confirmed AND the architect's prior conviction on funding carry is high enough that a shadow capture is judged redundant; or (3) provisioning the Tokyo VM is on a long lead time (cloud account setup, secrets migration) such that starting it in parallel with the funding shadow capture is free — in which case do the substrate provisioning concurrently and still gate the perp *execution* code on the shadow result. The recommendation does NOT flip toward pure tri-arb / latency-exploiter edge-discovery under any condition — the Gap Analysis is decisive that family is negative-EV at retail tier (`docs/STRATEGY_GAP_ANALYSIS.md:95-99`) and it is already correctly DEFERRED.

### Coupling to the other decisions

This decision is the spine of the set and is coupled to nearly all of the others:

1. **EN-W3 priority (this decision)** is the parent. Everything below is a consequence of how it resolves.

5. **Capital/fees confirmation ($10k @ VIP0, FLAGGED assumption #7)** is the tightest coupling. The Yield Harvester EV math — and therefore whether the EN-W3 substrate is worth building — depends on it (`NEXT-SESSION-PLAN-2026-06-13.md:77`; DECISIONS 2026-06-11 netting/margin trade-off explicitly flags it). **Ordering implication: the capital/fee input should be confirmed before, or concurrently with, the funding shadow capture — it is an input to the net-of-cost carry calculation.** If A is chosen substrate-first, this confirmation becomes urgent because it sizes the ISOLATED-margin top-up logic.

3. **Kill-switch operator gate** couples to the Option-B auto-deprecation wiring: an automated `KillSwitch.set_level(NEUTRALIZE)` must respect the operator-authorization model just hardened (DECISIONS 2026-06-11 — NEUTRALIZE is position-destructive and operator-gated for *human* callers; the automated decay path needs an explicit service-identity exemption or it will be 403-blocked). This must be resolved before B ships.

4. **CODEOWNERS / branch-protection** couples via merge-timing: EN-W3 touches money-at-risk paths (order events, execution), so once branch protection with CODEOWNERS is enabled (still pending the architect's GitHub handle), every EN-W3 PR requires architect review. **Ordering implication: enabling branch protection raises the per-PR cost of EN-W3's large blast radius — argues for the smaller B-then-C sequencing.**

6. **Merge-timing of feat/snappy-honest-edge → main** (35 commits ahead) gates everything: EN-W3 work should branch off a merged, gate-green main, not stack further on the integration branch.

Coupling to the other EN-W2 verdicts (decision set item 2) is informational: those verdicts (MACD killed, no re-band rescue, convergence confirmed) are the *evidence base* for this decision — they are the reason the edge headline exists.

### Cost of leaving it undecided

Leaving this undecided is costly because EN-W3 is the explicit plan of record — the *next* session will start building the Tokyo substrate, migration 025, and the perp/multi-leg primitives by default, because that is what `NEXT-SESSION-PLAN-2026-06-13.md` and `-06-14.md` both direct. That means the default outcome is **Option A by inertia**: 2–3 weeks of the highest-blast-radius, money-path schema and event-model work the codebase can absorb, committed before the funding-carry edge that justifies it has ever been measured — the precise deploy-on-faith failure mode the entire honesty programme was built to prevent.

Concretely, while this stays undecided: (1) the auto-deprecation gap (`decay_tracker.py:105-111`) stays open — the platform can detect a decayed strategy but cannot act, so any strategy that goes live on the new substrate has no automatic brake; (2) the FLAGGED capital/fee assumption (#7) keeps propagating into substrate sizing decisions (ISOLATED-margin top-up logic, compounding cadence) without confirmation, so the substrate may be built for the wrong economics; (3) the funding-carry thesis remains an *assumption* rather than a *measurement*, meaning the team could complete the entire EN-W3 substrate and only discover at the EN-W4 soak that the Yield Harvester is net-negative at VIP0 — wasting the most expensive work in the plan. The cheap insurance against all three (pull B forward, lead C with a funding shadow capture) is forfeited by default if the architect does not actively re-sequence.

### Evidence

*Grounding citations (verified against the tree at `7b8361d`):*

- `docs/NEXT-SESSION-PLAN-2026-06-13.md:33-38 (EN-W3 raised to PRIORITY: Tokyo substrate + Phase-A primitives + migration 025)`
- `docs/NEXT-SESSION-PLAN-2026-06-13.md:22-27 (the headline: every current signal family has negative OOS edge)`
- `docs/NEXT-SESSION-PLAN-2026-06-13.md:77 ($10k VIP0 capital/fees FLAGGED, blocks EN-W4 EV math)`
- `docs/NEXT-SESSION-PLAN-2026-06-13.md:81 (EN-W4 = Yield Harvester + auto-deprecation; capital allocator DEFERRED)`
- `docs/NEXT-SESSION-PLAN-2026-06-14.md:3-4 (directive unchanged: EN-W3 carried forward)`
- `docs/NEXT-SESSION-PLAN-2026-06-14.md:24 (migration 025 still RESERVED, none run this session)`
- `docs/NEXT-SESSION-PLAN-2026-06-10.md:142-149 (EN-W3 substrate + Phase-A primitives detail)`
- `docs/NEXT-SESSION-PLAN-2026-06-10.md:151-160 (EN-W4 Yield Harvester + auto-deprecation + 60-day soak)`
- `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:24-35 (MACD all negative OOS sharpe -2.7 to -8.2, killed)`
- `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:39-48 (RSI soak baseline OOS -4.00; re-band sweep WORSE at -5.41)`
- `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:53-69 (convergence PASSES; headline: negative OOS edge across all families)`
- `docs/DECISIONS.md:530-581 (EN-W2 verdicts: MACD killed, no re-band rescue, convergence confirmed, prioritization headline)`
- `docs/DECISIONS.md:351-394 (netting/margin policy binding for migration 025: horizon partitioning, no cross-horizon netting, ISOLATED perp legs; $10k VIP0 flagged)`
- `docs/DECISIONS.md:323-347 (cloud region locked AWS Tokyo ap-northeast-1)`
- `docs/DECISIONS.md:445-485 (kill-switch operator authorization: NEUTRALIZE operator-gated)`
- `services/analyst/src/decay_tracker.py:105-111 (auto-deprecation GAP: decay only logs + AMBER alerts, no KillSwitch.set_level call)`
- `docs/STRATEGY_GAP_ANALYSIS.md:299-307 (Phase A primitives unblock >=80% of downstream work)`
- `docs/STRATEGY_GAP_ANALYSIS.md:95-99 (tri-arb negative-EV at retail tier)`
- `docs/STRATEGY_GAP_ANALYSIS.md:100,123 (Yield Harvester funding/APY framing flagged as un-cost-modeled bias)`
- `docs/PLATFORM_VIABILITY_PLAN_2026-05-18.md:24-31 (laptop is poor measurement instrument for hold-strategies; Tokyo substrate justified by measurement honesty)`
- `docs/PLATFORM_VIABILITY_PLAN_2026-05-18.md:142-148 (Phase 6 live-decision gate: gate deployment on measured net-of-cost EV)`
- `migrations/versions/ (tops out at 024_trade_cost_attribution.sql — migration 025 confirmed not yet written)`
- `libs/core/enums.py (grep confirms OrderType/TimeInForce/MarginMode/MarketType/funding absent today)`

---

## Decision 2 — EN-W2 edge-triage verdicts sign-off

### Why this decision exists

EN-W2 was the platform's first *honest* edge-triage pass — the first time the walk-forward harness (EN-W1) and the new exit-band sweep dimension (EN-W2) were pointed at real production profiles on the live evaluation timeframe (1m candles), with out-of-sample (OOS) metrics computed on trades **entered in test segments only** (`services/backtesting/src/walk_forward.py:314`). The result is unambiguous and unflattering: every signal family the platform currently runs produces negative OOS Sharpe. The MACD triad lands between −2.74 and −8.21 (`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:26-31`); the RSI<35 soak strategy lands at −4.00 even before any re-banding, and −5.41 after an 18-combo exit-band sweep (`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:41-42`). This is not a measurement artifact — the convergence cross-check shows the simulator's exit behavior matches live soak within a few percentage points (`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:57-58`), which means the instrument is trustworthy and the verdict it delivers is real.

This is a decision and not just a report because signing off **commits the system to act (or refuse to act) on the numbers**. Four distinct commitments are bundled here: (a) permanently retiring three MACD profiles from the active set — `is_active=false` is a *manual* toggle (`services/api_gateway/src/routes/profiles.py:138`), so "killed permanently" is an operational promise, not an enforced state; (b) freezing the soak profile's exit bands against the conclusion that re-banding cannot rescue a directionless signal; (c) accepting a *negative* OOS row as the soak profile's decay baseline (`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:50-51`), which materially changes what "decay" means going forward; and (d) endorsing the headline that drives the entire forward roadmap — that EN-W3 (Tokyo substrate) / EN-W4 (Yield Harvester) is not an enhancement but the path to the *first defensible edge* (`docs/DECISIONS.md:570-576`).

What is fundamentally at stake is the platform's relationship to its own measurements. The whole Risk-Truth arc was about making the instrument honest. The instrument is now honest and it is telling the operator that there is nothing profitable to trade. Accepting these verdicts means trusting that honest-but-bleak signal enough to stop pouring engineering into the dead signal families and to redirect it to net-new strategy work. Rejecting or heavily caveating them means either distrusting the freshly-validated instrument or believing the sample/regime is unrepresentative — a defensible position given the four-window, two-month, single-market-regime test set, but one that has its own cost.

The architect is the domain expert on whether Apr–Jun 2026 was a representative regime and whether MACD "deserves" a different timeframe before burial. The handler's job here is to lay out exactly what each verdict mechanically commits the code to, and where the honest-but-narrow evidence base could mislead.

### What the system does today

In the absence of a sign-off decision, the system sits in the state EN-W2 left it, which is a mix of *already-applied* and *advisory-only* changes:

- **MACD profiles**: The verdict text says they "stay `is_active=false` permanently" (`docs/DECISIONS.md:547-548`), but I could not verify from code that any of the three MACD profiles were programmatically toggled inactive as part of EN-W2 — there is no automated deprecation path. `is_active` is flipped only by an explicit owner-authenticated `PUT /profiles/{id}/active` call (`services/api_gateway/src/routes/profiles.py:138-141`). So "killed" is currently a *documented intent*, and the actual active/inactive state of those three profiles in the DB is an operational fact I have not confirmed (assumption: they are inactive, since the runner enqueued them as "(inactive) profile" baselines, `scripts/en_w2_edge_triage.py:137`).
- **Soak exit bands**: Untouched. The sweep ran with `profile_id=""` (`scripts/en_w2_edge_triage.py:155`), so it was purely exploratory and never wrote back to the soak profile's `risk_limits`. The live soak keeps SL 4% / TP 3% / 6h.
- **Decay baseline**: The canonical soak baseline (`en-w2-soak-baseline`) was enqueued LAST with the real `profile_id` (`scripts/en_w2_edge_triage.py:160-170`) specifically so `latest_for_profile()` resolves to it (`libs/storage/repositories/backtest_repo.py:139-162`). This row **is already persisted and already live** as the soak profile's decay baseline. The DecayTracker reads it every cycle (`services/analyst/src/decay_tracker.py:77`). So this commitment is in effect *right now* regardless of sign-off — the soak profile moved from `no_baseline` status to having a negative OOS baseline.
- **Decay semantics under the new baseline**: With a negative baseline, the decay detector is largely inert for the soak profile. `assess_decay` only flags the avg-return path when `backtest_avg_return > 0` (`libs/core/decay.py:73-78`); the soak baseline's avg return is −0.41% (`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:42`), so that path can never fire. The win-rate path requires live win rate to fall >15 points below the (already low ~42%) baseline (`libs/core/decay.py:66-72`). "No decay" now means "live is matching the honestly-negative baseline" (`docs/DECISIONS.md:566-568`) — a true statement, but one that quietly converts the decay alarm into a near-permanent green light for a losing strategy.
- **Decay tracker scope**: It iterates `get_active_profiles()` only (`services/analyst/src/decay_tracker.py:69`). So killed MACD profiles drop out of decay assessment entirely; only the (active) soak profile is tracked.

### How each choice propagates through the system

**If accept-all:** The forward roadmap is unblocked. The handler stops spending cycles on MACD/RSI signal tuning and EN-W3/EN-W4 (Tokyo substrate, Yield Harvester) becomes the prioritized engineering lane (`docs/DECISIONS.md:570-576`). Operationally, the three MACD profiles must be confirmed `is_active=false` (a manual `PUT` per `services/api_gateway/src/routes/profiles.py:138`) — the blast radius is small because inactive profiles emit no orders and drop out of decay tracking (`services/analyst/src/decay_tracker.py:69`). The soak profile keeps running with its negative baseline as the decay reference. The notable second-order effect is that the decay tracker becomes a near-inert alarm for the soak profile (`libs/core/decay.py:76` gate plus a low win-rate baseline), so the operator must understand that "no AMBER decay alert on soak" no longer means "soak is healthy" — it means "soak is consistently unprofitable as expected." That is arguably *correct* behavior (you cannot decay below a floor that is already negative), but it removes the decay tracker as a useful guardrail for that profile.

**If reject-and-rerun:** No code changes; the existing seeded baseline stays live (it's already persisted). The cost is purely opportunity and queue time — the backtesting worker is a single serial consumer (`services/backtesting/src/walk_forward.py:57-58`), so a re-run competes with any other queued jobs. A re-run with different parameters (longer history, different timeframe, different regime slice) would produce a *newer* row, and because `latest_for_profile` is latest-wins (`libs/storage/repositories/backtest_repo.py:158`), that newer row would silently become the soak baseline — this is the documented "latest-wins landmine" (`services/validation/src/learning_loop.py:10-13`). Any re-run touching the soak profile must therefore replicate the `profile_id=""` poisoning guard discipline (`scripts/en_w2_edge_triage.py:17-20`) or it will clobber the canonical baseline.

**If accept-with-caveats (re-test MACD on a different regime/timeframe first):** Lowest-regret path on the MACD side. EN-W2 evaluated signals on **1m candles** because that is the live evaluation timeframe (`scripts/en_w2_edge_triage.py:15-16`, `services/strategy/src/hydrator.py` hydrates 1m). MACD is conventionally a trend-following indicator and 1m is an extremely noisy timeframe for it — the close-mix is dominated by `time_exit` (`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:26-31`), i.e. the signal rarely reaches its TP/SL and just times out, which is the fingerprint of a signal mismatched to its horizon. Re-testing MACD on a coarser timeframe is a one-script change (`TIMEFRAME` and `WF` bar counts in `scripts/en_w2_edge_triage.py:52,56`) and a few worker passes. The risk: a coarser-timeframe MACD that "works" in backtest would still have to be re-plumbed to evaluate live on that timeframe, which is real strategy work, not a config flip — so a positive coarse-timeframe result reopens an engineering commitment rather than closing one.

### Options

#### Accept all four verdicts as-is

*Sign off MACD KILL, soak bands frozen, convergence PASS, seeded negative baseline trusted — redirect all signal-engineering effort to EN-W3/EN-W4.*

**Pros:**

- Decisive; unblocks the forward roadmap with a clean conscience — the instrument is validated (convergence within a few points, docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:57-58) and the verdict it delivers is internally consistent across 24 windows.
- Stops sunk-cost engineering on signal families with no edge to rebuild (only 3 of 24 windows even had positive in-sample Sharpe, docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:33).
- Convergence PASS independently validates the EN-W1 exit-policy unification end-to-end — accepting it banks that validation as a reusable result.
- Lowest process overhead: three of four commitments are already in effect (baseline persisted, bands untouched); only the MACD is_active toggle needs operational confirmation.

**Cons:**

- Evidence base is narrow: 4 walk-forward windows over a single ~2-month window (Apr–Jun 2026), one market regime. A KILL ruling on this sample risks discarding a signal that simply didn't fit this regime or this timeframe.
- MACD on 1m is a horizon mismatch (time_exit-dominated close mix) — burying it without a coarser-timeframe re-test may be throwing away the indicator on a technicality of how it was measured, not its inherent merit.
- The negative decay baseline silently neuters the decay alarm for the soak profile (libs/core/decay.py:76 gate); 'no decay alert' stops meaning 'healthy', which can lull the operator.
- 'Permanently retire' overstates an is_active=false that no code enforces (services/api_gateway/src/routes/profiles.py:138) — nothing prevents reactivation, so the permanence is cultural, not mechanical.

**Changes required:** Confirm/set the three MACD profiles is_active=false via owner-authenticated PUT (services/api_gateway/src/routes/profiles.py:138). No code changes; seeded baseline and frozen bands are already in effect. Optionally annotate the decay snapshot consumer so operators read 'no decay' on soak as 'matching negative baseline'.

#### Accept with caveats — re-test MACD on a coarser timeframe before final burial

*Sign off soak bands, convergence, and the seeded baseline now; mark MACD KILL provisional pending a 15m/1h walk-forward re-run.*

**Pros:**

- Addresses the single most defensible objection (1m horizon mismatch) with a cheap, contained experiment — a TIMEFRAME/WF edit in scripts/en_w2_edge_triage.py:52,56 plus a handful of serial worker passes.
- Keeps the three non-MACD commitments (which are already-applied or low-risk) moving, so the roadmap isn't held hostage to the MACD question.
- Produces a stronger paper trail: a KILL that survives a regime/timeframe robustness check is far harder to second-guess later.
- Preserves optionality without indefinitely deferring the decision.

**Cons:**

- Adds a session of work and a serial queue cost before the MACD verdict closes; the worker is single-consumer (services/backtesting/src/walk_forward.py:57-58).
- A positive coarse-timeframe MACD result is a trap, not a win: it would require re-plumbing live evaluation onto that timeframe (strategy/hydrator work), reopening an engineering commitment rather than closing one.
- Risks scope creep — 'one more timeframe' can become 'one more regime, one more symbol' and never reach a verdict.
- The soak verdicts still ship with the same narrow-sample caveat; caveating only MACD is slightly inconsistent.

**Changes required:** Re-run MACD profiles via scripts/en_w2_edge_triage.py with TIMEFRAME='15m' or '1h' and recomputed train/test/step bar counts (line 52, 56). MUST keep profile_id set for canonical MACD baselines but ensure no soak-profile write (preserve the profile_id='' guard, lines 17-20). Mark the DECISIONS.md MACD verdict 'provisional pending coarse-TF re-test' until results land.

#### Reject and re-run with a broader evidence base

*Decline sign-off; demand a wider OOS test (longer history once available, more regimes, or a larger window count) before committing to any kill/keep ruling.*

**Pros:**

- Most statistically conservative — 4 windows is a thin basis for a permanent ruling on multiple strategy families.
- Guards against a regime-specific false negative across ALL signals, not just MACD.
- Forces the look-ahead/survivorship/auto-deprecation gap (libs/core/decay.py:8-11) to be confronted rather than papered over with a single seeded row.

**Cons:**

- History is the binding constraint: 1m coverage only starts 2026-04-18 (scripts/en_w2_edge_triage.py:49), so 'longer history on 1m' is not currently available — a broader test means coarser timeframes or waiting for data to accrue.
- High opportunity cost: indefinitely defers the EN-W3/EN-W4 redirect that is the actual path to edge (docs/DECISIONS.md:570-576) while the platform keeps running known-losing strategies.
- Distrusts a freshly-validated instrument (convergence PASS) without a concrete reason to believe the sample is unrepresentative — risks analysis paralysis.
- Any soak re-run risks the latest-wins baseline landmine (services/validation/src/learning_loop.py:10-13) if poisoning discipline lapses.

**Changes required:** Define and run a broader walk-forward matrix (more windows / multiple timeframes / additional symbols) before any verdict. Until then, leave MACD profiles in their current state and keep the already-seeded soak baseline. Strictly enforce the profile_id='' poisoning guard on every exploratory re-run.

### Recommendation

**Recommend Option 2 (accept-with-caveats): sign off three of the four verdicts now, mark the MACD KILL provisional pending a single coarse-timeframe re-test.**

The soak verdicts, the convergence PASS, and the seeded baseline should be accepted immediately. They are either already in effect (the baseline is persisted and live) or low-risk and well-evidenced: the convergence cross-check is the strongest result in the whole pass (sim matches live within a few points, `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:57-58`) and it validates the instrument we are about to trust. The soak re-banding rejection is also sound — an 18-combo sweep that comes out *worse* OOS than the untouched bands, with unstable per-window winners (`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:44-48`), is the textbook signature of in-sample overfit, and the conclusion that "you cannot re-band your way out of a directionless signal" is correct. Freezing the soak bands is the right call.

The one verdict I would not sign as *permanent* yet is the MACD KILL — not because I doubt the numbers, but because of a specific, cheap-to-close objection: MACD is a trend indicator and it was measured on 1m candles (`scripts/en_w2_edge_triage.py:15-16,52`), the noisiest plausible horizon for it, and the time_exit-dominated close mix (`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:26-31`) is the fingerprint of a signal mismatched to its horizon rather than a signal with no information. A 15m or 1h walk-forward re-run is a one-script edit and a few serial worker passes. If MACD is still negative on a coarser timeframe, the KILL becomes bulletproof and the architect can sign it with full confidence. If it is positive, the platform has learned something genuinely valuable before discarding an entire indicator family.

**This recommendation flips to Option 1 (accept-all) if** the architect's domain read is that (a) Apr–Jun 2026 was a representative-enough regime, and (b) MACD on a coarser timeframe isn't worth the re-plumbing cost even if it backtests well — because in that case the coarse-TF re-test is a dead-end experiment and accepting the KILL outright is the more honest use of time. It flips to Option 3 (reject) only if the architect believes the two-month single-regime window is fundamentally unrepresentative of the markets the platform intends to trade — but note the binding data constraint: 1m coverage only starts 2026-04-18 (`scripts/en_w2_edge_triage.py:49`), so "more data" today means coarser timeframes, which is exactly what Option 2 already does in a more targeted way.

One process note for whichever option is chosen: the decay tracker's behavior under a negative baseline (`libs/core/decay.py:76`) should be made explicit to the operator. "No decay alert on soak" now means "matching a negative baseline," not "healthy." That is correct behavior, but it is a silent semantic shift worth a sentence in the runbook.

### Coupling to the other decisions

This decision is coupled to several others in the set:

- **(1) EN-W3 priority** — Tightly coupled and effectively gated by this one. The entire justification for prioritizing EN-W3/EN-W4 is the headline that all current signals have negative OOS edge (`docs/DECISIONS.md:570-576`). If these verdicts are accepted, EN-W3 becomes the prioritized lane; if MACD's KILL is reconsidered (Option 2/3), the urgency of EN-W3 softens slightly. **Ordering implication: decide EN-W2 sign-off first; EN-W3 priority is downstream of it.**

- **(6) merge-timing** — The seeded baseline and the EN-W1 exit-policy unification that convergence validates are part of the 35-commit `feat/snappy-honest-edge` branch. Accepting the convergence verdict is partly an endorsement of merging that branch (the validated exit unification ships with it). Coupled to whatever governs merging this branch to main.

- **(5) capital/fees** — Indirectly coupled. These verdicts say there is currently no edge to deploy capital against. Any decision about capital allocation or going live is downstream — the EN-W2 conclusion is the gate: don't allocate to signal families with negative OOS edge.

- **(3) kill-switch operators** — Conceptually adjacent but mechanically independent. The "KILL" in MACD-KILL is a profile-deactivation (`is_active=false`), unrelated to the runtime kill-switch / halt ladder (`services/hot_path/src/kill_switch.py`, `services/pnl/src/halt_controller.py`). Worth disambiguating in the exec summary so the two "kill" concepts are not conflated.

Independent of: (2) EN-W2 sweep contract (already a separate, approved decision, `docs/DECISIONS.md:487-528`) and (4) CODEOWNERS/branch-protection.

### Cost of leaving it undecided

Leaving this undecided is moderately costly and asymmetric across the four sub-verdicts.

- **The seeded baseline is already live whether or not anyone signs off.** It was persisted as the last enqueued run (`scripts/en_w2_edge_triage.py:160-170`) and `latest_for_profile` already resolves to it (`libs/storage/repositories/backtest_repo.py:158`). So non-decision doesn't pause it — it just means the system runs with an unratified negative decay baseline and a quietly-neutered decay alarm for the soak profile (`libs/core/decay.py:76`) that nobody has consciously accepted. That is the worst of both worlds: the behavior change is in effect but unowned.

- **EN-W3/EN-W4 prioritization stalls.** The headline finding (`docs/DECISIONS.md:570-576`) is explicitly flagged for architect prioritization. Until the verdicts are accepted, the redirect of effort to net-new strategy work — the only path to a defensible edge per the analysis — has no green light, and the platform continues to carry known-losing signal families in its active set.

- **MACD profiles sit in an ambiguous state.** Documented as "killed permanently" but not enforced by code (`services/api_gateway/src/routes/profiles.py:138`). If their actual `is_active` flags weren't flipped, they may still be eligible to trade; if they were flipped, no decision-record ratifies it. Either way the gap between intent and enforced state stays open.

- **Re-run discipline degrades over time.** The longer the soak verdict stays open, the more likely a future exploratory backtest forgets the `profile_id=""` poisoning guard (`services/validation/src/learning_loop.py:10-13`) and silently overwrites the canonical baseline — a latent regression that gets more probable the longer the canonical row is unratified and unmonitored.

### Evidence

*Grounding citations (verified against the tree at `7b8361d`):*

- `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:26-31`
- `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:33`
- `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:41-48`
- `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:50-51`
- `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:57-58`
- `docs/EN-W2-EDGE-TRIAGE-2026-06-12.md:63-69`
- `docs/DECISIONS.md:541-549`
- `docs/DECISIONS.md:551-559`
- `docs/DECISIONS.md:561-568`
- `docs/DECISIONS.md:570-576`
- `docs/DECISIONS.md:487-528`
- `scripts/en_w2_edge_triage.py:15-20`
- `scripts/en_w2_edge_triage.py:49-65`
- `scripts/en_w2_edge_triage.py:136-170`
- `services/backtesting/src/walk_forward.py:57-65`
- `services/backtesting/src/walk_forward.py:214-221`
- `services/backtesting/src/walk_forward.py:254-329`
- `services/backtesting/src/simulator.py:117-156`
- `services/analyst/src/decay_tracker.py:55-118`
- `libs/core/decay.py:35-85`
- `libs/storage/repositories/backtest_repo.py:139-162`
- `services/validation/src/learning_loop.py:10-13`
- `services/api_gateway/src/routes/profiles.py:138-141`
- `services/api_gateway/src/routes/backtest.py:43-49`
- `tests/integration/test_repositories_db.py:264-312`

---

## Decision 3 — Kill-switch operator authorization model

### Why this decision exists

The kill switch is the platform's single most destructive control surface. Its strongest rung, `FLATTEN`, closes **every open position platform-wide** through the reduce-only close path — and it does so with no per-user scoping. `HaltController.flatten_all_open()` calls `self._position_repo.get_open_positions()` with no `profile_id` argument (`services/pnl/src/halt_controller.py:163`), which resolves to the unfiltered query `SELECT * FROM positions WHERE status = 'OPEN'` (`libs/storage/repositories/position_repo.py:122`). The halt level itself is a single global Redis key (`KILL_SWITCH_KEY = "praxis:kill_switch"`, `services/hot_path/src/kill_switch.py:24`), not a per-user value. So one POST to `/commands/kill-switch` with `level=FLATTEN` liquidates the book for the entire deployment, irrespective of who owns the positions.

The 2026-06-11 security review (logged in `docs/DECISIONS.md:445-484`) caught that this endpoint had authentication but no *authorization*: any JWT-bearing account could FLATTEN, or silently clear a halt that someone else set. The fix introduced an operator allowlist (`PRAXIS_KILL_SWITCH_OPERATORS`) gating the destructive verbs, but deliberately left it **unconfigured by default**, which collapses to "every authenticated user is an operator" (`services/api_gateway/src/routes/commands.py:41-52`). The reasoning was sound for a single-user box — an un-clearable brake is worse than a tierless one — but it bakes a cross-user destructive hole into the system that arms itself the instant a second human authenticates.

What forces the decision *now* rather than "at multi-user time" is that multi-user is not a gated future migration — it is one OAuth login away. The auth callback (`services/api_gateway/src/routes/auth.py:64-118`) does an **open upsert**: any account that completes the NextAuth/OAuth flow is `INSERT … ON CONFLICT DO UPDATE`'d into the `users` table with no invite list, no domain allowlist, and no admin approval (lines 95-112). There is no registration gate in code. So the boundary between "safe single-operator mode" and "anyone who logs in can liquidate the book" is a configuration value that is currently empty, not a feature that has yet to ship.

This is also live, not theoretical. This session's symbol-normalization event had the ExitMonitor auto-close three legacy positions (two synthetic take-profits, one real stop-loss). That demonstrates the close path is wired end-to-end and that position-destructive automation already fires on real positions — the same `request_close` path FLATTEN drives. The control is hot.

### What the system does today

**The exact authorization model on `feat/snappy-honest-edge` today** (`services/api_gateway/src/routes/commands.py`):

Every call to `/commands/kill-switch` (GET and POST) requires authentication via `get_current_user` (`services/api_gateway/src/deps.py:105-109`) — an unauthenticated request gets 401. Beyond that, verbs split into two tiers:

- **Open to ANY authenticated user (pull the brake):**
  - `level=STOP_OPENING` — block new entries.
  - `level=DE_RISK` — cancel resting orders / halt averaging-in.
  - Legacy `active=true` (maps to STOP_OPENING, `commands.py:146-152`).
  These are non-destructive escalations: they stop *new* risk, they don't touch existing positions or release someone else's halt. No operator check is applied.

- **Operator-gated (floor it or release it):**
  - `level=NEUTRALIZE` and `level=FLATTEN` — position-destructive (close other users' positions via the HaltController).
  - `level=NONE` — clears the halt (silently resumes trading someone else stopped).
  - Legacy `active=false` (clears the halt, `commands.py:154`).
  The gate is `if level.at_least(HaltLevel.NEUTRALIZE) or level == HaltLevel.NONE` (`commands.py:136`), which calls `_require_operator(...)` → 403 unless `is_operator(user_id)` (`commands.py:115-123`).

**What "operator" means:** `is_operator(user_id)` returns `True if allow is None else user_id in allow` (`commands.py:47-52`). The allowlist comes from the typed setting `KILL_SWITCH_OPERATORS: Optional[str]` (`libs/config/settings.py:84`, env `PRAXIS_KILL_SWITCH_OPERATORS`, comma-separated user_ids). When the setting is `None` or blank, `_operator_allowlist()` returns `None` (`commands.py:42-44`), and `is_operator` short-circuits to `True` for **everyone**. That is the shipped default: the setting is `Field(default=None)`.

**So today, unconfigured = single-operator mode:** every authenticated user can FLATTEN the entire book, NEUTRALIZE it, and clear any halt. There is no role table, no per-level operator distinction, and no admin/owner concept in the gate.

**Secondary effects of the same flag:** the kill-switch activity log (actor user_ids + free-text reasons) is operator-only when an allowlist *is* configured — `get_kill_switch_status` blanks `recent_log` for non-operators (`commands.py:85-87`). Unconfigured, everyone sees the full actor-attributed log. A post-auth per-user rate bucket caps halt *writes* at 10/min (`commands.py:22`, `_kill_switch_write_bucket`) to stop log-flooding, but this is a flood guard, not an authorization control — it does not restrict *who* may FLATTEN, only how fast.

**Defense-in-depth that exists regardless of operator config:** the FE FLATTEN gate requires a typed "FLATTEN" confirmation and a reason, and is structurally unreachable via Enter-key fallthrough (`frontend/components/shell/KillSwitchModal.tsx:198-214, 272-273`). The hot-path read is fail-safe (Redis unreachable → block trading, `kill_switch.py:66-72`), and `get_level` fail-safe is deliberately non-destructive (Redis error → STOP_OPENING, never auto-FLATTEN off a blip, `kill_switch.py:81-88`). These are UI/runtime safeguards, not server-side authorization — a direct API call bypasses the typed confirmation entirely.

### How each choice propagates through the system

The blast radius of the *unconfigured* default is the whole platform's open book. Because the halt is one global Redis key and `flatten_all_open` is unscoped (`halt_controller.py:163` → `position_repo.py:122`), any authenticated account that POSTs `level=FLATTEN` triggers `request_close(... close_reason="halt_flatten")` against every OPEN position on the next HaltController tick (`halt_controller.py:103-106, 159-180`). With the open OAuth upsert (`auth.py:95-112`), the set of "authenticated accounts" is "anyone who can complete a Google login," not "the operator." That is the cross-user destructive hole.

How each choice propagates:

- **Leave unconfigured (a):** zero code/config change. The blast radius stays "any authenticated user → liquidate everyone." Safe only while the deployment is genuinely single-human and login is not exposed to anyone else. The moment a second account exists — invited, shared, or an attacker who completes OAuth — the hole is live and there is no server-side backstop.

- **Configure the allowlist now (b):** set `PRAXIS_KILL_SWITCH_OPERATORS` to the architect's user_id. The gate at `commands.py:136-141` and `154` now denies NEUTRALIZE/FLATTEN/NONE to anyone not on the list (403), and `recent_log` is hidden from non-operators (`commands.py:85-87`). No code changes — the machinery already reads the setting. This closes the hole for the destructive verbs while keeping STOP_OPENING/DE_RISK open to all (anyone can still pull the brake). The cost is operational: the operator must know their `uuid.uuid5`-derived user_id (`auth.py:88-90`), which is not surfaced anywhere obvious, so a misconfiguration risks locking the operator *out* of FLATTEN/clear.

- **Role-based model (c):** introduces a `role` column or a roles table and a DB-backed `is_operator`. Touches `auth.py` (assign role on upsert), `deps.py` (load role), `commands.py` (consult role not env), plus a migration and likely an admin UI to grant roles. Largest surface; meaningful only once there are enough users that an env list is unwieldy.

- **Tiered operators (d):** different allowlists per halt level (e.g. anyone de-risks, a small list NEUTRALIZEs, one person FLATTENs). Requires generalizing `_require_operator` from one boolean to per-level membership and adding settings/role fields. The ladder already exists (`HaltLevel` rank, `enums.py:103-112`); the authorization layer would mirror it. Adds policy nuance but more config to get wrong.

Note one asymmetry worth flagging as a judgment call: STOP_OPENING/DE_RISK are open to all by design, so in *any* multi-user model a non-operator can still halt new entries platform-wide and cannot be stopped from doing so by a non-operator (only an operator can clear it via NONE). That is intentional ("anyone may pull the brake") but means a hostile authenticated user can still DoS trading by repeatedly halting — the rate bucket (10/min) bounds the spam, not the effect.

### Options

#### (a) Leave unconfigured — single-operator mode

*Ship as-is: empty PRAXIS_KILL_SWITCH_OPERATORS, every authenticated user is the operator.*

**Pros:**

- Zero work; matches the genuine single-user reality today.
- No lock-out risk — the operator can always FLATTEN and clear halts.
- Halt control is never un-pullable or un-clearable, which the original ruling judged worse than a tierless control.

**Cons:**

- Cross-user destructive hole the instant a 2nd account exists; multi-user is one open OAuth upsert away (auth.py:95-112), not a gated migration.
- No server-side backstop — a direct API call bypasses the FE typed-confirmation gate and FLATTENs the whole book.
- Full actor-attributed activity log is visible to every authenticated user (no CWE-200 protection until the list is set).

**Changes required:** none — current behavior (settings.py:84 default=None).

#### (b) Configure an explicit env allowlist now

*Set PRAXIS_KILL_SWITCH_OPERATORS to the architect's user_id; machinery already reads it.*

**Pros:**

- Closes the destructive-verb hole immediately with no code change — the gate at commands.py:136/154 already enforces it.
- Activates operator-only activity-log hiding (commands.py:85-87).
- Keeps STOP_OPENING/DE_RISK open to all (anyone can still pull the brake), preserving the safety intent.
- Trivially reversible; right-sized for the current 1–few user scale per the 2026-06-11 ruling's own trade-off note (DECISIONS.md:476-480).

**Cons:**

- Operator must discover their uuid5-derived user_id (auth.py:88-90), which isn't surfaced — misconfig risks locking the operator out of FLATTEN/clear.
- Env config, not a real role system — doesn't scale to many users and lives outside the DB/audit trail.
- Still global: an on-list operator FLATTENs ALL users' positions, not just their own (acceptable while one human owns the book).

**Changes required:** Set env PRAXIS_KILL_SWITCH_OPERATORS=<architect user_id> in the deployment. Optionally surface the current user_id in /auth/me or the UI so the operator can self-identify it without DB access.

#### (c) DB-backed role model

*Add a role column/table; is_operator consults the DB instead of an env string.*

**Pros:**

- Scales to many users; roles managed in-app, in the audit trail, not in env.
- Natural home for future authz (who may edit profiles, view per-user PnL, etc.).
- Roles survive redeploys and are queryable/auditable.

**Cons:**

- Largest surface: migration + auth.py upsert + deps.py role load + commands.py rewrite + an admin grant path.
- Over-engineered for today's user count; the env list already closes the hole.
- Needs its own access control (who grants roles?) — recurses the same problem one level up.

**Changes required:** New migration (role column or user_roles table), role assignment in auth.py:95-112 upsert, role load in deps.py, rewrite is_operator/_require_operator in commands.py, plus an admin UI/endpoint to grant roles.

#### (d) Tiered operators per halt level

*Different allowlists per rung — all de-risk, a few NEUTRALIZE, one FLATTENs.*

**Pros:**

- Finest-grained least-privilege; matches the existing HaltLevel severity ladder (enums.py:103-112).
- Reserves the single irreversible verb (FLATTEN) for the narrowest set, mirroring the auto-FLATTEN gate philosophy (DECISIONS.md:236-247).

**Cons:**

- Most config to author and the easiest to misconfigure (e.g. nobody able to FLATTEN in a real tail event).
- Premature: there is no second operator yet, let alone a need to stratify them.
- Generalizes _require_operator from a boolean to per-level membership — more code than (b) for no current payoff.

**Changes required:** Per-level operator settings/roles, generalize _require_operator (commands.py:115-123) to per-level membership checks, and per-level config in settings.py.

### Recommendation

**Recommend (b): configure the explicit env allowlist now**, with one supporting change — surface the logged-in user's `user_id` somewhere the operator can read it (e.g. in `/auth/me` output or a Settings panel) so they can populate `PRAXIS_KILL_SWITCH_OPERATORS` without querying the DB.

The honest rationale: option (b) closes the only genuinely dangerous gap (cross-user FLATTEN / silent halt-clear) at essentially zero engineering cost, because the authorization machinery is already built and wired — it is being held open only by an empty config value. The original 2026-06-11 ruling left it unconfigured to avoid an un-clearable brake on a single-user box (`DECISIONS.md:461-464`), and that reasoning was correct *for that moment*. But the same file's trade-off note already concedes the env allowlist is "fine at current scale, revisit with multi-user auth" (`DECISIONS.md:476-480`) — and the decisive fact this analysis surfaces is that "multi-user" is not a future code milestone. The OAuth callback open-upserts any account that logs in (`auth.py:95-112`), so the system is *already* structurally multi-user; only the deployment's exposure (a single human with the login) keeps it safe. Relying on "we only have one user" as the security boundary for a control that liquidates the entire book is the kind of implicit assumption that fails silently the first time the architect shares a screen, invites a collaborator, or someone discovers the OAuth flow.

I explicitly do **not** recommend (c) or (d) yet: both solve a scaling problem that does not exist, and (c) recurses the authz question (who grants roles?) while (d) risks a worse failure — nobody authorized to FLATTEN during a real tail. The right sequencing is (b) now, then (c) only when user count makes an env list unwieldy or when broader role-based authz is needed for other surfaces (profile editing, per-user PnL visibility), at which point the kill-switch role folds into that work.

**When the recommendation flips:** stay on (a) only if you can guarantee the deployment will never have a second authenticated account before (b) is applied — i.e. the login surface is not reachable by anyone else and won't be. Jump straight to (c)/(d) if a multi-user rollout with several operators is imminent in the same cycle, so you don't pay for the env-list step twice. The mitigating caveat for (b): confirm the operator's user_id is correct *before* relying on it, because a wrong value locks the only human out of FLATTEN and clear — test it by setting a halt and clearing it once after configuring.

### Coupling to the other decisions

This decision is coupled to several others in the set:

1. **Kill-switch operator (this) ↔ the live auto-close event / go-live readiness.** This session's ExitMonitor auto-close proved the position-destructive close path (`request_close`, the same path FLATTEN drives) fires on real positions. The authorization gap matters more the closer the system gets to live capital — so this decision should be settled *before* any go-live or fee/capital decision (Decision 5) that puts real money behind the open book FLATTEN can liquidate.

2. **↔ CODEOWNERS / branch-protection / org-side multi-user (Decision 4).** The 2026-06-11 ruling explicitly cross-references the org-side multi-user input (`DECISIONS.md:478-480`). The operator allowlist is the *runtime* half of the same "who is authorized to do destructive things" question that CODEOWNERS/branch-protection answers at the *repo* level. If the multi-user/org decision lands first and defines real roles, this decision should align to it (favoring (c)); if it doesn't, (b) stands alone.

3. **↔ EN-W3 priority / Phase-4 sequencing (Decision 1).** This is a small, high-leverage config change (b) versus a larger build (c/d). Where it sits in the Phase-4 priority order determines whether the cheap hole-closing happens now or waits behind edge/strategy work. Given the negative-OOS-edge headline, capital at risk is currently low, which *reduces* the urgency of (b) somewhat — but the open OAuth upsert keeps it non-trivial regardless.

Ordering implication: apply (b) immediately (it gates nothing else and unblocks safe multi-user exposure), and defer (c)/(d) to ride along with whichever of Decisions 4 / org multi-user lands the real role model.

### Cost of leaving it undecided

Leaving this undecided keeps the cross-user destructive hole armed: the platform is structurally multi-user (open OAuth upsert, `auth.py:95-112`), so any account that authenticates can today POST `level=FLATTEN` and liquidate the entire open book — across all profiles and all users — with no server-side authorization backstop (`commands.py:47-52` short-circuits to operator=true for everyone). The FE typed-confirmation gate does not protect a direct API call. Concretely, what stays at risk: (1) a shared, invited, or compromised second login can FLATTEN or NEUTRALIZE positions it does not own, or silently clear a halt the real operator set; (2) the full actor-attributed activity log (user_ids + free-text reasons) leaks to every authenticated user until an allowlist is configured (CWE-200). 

The degradation is asymmetric and cheap to avoid: the *fix* (option b) is a single env value the machinery already consumes, so the cost of leaving it undecided is borne entirely as standing risk, not as accumulating work. The one real cost of acting hastily is lock-out — configuring the wrong user_id removes the only human's ability to FLATTEN or clear a halt — which is why the recommendation pairs (b) with surfacing the user_id and a verify-once step. Net: the cost of leaving it undecided (a live liquidation/clear hole that grows the moment login is shared) materially exceeds the cost of deciding it.

### Evidence

*Grounding citations (verified against the tree at `7b8361d`):*

- `services/api_gateway/src/routes/commands.py:29-44 (_operator_allowlist returns None when unconfigured)`
- `services/api_gateway/src/routes/commands.py:47-52 (is_operator: True if allow is None else membership)`
- `services/api_gateway/src/routes/commands.py:115-123 (_require_operator → 403)`
- `services/api_gateway/src/routes/commands.py:136-141 (gate: at_least(NEUTRALIZE) or NONE requires operator)`
- `services/api_gateway/src/routes/commands.py:146-160 (legacy binary: active=true ungated STOP_OPENING; active=false operator-gated)`
- `services/api_gateway/src/routes/commands.py:85-87 (recent_log blanked for non-operators)`
- `services/api_gateway/src/routes/commands.py:22 (10/min post-auth write bucket)`
- `libs/config/settings.py:79-84 (KILL_SWITCH_OPERATORS: Optional[str] = Field(default=None))`
- `services/hot_path/src/kill_switch.py:24 (single global KILL_SWITCH_KEY)`
- `services/hot_path/src/kill_switch.py:90-119 (set_level; NEUTRALIZE+ logged CRITICAL; reason truncated to 256)`
- `services/hot_path/src/kill_switch.py:56-88 (is_active fail-safe blocks; get_level fail-safe non-destructive STOP_OPENING)`
- `libs/core/enums.py:89-112 (HaltLevel ladder NONE/STOP_OPENING/DE_RISK/NEUTRALIZE/FLATTEN + rank/at_least)`
- `services/pnl/src/halt_controller.py:103-106,159-180 (FLATTEN → flatten_all_open closes every open position via request_close)`
- `libs/storage/repositories/position_repo.py:117-123 (get_open_positions with no profile_id → SELECT * WHERE status='OPEN', unscoped)`
- `services/api_gateway/src/routes/auth.py:64-118 (OAuth callback open-upserts any account into users; no invite/allowlist gate)`
- `services/api_gateway/src/deps.py:105-109 (get_current_user: 401 if no user_id, else any authenticated user)`
- `frontend/components/shell/KillSwitchModal.tsx:198-214,272-273 (FLATTEN typed-confirm gate; not a <form>)`
- `frontend/lib/api/client.ts:659-674 (killSwitchSetLevel posts {level, reason})`
- `docs/DECISIONS.md:445-484 (2026-06-11 kill-switch operator authorization ruling + trade-off note)`
- `docs/DECISIONS.md:214-272 (2026-06-10 tiered flatten-authority ruling)`

---

## Decision 4 — CODEOWNERS handle + branch protection on main

### Why this decision exists

The repository carries a fully-built governance scaffold that is, today, *decorative* — it requests nothing and blocks nothing. `.github/CODEOWNERS` declares the architect (`@praxis-architect`) as a required reviewer on every money-at-risk path (`services/execution`, `services/pnl`, `services/risk`, `services/strategy`, `libs/core`) and on the binding contracts (`libs/messaging/channels.py`, `libs/core/enums.py`, `libs/core/schemas.py`, `migrations/**`, `docs/DECISIONS.md`). But CODEOWNERS only requests review when GitHub branch protection has "Require review from Code Owners" turned on. I verified directly against the GitHub API: `repos/stephenmt25/agentic-trading-platform/branches/main/protection` returns **HTTP 404 "Branch not protected"**. So the owner-review requirement is currently a comment, not a control — anyone with push access (today, the solo maintainer) can merge a change to the order-execution path with zero review and a red CI run, and nothing stops them.

This was a deliberate, time-boxed deferral, not an oversight. The 2026-06-10 branch-model decision (`docs/DECISIONS.md:311-315`) explicitly held the placeholder-swap and branch-protection enablement until "the slice is otherwise complete so we don't gate our own in-progress PRs." That rationale has now expired: the debt burn-down made every CI gate blocking and green on `feat/snappy-honest-edge` — mypy (0/275), ESLint (0/0), 24 integration tests, plus the float/channel/skill-drift guards (commits `b08e91b`, `7b8361d`; `ci.yml:43`, `ci.yml:234`). The slice is at the merge boundary (35 commits ahead of `main` at `ddf9db1`). The gates that branch protection would *enforce as required status checks* finally exist and are trustworthy.

What is fundamentally at stake is the difference between *having* a quality bar and *holding* one. The CI gates are green on a branch, but green-on-a-branch is a property a human chooses to honor; branch protection makes it a property the platform enforces at the merge button. For a platform whose stated north-star is "safe + autonomous trading" and whose CLAUDE.md §5 treats execution/pnl/risk/strategy as security-sensitive, the asymmetry is acute: the live ExitMonitor event this session (auto-closing dash-symbol positions at +635% / +63,649% synthetic and -15.2% real after a symbol-normalization change made them priceable) is exactly the class of money-path change that should not reach `main` without a human looking at it. The decision is whether to convert the existing scaffold into a real control now, partially, or not yet.

Note also a coupled cleanliness issue I found: `CONTRIBUTING.md:47-49` still describes mypy as an "advisory (non-blocking) check while the codebase finishes its typing cleanup," which is now stale — `ci.yml:43` makes mypy blocking. Whatever is decided here should sweep that line, because CONTRIBUTING is the document that tells a future contributor what actually gates a merge.

### What the system does today

**Branch protection: OFF.** Verified live against the GitHub REST API — `GET repos/stephenmt25/agentic-trading-platform/branches/main/protection` → `404 {"message":"Branch not protected"}`. No required reviews, no required status checks, no CODEOWNERS enforcement on `main`.

**CODEOWNERS: present but inert.** `.github/CODEOWNERS:9` sets `*  @stephenmt25` as the default owner. Lines 12-16 add `@praxis-architect` as a co-owner on the money-at-risk paths; lines 19-22 add it on the binding contracts (`channels.py`, `enums.py`, `schemas.py`, `migrations/**`); lines 25-28 cover `DECISIONS.md` and `CLAUDE.md`. The file's own header (`.github/CODEOWNERS:4-6`) warns that `@praxis-architect` is a placeholder and that "GitHub will silently fail to request the review" if it is left unreplaced under enforcement. So even if protection were enabled today, the architect line would either be ignored (invalid handle → silent no-op) or, worse, block all money-path merges with an un-satisfiable review requirement.

**CI gates: green and blocking, but only by convention.** `ci.yml` runs lint (black/isort/ruff + mypy via poetry, `ci.yml:34-62`), the float/channel/skill-drift guards (`ci.yml:71-87`), unit tests, 24 integration tests against Redis+TimescaleDB containers (`ci.yml:125-182`), security-scan (bandit/safety, non-blocking by `|| true`), frontend ESLint+tsc (`ci.yml:216-243`), and a docker base-image build. CI triggers on PRs into `main`, `develop`, and `feat/**` (`ci.yml:3-7`). All of this runs, but because `main` is unprotected, a red run does not block a merge — honoring CI is currently a discipline, not a gate.

**Process docs describe enforcement that does not exist yet.** `CONTRIBUTING.md:84-85` tells contributors "CODEOWNERS will auto-request architect review for money-at-risk paths" — true only once protection is on. The PR template (`.github/PULL_REQUEST_TEMPLATE.md:12-30`) already collects the risk tier and the financial-precision checklist, so the human-review *inputs* exist; only the enforcement hook is missing.

**Maintainer topology: solo.** The repo owner is `stephenmt25`, who is also the default CODEOWNER and the only contributor on the branch. There is no second human who can satisfy a "require review from someone other than the author" rule today.

### How each choice propagates through the system

**Enabling required-review + required-status-checks (Option a)** changes the merge mechanics for `main`, not the runtime. Concretely: (1) GitHub starts requiring a CODEOWNERS-matched approval on any PR touching `services/{execution,pnl,risk,strategy}`, `libs/core`, the three contract files, `migrations/**`, or the decision/CLAUDE docs — i.e. every path CLAUDE.md §5 already flags as security-sensitive. (2) The named CI jobs become *required status checks*, so a red lint/guard/test run blocks the merge button rather than relying on a human to notice. The blast radius is purely process/CI-config: no service code, no Redis channel, no schema changes. It does require the `@praxis-architect` placeholder to be replaced with the architect's real handle first (or a `@org/architects` team) — otherwise the money-path rules become un-satisfiable and freeze all merges to those paths. It also requires choosing which job *names* are required; the job ids are `lint`, `guards`, `test-unit`, `test-integration`, `frontend-lint` (and optionally `docker-build`, `security-scan`) per `ci.yml`. A subtlety: required-status-checks pin by job name, so renaming a CI job later silently drops it from the required set until re-added.

**Enabling required-status-checks only (Option b)** holds the *green-CI* line — no PR merges to `main` with a red mypy/ESLint/guard/test run — without making the architect a blocking reviewer. This is the half that no longer depends on a second human or on a valid CODEOWNERS handle, so it is immediately satisfiable by the solo maintainer. It leaves the human-review requirement on money-at-risk paths unenforced (CODEOWNERS stays inert), but it captures most of the regression-prevention value the just-finished burn-down created.

**Deferring entirely (Option c)** leaves `main` exactly as it is: shippable-by-discipline. The CI gates keep running and stay green by the maintainer's habit, but the platform enforces nothing. Given the slice is about to merge to `main`, this is the option that lets the symbol-normalization / ExitMonitor class of money-path change land with no required review and no required green run.

Across all three, the frontend redesign line (`redesign/frontend-v2`) and the per-slice `feat/**` integration branches are unaffected unless their protection is separately configured — branch protection rules are per-branch. CONTRIBUTING.md's branch model (integration branch → squash PRs → merge to `main` when green+verified) is designed for exactly this enforcement and would finally have teeth.

### Options

#### Enable now: real handle + required-review + required-status-checks

*Replace @praxis-architect with the architect's real handle, turn on 'Require review from Code Owners' and required status checks on main.*

**Pros:**

- Holds a real line on the exact money-at-risk paths CLAUDE.md §5 flags — order execution, pnl, risk, strategy, core types, contracts, migrations.
- Required green CI before merge: red mypy/ESLint/guard/test run blocks the merge button, locking in the burn-down the session just completed.
- The governance scaffold (CODEOWNERS, PR template risk-tier + financial-precision checklist) stops being decorative and becomes the control it was written to be.
- Cheapest moment to do it — the slice is at the merge boundary, so it gates no in-progress PR (the original deferral rationale, docs/DECISIONS.md:311-315, has expired).

**Cons:**

- Architect becomes a required reviewer on every money-path PR → latency on the highest-churn area of the codebase; a busy/absent architect stalls merges.
- Solo-maintainer bootstrapping problem: GitHub can require a CODEOWNERS approval, but if the architect is the only other owner and is unavailable, the maintainer either waits or uses admin-override (which hollows out the control).
- Hard-fails closed if the placeholder is mistyped or the architect lacks repo access — money-path merges freeze until fixed.
- Couples merge cadence to a second human before that human's review bandwidth is established.

**Changes required:** Edit .github/CODEOWNERS: replace @praxis-architect (lines 12-28) with the architect's real GitHub handle or a @org/architects team. Configure branch protection on main via GitHub settings or `gh api`: require pull request reviews + require review from code owners + require status checks (lint, guards, test-unit, test-integration, frontend-lint). Decide on the 'do not allow administrators to bypass' toggle. Sweep stale CONTRIBUTING.md:47-49 (mypy is now blocking, not advisory).

#### Enable required-status-checks only (green-CI gate, no required review)

*Turn on required status checks on main; do NOT enable required CODEOWNERS review yet.*

**Pros:**

- Immediately satisfiable by a solo maintainer — no dependency on a second human or a valid architect handle.
- Captures the bulk of the burn-down's value: no PR merges to main with a red lint/guard/test run, so the green baseline can't silently regress.
- Zero merge-latency cost — the maintainer still self-merges, just only on green.
- Reversible and incremental: required-review can be layered on later once the architect's handle and review bandwidth are confirmed.

**Cons:**

- Money-at-risk paths still get no enforced human review — the ExitMonitor / symbol-normalization class of change can still land unreviewed.
- Leaves CODEOWNERS inert, so the §5 security-review intent remains documented-but-unenforced.
- Half-measure: the governance story is 'CI is enforced, human review is not,' which is exactly inverted from where the highest-risk paths want the strongest control.
- Status-checks pin by job name; a later CI job rename silently drops the check until re-added (a quiet failure mode under this option too).

**Changes required:** Configure branch protection on main with required status checks only (lint, guards, test-unit, test-integration, frontend-lint) and require-branches-up-to-date if desired. Leave CODEOWNERS as-is (still inert) or replace the handle now for a later flip. Sweep stale CONTRIBUTING.md:47-49.

#### Defer entirely

*Leave main unprotected; keep honoring CI green by maintainer discipline.*

**Pros:**

- Zero process friction — fits a solo, high-velocity, pre-multi-user phase.
- No bootstrapping awkwardness of being one's own required reviewer.
- Nothing to maintain (no required-job-name list to keep in sync with ci.yml).

**Cons:**

- Green CI stays a convention, not a control — a red run can still merge to main; the entire burn-down's enforced value is left on the table.
- Money-at-risk paths get no enforced review at the precise moment the slice (incl. money-path changes like symbol normalization → ExitMonitor auto-close) is about to hit main.
- The CODEOWNERS + PR-template scaffold and the docs/DECISIONS.md:311-315 follow-up remain unfulfilled — the deferral's own end-condition (slice complete) has been reached and ignored.
- Misses the cheapest enablement window; re-deferring just pushes the same decision into a busier future.

**Changes required:** None — current behavior. Optionally update docs/DECISIONS.md:311-315 to record a re-deferral with a new trigger condition so the follow-up doesn't silently rot.

### Recommendation

**Recommended: Option (b) now, Option (a) as the immediate next step once the architect's handle is confirmed.** This is a sequencing recommendation, not a refusal of full enforcement.

The honest reality of a solo-maintained repo is that "require review from code owners" where the only other owner is an intermittently-available architect creates a real bootstrapping bind: GitHub will block money-path merges until the architect approves, and the escape valve (admin bypass) quietly defeats the control you just turned on. So enabling required-review *today* risks either stalling the very merge this slice is about to make, or training the maintainer to bypass — both worse than not having it. Required-status-checks, by contrast, has no human dependency: it is satisfiable by the solo maintainer on every green run, it is immediately reversible, and it locks in the single most valuable thing the burn-down produced — a green CI baseline that can no longer silently regress because a red run can no longer reach `main`. That is the part of the control that is unambiguously net-positive right now.

I would pair (b) with the *non-blocking* half of (a): replace the `@praxis-architect` placeholder with the architect's real handle (or a `@org/architects` team) in the same change, so CODEOWNERS still *auto-requests* review (a notification, not a block) on money-at-risk paths. That gives the architect visibility on every execution/pnl/risk/strategy/migrations PR without holding the merge hostage — and it makes the flip to full required-review a one-toggle operation the moment the architect confirms they want to be a blocking gate and have the bandwidth for it.

**The recommendation flips to Option (a) outright if any of these hold:** the architect explicitly wants to be a required reviewer and commits to a review SLA; a second maintainer joins (the bootstrapping bind disappears the moment "require review from someone other than the author" is satisfiable by a real human); or the repo moves toward any live-trading / multi-user posture, where an unreviewed money-path merge is no longer an acceptable residual risk. Given the north-star is explicitly "go live only when proven," (a) is the destination — (b)+auto-request is just the honest on-ramp that doesn't pretend a solo repo has two humans. **Do not choose (c):** the deferral's own end-condition (slice complete, CI green+blocking) has been met per docs/DECISIONS.md:311-315, and re-deferring at the cheapest enablement window only pays the cost later at a busier time. Whatever is chosen, sweep the stale CONTRIBUTING.md:47-49 mypy-is-advisory line in the same change.

### Coupling to the other decisions

This decision is the *enforcement substrate* for several others in the set and should be sequenced accordingly:

- **Coupled to (6) merge-timing of feat/snappy-honest-edge → main.** Branch protection should be enabled at the merge boundary, not mid-slice — that was the entire deferral rationale (docs/DECISIONS.md:311-315). If the slice merges to `main` *before* protection is on, the first enforced PR is the next one, and this slice lands ungated. So the natural order is: decide protection → enable required-status-checks → merge the slice as the first gated merge (or the last ungated one, depending on timing). These two decisions must be resolved together.

- **Coupled to (4-self) the CI gates being green+blocking.** Required-status-checks is only meaningful because the gates exist and are trustworthy now (commits b08e91b, 7b8361d). The required-job list pins to `ci.yml` job names — if those jobs are renamed or restructured by any other decision, the required set must be updated in lockstep or the check silently drops.

- **Hard dependency on the real architect handle.** Option (a)'s required-review half cannot be enabled until `@praxis-architect` (`.github/CODEOWNERS:12-28`) is replaced with a valid handle/team. This is an external input from the architect — it gates (a) but not (b).

- **Coupled to (3) kill-switch operator gate / (1) EN-W3 priority / (2) EN-W2 verdicts.** Those are about runtime/operational control and trading direction; this decision is about *who may change that code*. They are orthogonal in mechanism but aligned in intent — the kill-switch operator allowlist (docs/DECISIONS.md:478-480 explicitly notes "CODEOWNERS/branch-protection partner input already covers the org side") and CODEOWNERS are the two halves of a single governance posture: operational authority at runtime, change authority at merge. Decide them with one consistent answer to "is this still a single-operator/solo posture, or are we standing up real roles?"

- **Informs (5) capital/fees indirectly:** none mechanically, but the same single-maintainer-vs-multi-user inflection that flips this recommendation to (a) is the inflection that makes capital-at-risk review non-optional.

### Cost of leaving it undecided

Leaving this undecided keeps `main` in a state where green CI is a habit, not a control: a future PR (or a hurried fix to the order-execution path) can merge with a red mypy/ESLint/guard/test run and nobody is structurally stopped. Every dollar of the just-finished debt burn-down — mypy 0/275, ESLint 0/0, 24 integration tests, the float/channel guards — is held only by the maintainer's discipline, and the first lapse re-opens the baseline silently. Concretely, the regression-prevention value the session created is *unrealized* until a required-status-check exists.

It also leaves the §5 security-review intent permanently aspirational on the highest-risk paths. The CODEOWNERS scaffold, the PR template's risk-tier and financial-precision checklist, and the CONTRIBUTING promise that "CODEOWNERS will auto-request architect review" all describe a control that does not fire — so a money-path change (e.g. the symbol-normalization edit that this session made three positions priceable and triggered auto-closes at +635% / +63,649% / -15.2%) can reach `main` with zero required review. The architect's name is on those paths in the file but has no power over them in the platform.

Finally, the deferral itself rots. docs/DECISIONS.md:311-315 set the enablement trigger to "slice complete"; that condition is now met, and an undecided state means the follow-up sits unfulfilled with no new trigger recorded — the classic way a deliberate deferral quietly becomes a permanent gap. And the stale CONTRIBUTING.md:47-49 mypy-advisory line keeps misinforming any future contributor about what actually gates a merge.

### Evidence

*Grounding citations (verified against the tree at `7b8361d`):*

- `.github/CODEOWNERS:4-6 (placeholder warning: @praxis-architect must be replaced or GitHub silently fails to request review)`
- `.github/CODEOWNERS:9 (default owner * @stephenmt25 — the solo maintainer)`
- `.github/CODEOWNERS:12-16 (money-at-risk paths: execution/pnl/risk/strategy/libs-core co-owned by @praxis-architect)`
- `.github/CODEOWNERS:19-22 (binding contracts: channels.py/enums.py/schemas.py/migrations co-owned)`
- `.github/CODEOWNERS:25-28 (DECISIONS.md, CLAUDE.md co-owned)`
- `GitHub API: GET repos/stephenmt25/agentic-trading-platform/branches/main/protection → HTTP 404 {"message":"Branch not protected"} (verified live this session)`
- `docs/DECISIONS.md:311-315 (2026-06-10: branch-protection + placeholder-swap explicitly DEFERRED to end of slice 'so we don't gate our own in-progress PRs')`
- `docs/DECISIONS.md:478-480 (kill-switch decision notes CODEOWNERS/branch-protection 'already covers the org side' — coupling to governance posture)`
- `ci.yml:3-7 (CI triggers on PRs into main/develop/feat/**)`
- `ci.yml:43-62 (mypy now BLOCKING as of 2026-06-13, run via poetry)`
- `ci.yml:71-87 (float/channel guards + skill-drift guard, blocking)`
- `ci.yml:125-182 (24 integration tests against Redis+TimescaleDB containers)`
- `ci.yml:234-243 (ESLint BLOCKING as of 2026-06-13, baseline 300→0/0)`
- `CONTRIBUTING.md:47-49 (STALE: still calls mypy 'advisory (non-blocking)' — contradicts ci.yml:43; sweep in same change)`
- `CONTRIBUTING.md:84-85 (claims CODEOWNERS auto-requests architect review — true only once protection is on)`
- `.github/PULL_REQUEST_TEMPLATE.md:12-30 (risk-tier + financial-precision checklist already collected — review inputs exist, enforcement hook missing)`
- `git: 7b8361d head, 35 commits ahead of main=ddf9db1; commits b08e91b/7b8361d made gates blocking`

---

## Decision 5 — Capital / fees confirmation ($10k @ Binance VIP0)

### Why this decision exists

This decision exists because EN-W4 (Yield Harvester + auto-deprecation + 60-day soak) cannot do honest expected-value math without two anchored inputs: the real working capital and the real fee schedule. EV math is a cost-survival test — "does this strategy's edge survive its own transaction costs?" — and that test is only meaningful against concrete numbers. Today both numbers are *assumptions*: `$10k @ Binance VIP0` is logged as FLAGGED assumption #7 (`docs/DECISIONS.md:381`) and is called out as unconfirmed in every recent session plan (`docs/NEXT-SESSION-PLAN-2026-06-10.md:197`, `-06-11.md:93`, `-06-12.md:99`, `-06-13.md:77`).

The reasoning chain runs through the cost stack. Crypto taker fees scale with VIP tier: Binance spot VIP0 is ~10 bps (0.10%) per side; higher VIP tiers (and BNB-discount / maker rebates) drop that materially. A round-trip at VIP0 costs ~20 bps before slippage and funding; at a higher tier it can be half that or less. A mean-reversion or funding-harvest strategy whose gross edge is small enough (the soak RSI strategy's OOS sharpe is already −4.0, per `docs/DECISIONS.md:554`) lives or dies on that spread — a strategy that is EV-positive at VIP3 fees can be EV-negative at VIP0. So the *answer* to "is there edge after costs" literally changes sign with the fee assumption. You cannot auto-deprecate (EN-W4's job: `decay_tracker` → `KillSwitch.set_level(NEUTRALIZE)`) on a cost basis that is itself a guess.

The capital number matters for a different reason: it sets the denominator for compounding/EV projections and it is the value the binding RiskGate and daily-loss circuit-breaker already use (`docs/DECISIONS.md:96`). The Yield Harvester's delta-neutral pairs (spot long + ISOLATED perp short, per the 2026-06-11 netting decision at `docs/DECISIONS.md:351`) pay *double* fees/funding vs netting by design — that doubled cost is only tolerable if the capital base and fee tier are pinned, because the harvester's whole thesis is a thin funding spread net of those doubled costs.

What is fundamentally at stake: if EN-W4 ships its EV/auto-deprecation logic against an un-pinned or wrong fee tier, it will either keep strategies that are actually loss-making (fees underestimated) or kill strategies that actually work at the real tier (fees overestimated). Both are silent, expensive errors in an autonomous system whose north-star is honest paper fidelity before going live.

### What the system does today

Today the system runs on two *separate, non-contradictory* capital constants plus a hardcoded fee table — none of which is tied to a confirmed "$10k @ VIP0" decision.

**Per-profile notional ($10k).** `libs/core/notional.py:21` defines `NOTIONAL_PER_ALLOC_UNIT_USD = Decimal("10000")` as the single source of truth for the per-allocation-unit notional. A profile with `allocation_pct = 1.0` therefore has $10k of nominal trading capital (`libs/core/notional.py:29`, `profile_notional()` at `:34-71`). This governs *per-profile* gates: the RiskGate exposure-at-notional check fed by `state.notional` (`services/hot_path/src/state.py:39`, `:58`), the validation service's allocation/concentration check (`services/risk/src/__init__.py:72`, `:78-84`), and the daily-loss circuit-breaker denominator in the closer. The 2026-05-05 DECISIONS entry (`docs/DECISIONS.md:78-160`) records that this was reverted from a session-bridge $100k bump back to $10k across all (then five) call sites and collapsed into the one helper, precisely so the gates stop drifting apart.

**Portfolio gross budget ($100k).** `libs/config/settings.py:51` defines `PORTFOLIO_GROSS_BUDGET_USD = Decimal("100000")`. This is a *different governor*: it is the PR4 portfolio-wide cap on total open notional summed across ALL profiles (comment at `settings.py:50`), used by the correlation-cluster cap (`CORRELATION_CLUSTER_CAP_PCT`, `settings.py:55`) and NEUTRALIZE target (`settings.py:63`). So $10k = one profile's allocation unit; $100k = the aggregate ceiling that would allow up to ~10 such profiles before the portfolio gate bites. They are not in tension — they sit at different layers (per-profile vs portfolio-aggregate).

**Fees.** Taker fee is hardcoded as a per-venue table in three independent places, all agreeing on Binance = 0.001 (10 bps): `services/pnl/src/main.py:116-120` (`TAKER_RATES`, BINANCE 0.001 / COINBASE 0.006 / DEFAULT 0.002), `services/execution/src/executor.py:39-46` (`EXCHANGE_FEE_RATES`, identical), and `services/pnl/src/executed_consumer.py:50` (`_DEFAULT_TAKER_RATE = 0.001`). Fees enter live PnL at `services/pnl/src/calculator.py:44` (`fees_exit = cp * qty * taker_rate`; `total_fees = entry_fee + fees_exit`) and the closed-trade write at `services/pnl/src/closer.py:289`. **There is no VIP-tier concept anywhere** — the 10 bps figure is consistent with Binance spot VIP0, but it is a hardcoded constant, not a confirmed tier, and there is no maker/taker split, no BNB discount, no funding-rate model surfaced in fee config. (Judgment: 10 bps ≈ VIP0 taker, so the *value* already matches the assumption; what is missing is the *confirmation* and the *parameterization*.)

**Critical EV gap I verified.** The backtest simulator — the substrate EN-W4 EV math runs on — applies *slippage only, not fees*. `services/backtesting/src/simulator.py:288-299` computes `pnl_pct` off the slipped entry/exit prices with no fee subtraction; the EN-W1 decision documents this explicitly as "gross of exit costs" (`docs/DECISIONS.md:416-419`). So today's OOS edge numbers (RSI sharpe −4.0) are *gross-of-fees*; layering VIP0 round-trip fees on makes them strictly worse, not better.

### How each choice propagates through the system

**If $10k @ VIP0 is confirmed as-is (Option A):** essentially zero code change. The $10k already lives in `libs/core/notional.py:21` and 10 bps already lives in the three fee tables. EN-W4 EV math can be written directly against these constants. Blast radius: documentation only — flip assumption #7 from FLAGGED to CONFIRMED in `docs/DECISIONS.md`. Risk inherited: the fee constant is duplicated in three files, so any *future* tier change touches `pnl/main.py`, `execution/executor.py`, and `pnl/executed_consumer.py` and must stay in sync (the same drift failure mode the notional helper was created to kill, per `docs/DECISIONS.md:128-141`).

**If a different capital tier is chosen (Option B):** change is localized to `libs/core/notional.py:21` for the per-profile unit, and possibly `settings.PORTFOLIO_GROSS_BUDGET_USD` (`settings.py:51`) if the aggregate ceiling should move with it. But a larger capital base may *cross a real VIP threshold* (Binance VIP tiers key off 30-day volume and BNB balance), which would couple this back into the fee tier — so B rarely travels alone.

**If a different venue / fee schedule is chosen (Option C):** the per-venue tables already exist (`TAKER_RATES`, `EXCHANGE_FEE_RATES`) so adding/repricing a venue is a table edit in three files. But anything beyond taker (maker rebates, BNB discount, perp funding for the Yield Harvester legs) has *no home in config today* and would need new fields — funding in particular is the dominant cost for delta-neutral harvest and is currently unmodeled in fee config.

**If fully parameterized (Option D):** introduce `PRAXIS_NOTIONAL_BASE_USD` (already flagged as future work at `docs/DECISIONS.md:152-154`) and a `PRAXIS_FEE_TIER` / structured fee config in `libs/config/settings.py`, then route the three hardcoded fee tables and `notional.py:21` through it. This is the only option that lets EV math be *recomputed* when the tier changes without a code edit, and it would also fix the three-way fee-constant duplication. Blast radius is wider (settings + three services + the notional helper + the simulator, which must finally subtract fees to make the EV baseline honest), but it is mechanical and well-bounded.

**Cross-cutting, all options:** to make EN-W4 EV math *meaningful at all*, the backtest simulator (`simulator.py:288-299`) must start subtracting round-trip fees — otherwise the EV test is run on a gross-of-fees baseline that systematically overstates edge. This is independent of which capital/fee values are chosen and is, in my judgment, the load-bearing change Decision 5 actually unblocks.

### Options

#### A — Confirm $10k @ Binance VIP0 as the binding assumption

*Ratify the values already in the code ($10k per-profile notional, 10 bps Binance taker = VIP0) and flip assumption #7 to CONFIRMED.*

**Pros:**

- Zero rework — $10k is already the single-source constant (libs/core/notional.py:21) and 10 bps is already the Binance rate in all three fee tables.
- Keeps the 3,689 closed BTC trades and the binding RiskGate/circuit-breaker history coherent — they all accrued under $10k (docs/DECISIONS.md:159).
- VIP0 is the most conservative (highest-fee) realistic Binance tier, so EV math computed here is a worst-case floor — a strategy that survives VIP0 fees survives every higher tier.
- Unblocks EN-W4 EV math immediately; matches honest-paper-trading north-star (one real portfolio size).

**Cons:**

- Leaves the taker constant duplicated across pnl/main.py, execution/executor.py, executed_consumer.py — future tier change must hand-sync three files (the exact drift the notional helper was built to prevent).
- Does not by itself fix the simulator's gross-of-fees EV baseline (simulator.py:288-299) — EV math would still need the fee-subtraction change.
- $10k may be unrealistically small for the Yield Harvester's double-fee delta-neutral pairs; thin funding spreads at $10k scale may not clear ISOLATED-margin top-up overhead.

**Changes required:** None to capital/fee values (already in code). Documentation: flip assumption #7 FLAGGED→CONFIRMED in docs/DECISIONS.md. Strongly recommend also doing the simulator fee-subtraction (see cross-cutting impact).

#### B — Different capital tier (e.g. higher base)

*Set a different working-capital base than $10k.*

**Pros:**

- Larger base may make the Yield Harvester's thin funding spreads clear fixed/ISOLATED-margin overhead.
- Localized edit: libs/core/notional.py:21 (and optionally settings.PORTFOLIO_GROSS_BUDGET_USD:51).

**Cons:**

- Breaks coherence with the 3,689-trade history accrued under $10k (docs/DECISIONS.md:159).
- A bigger base can cross a real Binance VIP volume threshold, which would *change the fee tier too* — so B usually drags the fee decision with it rather than standing alone.
- No evidence in repo for any specific alternate number — would be a new unsupported assumption replacing an old one.

**Changes required:** Edit NOTIONAL_PER_ALLOC_UNIT_USD (libs/core/notional.py:21); reassess PORTFOLIO_GROSS_BUDGET_USD; re-derive the implied VIP tier and update the three fee tables if it changes.

#### C — Different venue / fee schedule

*Trade a different venue or apply maker rebates / BNB discount / a non-VIP0 Binance tier.*

**Pros:**

- Lower effective fees (maker rebates, BNB discount, higher VIP) could rescue a marginally-negative strategy's EV.
- Per-venue taker tables already exist (TAKER_RATES, EXCHANGE_FEE_RATES) — repricing a known venue is a table edit.

**Cons:**

- Optimistic fees flatter EV — a strategy that needs VIP3/maker pricing to be EV-positive is fragile and may flip negative on any tier slip.
- Maker rebates, BNB discount, and perp funding have NO config home today; funding (dominant for the delta-neutral harvester) is entirely unmodeled in fee config.
- Diverges from the 10 bps Binance reality the live paper system already simulates.

**Changes required:** Reprice the three fee tables; add new config for maker/rebate/funding (does not exist today); reconcile against the simulator and live PnL fee paths.

#### D — Fully parameterize capital + fee tier as config

*Introduce PRAXIS_NOTIONAL_BASE_USD and a structured PRAXIS_FEE_TIER so capital and fees are operator-set config; route the notional helper + three fee tables + simulator through it.*

**Pros:**

- EV math becomes *recomputable* when the tier changes — no code edit needed, exactly what EN-W4 auto-deprecation needs to stay honest as volume/tier evolves.
- Kills the three-way fee-constant duplication and finishes the future-work item already flagged at docs/DECISIONS.md:152-154.
- Forces the simulator-fee-subtraction fix as part of the same change, making the EV baseline honest.
- Lets the architect sweep EV across tiers (VIP0..VIP3, with/without maker/funding) to see exactly where each strategy flips sign.

**Cons:**

- Largest blast radius now: settings + notional.py + three services + simulator must all route through the new config.
- More than EN-W4 strictly needs to *start* — risks gold-plating before there is even one EV-positive strategy to deprecate.
- Schema-rename adjacency (allocation_pct → notional_capital_dollars, DECISIONS.md:149) tempts scope creep.

**Changes required:** Add PRAXIS_NOTIONAL_BASE_USD + structured fee config to libs/config/settings.py; route libs/core/notional.py:21 and the three fee tables (pnl/main.py:116, execution/executor.py:39, executed_consumer.py:50) through it; make services/backtesting/src/simulator.py subtract round-trip fees.

### Recommendation

Recommend **Option A now, with the simulator fee-subtraction fix attached, and Option D's parameterization deferred to inside EN-W4** — i.e. confirm $10k @ Binance VIP0 as the binding assumption and treat D as the natural follow-on once a real EV consumer exists.

The honest rationale: A is the option that unblocks EN-W4 with the least rework, because the values are *already in the code* — $10k is the single-source constant at `libs/core/notional.py:21` and 10 bps Binance taker (VIP0-equivalent) is already what the live paper system simulates in all three fee tables. Confirming A is, in practice, a documentation flip (assumption #7 FLAGGED→CONFIRMED) plus ratifying reality. VIP0 is also the *conservative* choice: it is the highest realistic Binance fee tier, so any edge that survives EV math here survives at every better tier — exactly the right bias for an autonomous system whose north-star is proving edge before going live. Choosing a lower-fee tier (C) to flatter EV would be self-deception; choosing a different capital base (B) has no supporting evidence in the repo and breaks history coherence.

The one thing A does *not* fix on its own, and the reason I attach a caveat: the backtest simulator computes EV gross-of-fees (`services/backtesting/src/simulator.py:288-299`; documented at `docs/DECISIONS.md:416-419`). Confirming "$10k @ VIP0" is only *useful* to EN-W4 if the EV math then actually subtracts the confirmed VIP0 round-trip fee. So the load-bearing engineering deliverable Decision 5 unblocks is "make the EV/edge baseline net-of-fees at the confirmed tier," not the constant itself. I would bundle that fee-subtraction into the first EN-W4 PR.

Defer full parameterization (D) until that first EN-W4 consumer exists — D is the right *end state* (it kills the three-way fee duplication and lets the architect sweep EV across tiers), but building the config plumbing before there is a single EV-positive strategy to deprecate is gold-plating against the current no-edge reality.

This recommendation flips to D-first only if the architect already intends to run EN-W4 EV across *multiple* tiers (e.g. modeling the realistic glide-path from VIP0 up as volume grows), or if the Yield Harvester's funding-cost modeling — which has no config home today — is in scope for the first EN-W4 PR. In that case, pay the parameterization cost up front rather than hardcoding twice.

### Coupling to the other decisions

This decision is coupled to several others in the set:

- **(1) EN-W3/EN-W4 priority** — this is the tightest coupling. Capital/fees only matters *because* EN-W4 EV math needs it; if the architect re-sequences EN-W4 later or replaces the Yield Harvester thesis, the urgency of confirming this drops. Decision 5 should be resolved *before or with* the EN-W4 go decision, since EV math is the first thing EN-W4 builds.
- **(5/this) ↔ capital scale of the netting decision** — the 2026-06-11 ISOLATED-perp-leg netting decision (`docs/DECISIONS.md:351-394`) explicitly justifies ISOLATED margin as "the right call at the working capital scale ($10k @ VIP0 — FLAGGED assumption #7)" (`docs/DECISIONS.md:381`). Confirming Decision 5 retroactively firms up that already-approved schema decision (migration 025). If capital changes (Option B), revisit whether ISOLATED-vs-CROSS still holds.
- **(2) EN-W2 verdicts** — the EN-W2 kill verdicts (`docs/DECISIONS.md:541-568`) were computed on the *gross-of-fees* simulator baseline. Layering confirmed VIP0 fees only makes those already-negative numbers worse, so it *reinforces* the EN-W2 kill decisions — it cannot rescue them. No conflict, but the two share the same EV substrate.

Ordering implication: confirm Decision 5 (capital/fee tier) **before** EN-W4 starts and **alongside** the simulator fee-subtraction fix; it has no hard dependency on the kill-switch operator, CODEOWNERS, or merge-timing decisions.

### Cost of leaving it undecided

Leaving this undecided directly blocks EN-W4, which is the platform's primary bet (LOCKED #3b, the capstone, per `docs/NEXT-SESSION-PLAN-2026-06-10.md:151`). Concretely:

- **EN-W4 EV / auto-deprecation cannot ship honestly.** The auto-deprecation wiring (`decay_tracker` → `KillSwitch.set_level(NEUTRALIZE)`) needs a net-of-cost EV test to decide *what* to deprecate. With the fee tier unpinned and the simulator running gross-of-fees (`simulator.py:288-299`), any EV verdict is computed on an optimistic baseline — risking either keeping loss-making strategies or killing viable ones.
- **The Yield Harvester EV is materially mis-stated.** Its delta-neutral pairs pay double fees/funding by design (`docs/DECISIONS.md:382-384`); without a confirmed fee tier (and a funding model, which has no config home today), its projected edge is a guess on top of a guess.
- **Assumption #7 stays a standing flag.** It has been carried unconfirmed across at least four session plans (2026-06-10 through -06-13) and the burn-down handoff (`docs/DEBT-BURNDOWN-HANDOFF-2026-06-13.md:161`). It is a one-line architect confirmation that keeps re-surfacing as a blocker because no other role can set the real capital/fee tier.
- **Latent cost: the three duplicated fee tables keep drifting risk.** Every day this stays a hardcoded constant rather than confirmed-and-ideally-parameterized config, the `pnl/main.py` / `executor.py` / `executed_consumer.py` triplet remains a hand-sync hazard the moment anyone touches fees.

### Evidence

*Grounding citations (verified against the tree at `7b8361d`):*

- `libs/core/notional.py:21`
- `libs/core/notional.py:29`
- `libs/core/notional.py:34`
- `libs/config/settings.py:50`
- `libs/config/settings.py:51`
- `libs/config/settings.py:55`
- `libs/config/settings.py:63`
- `services/pnl/src/main.py:116`
- `services/pnl/src/calculator.py:44`
- `services/pnl/src/executed_consumer.py:50`
- `services/execution/src/executor.py:39`
- `services/pnl/src/closer.py:289`
- `services/hot_path/src/state.py:39`
- `services/hot_path/src/state.py:58`
- `services/risk/src/__init__.py:72`
- `services/backtesting/src/simulator.py:288`
- `services/backtesting/src/job_runner.py:207`
- `services/backtesting/src/vectorbt_runner.py:461`
- `docs/DECISIONS.md:78`
- `docs/DECISIONS.md:96`
- `docs/DECISIONS.md:152`
- `docs/DECISIONS.md:159`
- `docs/DECISIONS.md:351`
- `docs/DECISIONS.md:381`
- `docs/DECISIONS.md:416`
- `docs/DECISIONS.md:554`
- `docs/NEXT-SESSION-PLAN-2026-06-10.md:197`
- `docs/EXECUTION-BRIEF-2026-06-11-PHASES-1-2.md:57`

---

## Decision 6 — Merge timing: feat/snappy-honest-edge → main

### Why this decision exists

The integration branch `feat/snappy-honest-edge` (head `7b8361d`) sits **35 commits and 241 files ahead of `main`** (`ddf9db1`), carrying +17,269/−3,040 lines — the entire Risk-Truth slice tail plus FE-W0/W1/W2, EN-W1/W2, and this session's full debt burn-down. The verified facts: `main` is a *clean ancestor* of the branch (zero commits have landed on `main` since the merge-base, so the merge is **fast-forwardable with no conflict surface**); every CI gate is now BLOCKING and green on the branch head (mypy 0/275, ESLint 0/0, 24 integration tests, float/channel guards, skill-drift); but `main` itself is still **red** — it predates the burn-down, so its blocking gates would fail if run today.

This is a decision because the branch model has an explicit, written exit bar that this branch now satisfies, and continuing to defer the merge actively *costs* the project. `docs/DECISIONS.md:290-291` and `CONTRIBUTING.md:27-28` both state the rule: "merge to `main` only when the whole slice is green in CI **and** verified." The slice is green and the live ExitMonitor event plus prod-verified FE-W2 constitute the "verified" half. The countervailing force is that the same decision (`docs/DECISIONS.md:311-315`) **deferred** the CODEOWNERS/branch-protection follow-up "until the slice is otherwise complete" — and "otherwise complete" is now, which is exactly the trigger to wire Decision 4 *before or as part of* this merge. So the timing question is genuinely coupled, not free.

What is fundamentally at stake is the credibility of the "green CI as a gate" claim. Right now the blocking gates are real only *on the branch*. `main` — the branch every future slice forks from and the branch branch-protection will guard — is red. Until this merge happens, the repo is in a contradictory state: the canonical line fails the gates the project says are mandatory. The merge is the single act that flips `main` green and makes the blocking gates real repo-wide. Conversely, merging a 241-file diff in one shot concentrates risk: it is the largest single change to `main` in the project's recent history, and a fast-forward leaves no merge commit to revert as a unit unless we choose the mechanics deliberately.

Finally, every additional EN-W3 commit on the branch widens an already-large diff and lengthens the window in which `main` is the wrong source of truth — the classic long-lived-branch failure mode the integration-branch model was adopted (`docs/DECISIONS.md:303`) specifically to avoid.

### What the system does today

In the absence of a decision, the default is **drift continues**: development stays on `feat/snappy-honest-edge` and `main` remains at `ddf9db1`.

Verified repo state today:
- **Commits ahead:** 35 (`git log --oneline main..feat/snappy-honest-edge | wc -l` → 35).
- **Blast size:** 241 files changed, +17,269 / −3,040.
- **Drift:** *zero* — `git merge-base main feat/snappy-honest-edge` is `ddf9db1`, which equals `main`'s head, and `git merge-base --is-ancestor main feat/snappy-honest-edge` succeeds. The merge is a clean fast-forward; there is no conflict surface.
- **Push state:** `origin/feat/snappy-honest-edge` == local (`7b8361d`), `origin/main` == local `main` (`ddf9db1`). Nothing unpushed.
- **CI:** all gates BLOCKING and green on `7b8361d` (run 27441306368, per the brief). The blocking promotions are documented inline in the workflow: mypy (`.github/workflows/ci.yml:43-62`), ESLint `--max-warnings 0` (`.github/workflows/ci.yml:234-240`), 24 integration tests (`.github/workflows/ci.yml:167-175`), float/channel guards and skill-drift (`.github/workflows/ci.yml:71-87`).
- **`main` is red:** it predates the burn-down (ESLint 300 problems, mypy ~97 errors per the inline CI comments), so the now-blocking gates would fail on `main` as it stands.

The written exit bar is already met on the green half. `docs/DECISIONS.md:290-291` and `CONTRIBUTING.md:27-28` require "green in CI **and** verified"; the branch is green, and FE-W2 was prod-verified plus the live ExitMonitor auto-close exercised the risk path end-to-end. No open PR could be confirmed (the `gh` CLI is unauthenticated in this shell; this is an unverified gap, not evidence that none exists).

The naming has already iterated past the original decision: `docs/DECISIONS.md:288-289` and `CONTRIBUTING.md:23` name `feat/risk-truth-hardening` as "the first" integration branch; the current slice is the *second* (`feat/snappy-honest-edge`), and `3026c33 Merge main (post risk-truth slice merge) into feat/snappy-honest-edge` in the branch log confirms the first slice already landed on `main` and this branch was re-based forward from it. So the model is working as designed — this is simply the second slice reaching its exit bar.

### How each choice propagates through the system

**Merging now flips the repo's source of truth from contradictory to coherent.** The propagation is broad but mechanically clean because of the zero-drift fast-forward:

- **`main` becomes green and the blocking gates become real repo-wide.** Today the gates bite only on the branch; on `main` they would fail. After merge, `main` passes mypy 0/275, ESLint 0/0, 24 integration tests, and the guards — which is the precondition for Decision 4 to enable "required status checks" branch protection on `main` without immediately bricking it.
- **Money-at-risk and contract paths are in the diff** and therefore in the blast radius. The merge touches CODEOWNERS-protected paths: `libs/core/schemas.py` (a binding contract, CODEOWNERS line 21), `libs/core/{agent_registry,correlation,exit_policy,portfolio}.py` (line 16), and `services/pnl/src/*` + `services/risk/src/*` + `services/strategy/src/compiler.py` (lines 12-15). The PnL changes are exactly the code that just auto-closed three legacy positions live (the ExitMonitor / closer / stop_loss_monitor files), so this merge promotes freshly-exercised-but-eventful risk code to `main`.
- **No migrations are in the diff** (`git diff --name-only` shows zero `migrations/` files). This materially lowers merge risk: there is no schema-first ordering hazard, no irreversible DB step, and rollback is purely a git operation.
- **Frontend is the largest surface** (70 files) but is non-financial; `services/` (48) and `tests/` (26) follow.

**Each choice propagates differently:**
- *Squash to one commit:* `main` gains a single revertable node but the 35-commit paper trail (every `feat(...)`/`fix(...)`/`docs:` message, the EN-W2 verdicts, the D-A ruling) collapses into one message and is recoverable only via the branch. Given how paper-trail-rich this history is, that is a real loss.
- *Merge commit (`--no-ff`):* preserves all 35 commits *and* creates one merge node on `main` that reverts the whole slice atomically — the safest unit-of-revert for a 241-file landing.
- *Fast-forward:* possible (drift is zero) but leaves no single revert handle and no record that a "slice" landed; reverting means resetting 35 commits. Not recommended despite being the path of least resistance.

**Deferring (keep developing through EN-W3)** keeps `main` red and the gates theoretical, and grows the diff. The blast radius only increases, and the window in which `main` is the wrong source of truth lengthens.

### Options

#### (a) Merge now via a recorded PR — merge-commit (--no-ff), squash NOT recommended

*Open a PR branch→main for the record, let CI run on the PR, merge with --no-ff to preserve all 35 commits plus one atomic revert handle.*

**Pros:**

- Satisfies the written exit bar today (docs/DECISIONS.md:290-291, CONTRIBUTING.md:27-28): green + verified.
- Flips main green immediately; the blocking gates become real repo-wide, unblocking Decision 4's branch protection.
- --no-ff preserves the paper-trail-rich 35-commit history AND gives one merge node to revert the whole slice atomically — best unit-of-revert for a 241-file landing.
- Zero-drift fast-forward base means no conflicts; CI already green on the exact head (run 27441306368).
- No migrations in the diff → rollback is a pure git operation, low blast radius for the size.
- A recorded PR creates the audit artifact the architect-as-reviewer model wants, even for a solo maintainer.

**Cons:**

- Lands the largest single diff to main in recent history (241 files) at once — review-in-aggregate is impractical; trust rests on the green gates and per-PR review already done into the branch.
- Promotes freshly-exercised-but-eventful PnL/risk code (the ExitMonitor that auto-closed 3 positions) to main.
- With CODEOWNERS still a placeholder (@praxis-architect), the architect-review gate does NOT actually fire on this merge — so the 'recorded PR' is real but the review-enforcement is cosmetic until Decision 4 lands.
- If squash were chosen instead of --no-ff, the 35-commit paper trail collapses to one node — a real loss given the history's value.

**Changes required:** Push is already done (origin == local at 7b8361d). Open PR feat/snappy-honest-edge→main via gh (note: gh is unauthenticated in this shell — use the documented credential-fill token pattern). Merge with --no-ff (a merge commit), not squash. Optionally update CONTRIBUTING.md:47-49 which still calls mypy 'advisory' (now stale vs ci.yml).

#### (b) Merge after Decision 4 (replace CODEOWNERS placeholder + enable branch protection first) so the merge itself exercises the gate

*Wire @praxis-architect's real handle and turn on 'Require review from Code Owners' + required status checks on main, THEN open the PR so the architect-review gate actually fires on this very merge.*

**Pros:**

- The merge becomes the first real exercise of the gate the project designed — architect review on money-at-risk paths (libs/core, services/pnl/risk/strategy are all in this diff) fires for real, not cosmetically.
- Exactly what docs/DECISIONS.md:311-315 intended: the CODEOWNERS/branch-protection follow-up was deferred 'until the slice is otherwise complete' — which is now.
- Ordering is honest: you don't claim a reviewed-merge model while self-merging past a placeholder owner.
- Required status checks on main lock in the green-gate guarantee permanently from this merge forward.

**Cons:**

- Branch protection requiring CodeOwner review + a non-author approver can BLOCK a solo maintainer from merging their own PR (the MEMORY note flags self-merge as permission-gated) — risk of gating your own landing.
- Adds a sequencing dependency: Decision 4 must resolve (real handle, possibly a 2nd GitHub identity or admin-bypass policy) before this merge can proceed, delaying the main-goes-green moment.
- main stays red in the interim, so the very status checks you'd require are failing on main until the merge — you must enable 'required checks' in a way that doesn't brick the branch before the green slice lands.
- More moving parts at once (protection config + large merge) — if protection is misconfigured, the merge stalls.

**Changes required:** Resolve Decision 4 first: replace @praxis-architect in .github/CODEOWNERS:12-28 with a real handle/team; configure branch protection on main (required status checks = the now-blocking CI jobs; Require review from Code Owners). Decide self-merge policy (admin bypass vs second approver). THEN open + merge the PR. Sequence-sensitive: enable required-checks such that the green slice is what first satisfies them.

#### (c) Keep developing on the branch through EN-W3, merge later

*Defer the merge; continue EN-W3 (the negative-OOS-edge follow-up / Phase-4 priority) on the same integration branch and merge the larger slice afterward.*

**Pros:**

- Lands one larger, more complete slice — fewer main-merge events overall.
- Keeps EN-W3 work co-located with the burn-down it depends on.
- No immediate branch-protection / CODEOWNERS work needed right now.

**Cons:**

- Directly violates the model's intent (docs/DECISIONS.md:303): integration branches exist to keep main shippable with LESS long-lived divergence — 35 commits is already long-lived.
- main stays RED and the blocking gates stay theoretical for the whole EN-W3 window — the repo remains in its contradictory state.
- Diff grows beyond 241 files / +17k lines, making the eventual single merge even riskier and less reviewable.
- Drift risk: today drift is zero, but any hotfix to main during EN-W3 would force a real reconciliation merge into the branch (the model's worst case).
- Postpones the moment branch protection can be safely enabled on a green main, leaving Decision 4 blocked too.

**Changes required:** None now — continue committing to feat/snappy-honest-edge. Accept growing diff and a red main until the EN-W3 slice completes; re-run this decision at that point.

### Recommendation

**Recommend (a) merge now via a recorded PR, with a `--no-ff` merge commit (not squash) — and strongly consider folding in Decision 4's CODEOWNERS handle first if and only if the architect can be a real approver, which tips it toward (b).**

The honest core: the branch *already meets the written exit bar* (`docs/DECISIONS.md:290-291`: green + verified), drift is zero so the merge is conflict-free, no migrations are in the diff so rollback is a pure git operation, and every blocking gate is green on the exact head. Holding the merge keeps `main` red and the gates theoretical — the single worst property the project can have while claiming "green CI is the gate." So the strong default is: **merge, soon.** Deferring (option c) is the weakest path; it grows an already-large diff and prolongs the contradiction the integration-branch model was adopted to prevent (`docs/DECISIONS.md:303`).

On mechanics: prefer a **merge commit over squash.** This history is unusually paper-trail-rich — 35 commits carrying the EN-W2 verdicts, the D-A direction-aware-scoring ruling, the mypy 104→0 and ESLint 300→0 burn-downs. Squashing discards that narrative from `main`; `--no-ff` keeps all of it *and* gives one revert handle for the whole slice, which is exactly what you want when landing 241 files at once. Open the PR even as a solo maintainer: it is the audit artifact the architect-as-reviewer relationship depends on, and it lets CI re-run against `main` as the PR base.

**Where the recommendation flips to (b):** if the architect can act as a genuine GitHub approver (real handle, second identity, or an agreed admin-bypass policy), then wiring CODEOWNERS first so this merge is the *first real exercise* of the architect-review gate is the better story — it is precisely what `docs/DECISIONS.md:311-315` deferred to "when the slice is otherwise complete," and the diff touches `libs/core/schemas.py` and `services/{pnl,risk,strategy}` (CODEOWNERS lines 12-21), so the gate would meaningfully fire. The blocker is the solo-maintainer self-merge constraint (the MEMORY note flags self-merge as permission-gated): if enabling "Require review from Code Owners" would lock *you* out of merging your own green slice, do **not** front-load it — merge under (a) now, and enable branch protection on the now-green `main` immediately after, so the *next* slice is the first to be gated. Either way, the CODEOWNERS placeholder (`@praxis-architect`, `.github/CODEOWNERS:4-6`) must be resolved before branch protection is switched on, or GitHub silently fails to request the review.

Assumption stated plainly: I could not verify whether a PR already exists (`gh` unauthenticated here) and I am taking CI run 27441306368's green status from the brief, not from a live API check.

### Coupling to the other decisions

**Tightly coupled to Decision 4 (CODEOWNERS handle + branch protection).** The 2026-06-10 branch-model decision explicitly *deferred* the CODEOWNERS/branch-protection follow-up "until the slice is otherwise complete" (`docs/DECISIONS.md:311-315`) — and this merge is the act that completes the slice. The ordering question is the whole crux: (i) merge first, then enable protection on a green `main` (option a — safe for a solo maintainer, but this merge is not gate-exercised); or (ii) wire CODEOWNERS first so the merge itself fires the architect-review gate (option b — better story, but risks locking a solo maintainer out of their own merge). The placeholder `@praxis-architect` (`.github/CODEOWNERS:4-6,12-28`) MUST be resolved before any "Require review from Code Owners" enforcement, or the review is silently skipped — so Decision 4 cannot be half-done around this merge.

**Coupled to the kill-switch operator gate hardening and EN-W2 verdicts (other decisions in the set):** this merge is what *promotes* that work to `main`. The diff includes `services/risk/src/main.py`, `services/pnl/src/*` (including the ExitMonitor that just auto-closed three positions live), and `libs/core/exit_policy.py` — so any decision about the kill-switch operator gate or the EN-W2 exit-band sweep is downstream of, or made moot by, this merge landing.

**Loosely coupled to EN-W3 priority:** option (c) is literally "defer this merge to keep doing EN-W3 on the branch," so the EN-W3-priority decision and this one are mutually exclusive in timing — you cannot both merge-now and keep-developing-pre-merge.

**Ordering implication:** resolve Decision 4's *self-merge policy* question first (can the architect approve, or is admin-bypass agreed?). That single answer determines whether the correct sequence is (a)-then-protection or protection-then-(b). Everything else about the merge (no-ff, recorded PR, no migrations to sequence) is independent and low-risk.

### Cost of leaving it undecided

Leaving the merge undecided is not neutral — it has concrete, compounding costs:

- **`main` stays red and the blocking gates stay theoretical.** The repo continues to claim "green CI is the mandatory gate" while its canonical branch fails mypy/ESLint/integration. Every future slice forks from a red `main`. This is the single most expensive consequence: the gate's credibility is undermined for as long as it persists.
- **Decision 4 stays blocked.** Branch protection with "required status checks" cannot be safely enabled on `main` until `main` is green — so the CODEOWNERS/branch-protection work (already deferred once, `docs/DECISIONS.md:311-315`) is blocked behind this merge. Two decisions stall on one.
- **The diff grows and review-in-aggregate gets worse.** It is already 241 files / +17k lines — the largest single landing in recent history. Each EN-W3 commit makes the eventual merge bigger and the "trust the gates because per-PR review happened into the branch" argument thinner.
- **Drift risk converts from zero to real.** Today the merge is a clean fast-forward (zero drift). The moment any hotfix lands on `main` during the delay, a reconciliation merge into the branch is forced — the integration-branch model's explicit worst case (`docs/DECISIONS.md:303`).
- **The freshly-exercised-but-eventful PnL/risk code stays off `main`.** The ExitMonitor that just auto-closed three legacy positions (+635% / +63,649% synthetic TPs, −15.2% real SL) is on the branch only; the longer it is unmerged, the longer `main` runs the *older* risk code while the new code accrues more divergence.

In short: degradation here is slow but monotonic — nothing breaks today, but the cost of the merge rises every day it is deferred, and a second decision (branch protection) is held hostage to it.

### Evidence

*Grounding citations (verified against the tree at `7b8361d`):*

- `.github/workflows/ci.yml:43-62 (mypy promoted to BLOCKING, run via poetry for parity)`
- `.github/workflows/ci.yml:234-240 (ESLint BLOCKING, --max-warnings 0, 300→0)`
- `.github/workflows/ci.yml:167-175 (24 integration tests, BLOCKING, 2026-06-13)`
- `.github/workflows/ci.yml:71-87 (float/channel guards + skill-drift guard, stdlib-only blocking)`
- `.github/workflows/ci.yml:4-7 (CI triggers include feat/** for push and PR)`
- `docs/DECISIONS.md:290-291 (exit bar: merge to main only when whole slice green in CI AND verified)`
- `docs/DECISIONS.md:288-289 (first integration branch named feat/risk-truth-hardening — current slice is the second)`
- `docs/DECISIONS.md:303 (rationale: per-slice integration branches keep main shippable with less long-lived divergence)`
- `docs/DECISIONS.md:311-315 (CODEOWNERS placeholder + branch protection DEFERRED until slice otherwise complete)`
- `CONTRIBUTING.md:21-30 (branch model rules: main stays shippable; merge integration branch to main only when green AND verified)`
- `CONTRIBUTING.md:47-49 (STALE: still calls mypy 'advisory' — contradicts ci.yml:43, a doc-drift to flag)`
- `CONTRIBUTING.md:84-85 (CODEOWNERS auto-requests architect review for money-at-risk paths)`
- `.github/CODEOWNERS:4-6 (@praxis-architect is a placeholder — must be replaced before enforcement)`
- `.github/CODEOWNERS:12-21 (money-at-risk + contract paths requiring architect review: execution/pnl/risk/strategy, libs/core, schemas.py, channels.py, migrations)`
- `DECISIONS.md:1-10 (root file is a pointer; docs/DECISIONS.md is canonical)`
- `git: main..feat/snappy-honest-edge = 35 commits; git diff --stat = 241 files changed, +17269/-3040`
- `git: merge-base(main, feat/snappy-honest-edge) = ddf9db1 = main HEAD; main IS ancestor of branch → zero drift, fast-forwardable`
- `git: origin/feat/snappy-honest-edge == local 7b8361d, origin/main == local main == ddf9db1, zero unpushed`
- `git diff --name-only main..feat/snappy-honest-edge: zero migrations/ files; libs/core/schemas.py present; services/{pnl,risk}/* and services/strategy/src/compiler.py present`
- `git log: commit 3026c33 'Merge main (post risk-truth slice merge) into feat/snappy-honest-edge' confirms first slice already landed on main`

---

*Generated for architect sign-off. Recommendations are the handler's analysis; the calls are the architect's. The companion what-happened brief is `docs/EXECUTION-BRIEF-2026-06-13-DEBT-BURNDOWN.md`.*
