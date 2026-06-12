# Decisions log

> Architectural and trade-off decisions that diverge from a default, a plan, or
> a prior decision. Append-only — preserve history.

---

## 2026-05-05 — Clean-baseline reset of meta-learning Redis state

### Context

Five rails fixes landed today that change the *interpretation* of every prior
closed trade in the EWMA learning loop:

1. CRISIS abstention restored (`a08d576`) — trades during CRISIS regimes
   should not have happened.
2. Mainnet-vs-testnet OHLCV volume contamination (already RESOLVED earlier
   2026-05-05) — every volume-derived feature was wrong by ~10×.
3. Notional unit alignment ($10k vs $100k drift) — concentration math
   used the wrong denominator.
4. Sentiment + debate "fake LLM votes" filtered out (`4b58e52`) — the
   `agent:closed:{symbol}` stream had been recording sentiment + debate
   with `score=0.0` on every closed trade.
5. Bytes-vs-string Redis decode bug in analyst tracker (`acb25ae`).

The Redis EWMA aggregates (`agent:tracker:{symbol}:{agent}`,
`agent:weights:{symbol}`) integrate over all that poisoned data. Going
forward we want a clean reading.

### Decision

Ran `scripts/reset_clean_baseline.py --apply` at unix ts `1777985139`. The
script:

- Archived `agent:closed:{symbol}` and `agent:outcomes:{symbol}` streams to
  `agent:archive:1777985139:closed:{symbol}` and
  `agent:archive:1777985139:outcomes:{symbol}` (RENAME, atomic).
- Deleted `agent:tracker:{symbol}:*` for every symbol/agent.
- Deleted `agent:weights:{symbol}` so next recompute writes from defaults.
- Deleted `sentiment:{symbol}:latest` (the cache poisoned by `llm_error`
  fallbacks pre-fix).
- Deleted `agent:sentiment:{symbol}` and `agent:debate:{symbol}` so the
  next cycle writes fresh state.

Pre-reset state: BTC/USDT had 3,689 closed-trade entries (9 wins / 3,680
losses), ETH/USDT had 956. After reset: all four streams empty.

### Trade-off

We lose the EWMA convergence on the prior 4,645 trades. But that
convergence was on contaminated inputs, so the only signal it carried was
"all of this was wrong." Restarting from `AGENT_DEFAULTS`
(`ta: 0.20, sentiment: 0.15, debate: 0.25`) gives every agent a fair shot
at proving itself on post-fix data.

### Not reset

- `closed_trades` and `pnl_snapshots` Postgres tables — historical audit;
  the dashboard's all-time PnL reads from these.
- `agent_weight_history` Postgres table — historical record of what the
  system actually computed; preserves the audit trail.
- The archived Redis streams (`agent:archive:1777985139:*`) — kept for
  post-mortem analysis of the contaminated period.

### Verification

After running `bash run_all.sh --local-frontend`, confirm with the probe:
```
poetry run python scripts/probe_agent_scores.py
```
The next analyst recompute (5-min cycle) should write `AGENT_DEFAULTS` to
`agent:weights:{symbol}` for both symbols. The first post-reset closed
trade adds an entry to a now-empty `agent:closed:{symbol}` stream; EWMA
restarts from MIN_SAMPLES=10.

---

## 2026-05-05 — Notional-per-allocation reverted to $10k across all four call sites

### Context

Four call sites in financial code multiply `allocation_pct` by a hardcoded
notional constant:

| File | Constant | Effect |
|------|----------|--------|
| `services/hot_path/src/main.py:132` | `Decimal("10000")` | Sets `state.notional` per profile load (binding for RiskGate's exposure-at-notional check) |
| `services/hot_path/src/state.py:33` | `Decimal("10000")` | `ProfileState` default — only fires if no profile loaded; dead code in production |
| `services/risk/src/__init__.py:60` | `Decimal("10000")` | RiskService.check_order's `portfolio_value` (concentration check, allocation cap) |
| `services/pnl/src/closer.py:35` | `Decimal("10000")` | Daily realised-PnL counter denominator (CircuitBreaker compares against this) |

Commit `ddb68e5` (2026-05-01) bumped `state.py:33` and `risk/__init__.py:60`
from `$10k → $100k` as a session-bridge to unfreeze decision flow during a
demo session where 7 open positions had saturated the $10k notional.
`main.py:132` and `closer.py:35` were missed by the bump, so the running
system used **$10k for the binding RiskGate and the daily-loss counter**
but **$100k for the validation service's pre-trade concentration check** —
a 10× unit mismatch.

### Decision

Reverted `state.py:33` and `risk/__init__.py:60` to `$10k` to match the
other two call sites. All four constants now agree.

### Trade-off

If a profile's open exposure saturates $10k (the original demo's failure
mode), RiskGate's exposure-at-notional check will again freeze new decision
flow. This is **correct rails behaviour** under the documented contract —
the gate exists to enforce capital discipline. Workarounds for an active
demo session: close positions, lower `allocation_pct`, or land the
long-term fix.

### Long-term fix (LANDED 2026-05-05)

The hardcoded `$10,000` constant has been collapsed into a single helper at
`libs/core/notional.py`:

- `NOTIONAL_PER_ALLOC_UNIT_USD = Decimal("10000")` — the only place the
  constant lives.
- `DEFAULT_ALLOCATION_PCT = Decimal("1.0")`
- `DEFAULT_NOTIONAL_USD = DEFAULT_ALLOCATION_PCT * NOTIONAL_PER_ALLOC_UNIT_USD`
- `profile_notional(profile)` — accepts the dict returned by
  `ProfileRepository.get_profile`, returns the computed Decimal. Strictly
  positive — invalid/missing/zero/negative inputs all return
  `DEFAULT_NOTIONAL_USD` so callers can divide without guards.

While auditing, a **fifth** call site was discovered that the original
DECISIONS entry missed: `services/validation/src/check_6_risk_level.py:48`
used a Python `int` literal `10_000` (not even a `Decimal`). It would have
been the next site to silently drift on any future bump.

All five sites now read from the helper:

| File (was) | Now |
|------------|-----|
| `services/hot_path/src/main.py:132` `alloc_pct * Decimal("10000")` | `profile_notional(prof)` |
| `services/hot_path/src/state.py:33` default `Decimal("10000")` | default `DEFAULT_NOTIONAL_USD` |
| `services/risk/src/__init__.py:60` `Decimal(...) * Decimal("10000")` | `profile_notional(profile)` |
| `services/pnl/src/closer.py:_profile_notional` `alloc * _NOTIONAL_PER_ALLOC_UNIT` | wraps `profile_notional(row)` with caching |
| `services/validation/src/check_6_risk_level.py:48` `profile_allocation * 10_000` | `profile_notional(profile)` |

Tests: `tests/unit/test_notional.py` (16 cases) covers the helper's
contract — string/Decimal/int/float inputs, missing/None/empty profile,
zero/negative/garbage values, the strictly-positive-output property.

### Future work (still open)

- Schema rename `trading_profiles.allocation_pct` → `notional_capital_dollars`
  (storing absolute dollars, not a multiplier). Single helper edit when it
  lands. DB migration + frontend form update needed.
- `notional` becomes profile-scoped from a config setting
  (`PRAXIS_NOTIONAL_BASE_USD`) so operators can change the base without a
  code edit. Would live entirely inside `libs/core/notional.py`.

### Why not preserve the bump (keep $100k everywhere)?

- The bump was explicitly marked session-bridge with revert instructions
- The closer's daily-loss counter and the binding RiskGate were never bumped — 3,689 closed BTC trades have already accrued under effective $10k notional; preserving $10k keeps that history coherent
- Honest paper-trading (the user's stated goal) requires the system's numbers to reflect a single, real portfolio size; $10k is the value the binding gate has always used

---

## 2026-06-10 — Adopt the "Risk-Truth Hardening" slice + the safe-to-go-live bar

### Context

`docs/RISK-TRUTH-HARDENING-DECISION-BRIEF.md` (2026-06-02) audited the
federated-architecture taxonomy against the actual code (16 investigators, each
finding adversarially re-checked with file:line evidence) and proposed an 8-PR
slice that complements the Viability Plan's Phase 3. The brief asked for three
sign-offs. This entry records the first.

### Decision

Adopt the §5 **Risk-Truth Hardening** slice as the complement to the Viability
Plan (slotting into / expanding its Phase 3), with **PR 1–2 pulled earlier**
because phantom-close and the dead-wired reconciler corrupt *paper fidelity now*,
not just live readiness. The PR order stands:

| PR | Title | Closes |
|----|-------|--------|
| 0 | SDLC scaffolding | — |
| 1 | Real exchange close (kill phantom close) | 0.2 (partial), fidelity |
| 2 | Wire `BalanceReconciler` + live drift alarms | 1.6 |
| 3 | Tiered kill-switch verbs + record flatten-authority | 0.1, 1.9 |
| 4 | Aggregate/portfolio risk + stress-correlation concentration | 0.4, 2.12 |
| 5 | Funding-aware, per-strategy net-of-cost accounting | 0.5 |
| 6 | Regime hysteresis | 2.11 |
| 7 | Live-vs-backtest decay tracking | 3.14 |

**"Safe enough to go live" bar (adopted as the exit checklist):**

- [ ] Closes reach the exchange and reconcile (PR 1–2).
- [ ] A tiered halt exists with a *documented* flatten-authority policy (PR 3 — see next entry).
- [ ] Portfolio-level (not just per-profile) exposure + correlation limits (PR 4).
- [ ] Realized PnL is net of fees **and** funding **and** slippage, per strategy (PR 5).
- [ ] At least one exchange-side protective order (reduce-only / stop) as defense-in-depth (extends PR 1).
- [ ] Live-vs-paper PnL delta measured and within tolerance (ties to Viability Plan Phase 1).

### Trade-off

Defers federation split (Part 2 / Tier 2.10), sub-account isolation (1.8), the
capital allocator (3.15), and the microstructure/arb/on-chain signal families
(Part 1 E/F/H/I/J) — all low-severity or premature for single-engine spot.
Documented in brief §8.

### Approved by

Architect (partner), via Stevo, 2026-06-10.

---

## 2026-06-10 — Flatten authority: tiered / graduated, not binary

### Context

Brief Decision 2 — the most consequential architecture call for an *autonomous*
system: should the automated layer ever flatten positions unattended, or only
de-risk and reserve "flatten" for a human? Today the kill switch is **binary and
stop-opening only** — it blocks new orders and never flattens (`hot_path/kill_switch.py`).
The taxonomy doc also notes a "reliability inversion": a process-resident kill
switch is least able to act exactly when it is most needed.

### Decision

Adopt **tiered / graduated authority**. Automate the cheap/reversible verbs;
gate the single irreversible verb (full flatten) behind a human *or* a very high
multi-signal threshold. The escalating verb ladder (each subsumes the cheaper):

| Verb | Action | Authority |
|------|--------|-----------|
| **STOP_OPENING** | Block new entries (today's kill switch) | Fully automated |
| **DE_RISK** | Cancel all resting/working orders; halt averaging-in | Fully automated |
| **NEUTRALIZE** | Reduce-only trims to bring gross exposure under a reduced budget (≤ 50% of normal); close most-correlated / worst-PnL first; never flips direction | Fully automated, bounded |
| **FLATTEN** | Close all positions to zero | **Gated** (see below) |

**Auto-FLATTEN gate** — permitted *without* a human ONLY when **≥ 2 independent
severe triggers** fire and persist through a confirmation dwell. Initial
thresholds (tunable; owned by the architect, changeable via config not code):

- Trigger set (need ≥ 2 concurrent):
  - Portfolio intraday drawdown **≥ 15%** from day-start equity.
  - Exchange reconciliation **drift alarm** (books vs exchange beyond tolerance) — live once PR 2 wires the reconciler.
  - **CRISIS** regime confirmed (already the only hard-stop regime).
- Confirmation **dwell ≥ 30s** — triggers must persist (kills single-tick spikes / false positives).
- Below that bar, FLATTEN requires **explicit human authorization (HITL)**.
- Every automated NEUTRALIZE/FLATTEN emits an alert and writes a full audit row.

**Defense-in-depth against the reliability inversion:** because a
process-resident halt may be unable to act when most needed, the policy is
backed by **pre-placed exchange-side reduce-only / stop orders** (the §5 exit
checklist item, extends PR 1) so tail protection does not depend solely on our
process being alive.

### Trade-off

Pure auto-flatten gives faster 24/7 tail protection but risks false-positive
self-harm and depends on the least-reliable-when-needed path. Human-only flatten
is safe against our own kill switch but a true tail can outrun a human between
check-ins. Tiered authority automates everything reversible and reserves only the
irreversible verb for a high bar — the best fit for "safe **and** autonomous."

### Implementation note

The verb ladder and the auto-flatten gate land in **PR 3**. These thresholds are
the *initial* values; PR 3 surfaces them as config so the architect can tune
without a code change.

### Approved by

Architect (partner), via Stevo, 2026-06-10.

---

## 2026-06-10 — Branch model: integration branch + PR gates, reusable CI

### Context

Brief Decision 3, with the stated goal of a CI/SDLC baseline reusable on the
next project and a clean Claude-Code workflow.

### Decision

Adopt the **integration-branch + PR-gates** model (over permanent `develop` /
GitFlow-lite and over trunk-based + feature flags):

- One long-lived integration branch per slice off `main` — first one is
  **`feat/risk-truth-hardening`**.
- Small PRs squash-merge into the integration branch; merge to `main` only when
  the whole slice is green in CI **and** verified (paper/testnet where relevant).
- Add a portable SDLC set, designed to be copy-pasteable into the next repo:
  `.pre-commit-config.yaml` (mirrors the CI `lint` gates — black/isort/ruff/mypy,
  pinned to `pyproject.toml` versions), `.github/PULL_REQUEST_TEMPLATE.md`,
  `.github/CODEOWNERS` (architect review on money-at-risk paths + binding
  contracts), and `CONTRIBUTING.md` (this model, written down once).
- Consolidate the decision log: this file (`docs/DECISIONS.md`) is canonical;
  the root `DECISIONS.md` becomes a pointer here.

### Trade-off

A permanent `develop` would suit many parallel efforts (incl. the redesign
branch), but per-slice integration branches keep `main` shippable with less
long-lived divergence. Trunk-based was rejected as premature — it leans on a
feature-flag system we don't have yet.

### Follow-ups

- ✅ Done — `.github/workflows/ci.yml` trigger extended to include `feat/**`, so
  PRs into the integration branch run CI during the slice.
- **Deferred to end of slice** (per 2026-06-10 directive): replace the
  `@praxis-architect` placeholder in `.github/CODEOWNERS` with the architect's
  real GitHub handle, and enable branch protection ("Require review from Code
  Owners" + required status checks) on `main` and the integration branch. Held
  until the slice is otherwise complete so we don't gate our own in-progress PRs.

### Approved by

Architect (partner), via Stevo, 2026-06-10.

---

## 2026-06-11 — Cloud region: AWS Tokyo (ap-northeast-1)

### Context

Viability Plan §4 Decision 1 deferred the region choice (AWS Tokyo vs GCP
asia-northeast1). Locked as decision #1 in `NEXT-SESSION-PLAN-2026-06-10.md` §2.

### Decision

**AWS Tokyo (`ap-northeast-1`).** One Linux VM (4–8 vCPU, 16–32 GB) running the
existing `bash run_all.sh` under Docker Compose — same architecture as local,
per Viability Plan §2. Secrets move from `.env` to **AWS Secrets Manager**.
Co-located with the Binance matching engine: WS RTT <10 ms vs ~150–300 ms from
the laptop.

### Trade-off

AWS over GCP per Viability §4: cheaper at scale, stronger secrets/security
primitives; GCP's marginally simpler ops doesn't outweigh that. This VM is the
substrate for EN-W3 (provisioning) and EN-W4 (60-day Yield Harvester soak), and
unblocks Viability Phase 1 (cloud baseline + local↔cloud PnL delta).

### Approved by

Architect (partner) — locked recommendation #1, NEXT-SESSION-PLAN-2026-06-10 §2.

---

## 2026-06-11 — Netting & margin: horizon partitioning, no cross-horizon netting, ISOLATED perp legs

### Context

Decision #5 in `NEXT-SESSION-PLAN-2026-06-10.md` §2, written down NOW because it
is binding input to the Phase-A schema (migration 025 `accounts`,
`position_groups`) — policy before schema (EN-W0 precedes EN-W3). The Yield
Harvester introduces perp legs alongside spot positions with different holding
horizons.

### Decision

- **Partition positions across horizons.** Each strategy horizon (e.g. scalp /
  swing / funding-harvest) owns its positions and its risk budget.
- **Never hard-veto across horizons.** A new signal in one horizon must not be
  vetoed because an opposing position exists in another horizon; risk responds
  through sizing and budget, not veto.
- **Forbid cross-horizon netting.** Opposing positions in different horizons are
  held simultaneously, never collapsed into one net position — preserves
  per-strategy PnL truth (PR5 net-of-cost attribution) and each horizon's exit
  semantics.
- **Perp-leg margin = ISOLATED, never CROSS.** A perp leg's liquidation risk is
  confined to its own margin. Yield Harvester delta-neutral pairs (spot long +
  perp short) are *grouped* via `position_groups` (`leg_group_id`/`leg_index`),
  not netted.

### Trade-off

ISOLATED forgoes cross-margin capital efficiency and needs explicit margin
top-up management (an EN-W3 scheduler job), but caps blast radius per leg — the
right call at the working capital scale (**$10k @ VIP0 — FLAGGED assumption #7,
unconfirmed**). Holding opposing positions across horizons pays double
fees/funding vs netting, but keeps strategy-level measurement honest — the
north-star of this slice.

### Schema implications (binding for migration 025)

`accounts`/`positions` carry `market_type` + `margin_mode`; `position_groups`
groups legs; positions carry a horizon partition key; all money columns
`NUMERIC` — never `DOUBLE PRECISION`.

### Approved by

Architect (partner) — locked recommendation #5, NEXT-SESSION-PLAN-2026-06-10 §2.

## 2026-06-11 — EN-W1 backtest exit semantics: shared exit policy, bar-close-only fills, walk-forward OOS baseline

### Context

Registry row 43 + locked decision #4 (backtest truth-pass, mandatory Phase-6
blocker): the backtester closed only on opposing signals while live closes only
on SL/TP/time. EN-W1 makes the sim honest; the *how* involves judgment calls
recorded here.

### Decision

- **Single source of truth**: exit decision logic lives in
  `libs/core/exit_policy.py`, consumed by BOTH the live `ExitMonitor` and both
  backtest engines. Copying it anywhere else is a defect.
- **Bar-close-only fills, no intrabar SL/TP**: sim exits evaluate the shared
  policy at the bar close only; high/low are NOT used for SL/TP fills because
  the intrabar ordering of SL vs TP inside one OHLC bar is unknowable — any
  intrabar model would fabricate fills. Consequence: sim SL/TP fire up to one
  bar later than a tick-level live fill — conservative, no look-ahead
  (prefix-invariance tested).
- **Basis difference (documented, deliberate)**: live `pct_return` is
  net-post-tax (PnLCalculator); sim `pct_return` is the directional move off
  the slipped entry price, gross of exit costs. The decision *logic* is shared;
  the basis difference is documented in the lib docstring.
- **Opposing-signal closes removed** from both engines; entries only open when
  flat.
- **Walk-forward baseline**: a walk-forward run persists its OOS aggregate
  (trades entered in test segments only) as the parent `backtest_results` row —
  the DecayTracker baseline becomes out-of-sample by construction. Per-window
  detail lives on the Redis status payload. **Convergence checks (PR7) must
  filter `close_reason="end_of_data"`** — each window contributes one synthetic
  boundary close that cannot occur live.
- **Compute budget**: walk-forward bars/param-grid capped at the API edge and
  the worker (max 200 windows / 1,000 engine runs / 600s per job) — a single
  authenticated job must not starve the serial backtest worker.

### Trade-off

Bar-close fills understate intrabar SL hits (a position that breached SL
intrabar but recovered by the close survives in sim). The alternative —
modeling intrabar fills off high/low — fabricates an ordering the data cannot
support, which is worse for a truth-pass. Accepted; tick-level sim is future
work if decay tracking shows material divergence.

### Approved by

Executes locked decision #4 (architect-approved 2026-06-10); implementation
judgment calls by Claude Code, flagged here for architect review.

## 2026-06-11 — Kill-switch operator authorization + FE tier severity mapping

### Context

FE-W1 exposed all four halt verbs in the UI (locked decision #6). The security
review found POST /commands/kill-switch had authentication but no
*authorization*: any authenticated account could FLATTEN all positions
(cross-user destructive) or silently resume a halt someone else set.

### Decision

- **Operator allowlist**: `PRAXIS_KILL_SWITCH_OPERATORS` (comma-separated
  user_ids). NEUTRALIZE / FLATTEN (position-destructive) and clearing a halt
  (NONE, incl. legacy `active=false`) require operator membership → 403
  otherwise. STOP_OPENING / DE_RISK stay open to any authenticated user —
  anyone may pull the brake; only operators may floor or release it.
- **Unconfigured = single-operator mode**: with no allowlist set, all
  authenticated users are operators. Rationale: an un-clearable halt control on
  the current single-user deployment is worse than a tierless one. MUST be
  configured before any multi-user deployment.
- **Operator-only detail**: the kill-switch activity log (actor user_ids +
  free-text reasons) and the /risk/portfolio per-symbol/per-cluster breakdown
  are operator-only when an allowlist is configured (`detail_restricted` flag);
  aggregate exposure stays visible to all.
- **FE severity mapping**: body danger overlay (`data-kill-switch="hard"`) and
  danger pill tone fire at NEUTRALIZE+ — matching the backend CRITICAL-log
  threshold in `KillSwitch.set_level`; STOP_OPENING/DE_RISK are warn-tier. The
  FLATTEN UI gate states the locked auto-FLATTEN policy verbatim and requires
  typed confirmation; manual FLATTEN via UI = explicit human authorization per
  decision #2.

### Trade-off

The allowlist is deployment config, not a real role system — fine at current
scale, revisit with multi-user auth (CODEOWNERS/branch-protection partner input
already covers the org side).

### Approved by

Claude Code (handler), executing decisions #2/#6; security posture flagged for
architect sign-off with this session's brief.

## 2026-06-12 — EN-W2 risk_limits_grid: exit-band sweep contract

### Context

Locked decision #3 (per-profile edge triage) needs exit bands swept per
profile, but `run_sweep`'s `param_grid` only swept strategy-rule condition
values. Threading a second grid dimension involved contract judgment calls.

### Decision

- **Allowed keys are EXACTLY the three exit bands** (`stop_loss_pct`,
  `take_profit_pct`, `max_holding_hours`) — the keys `exit_policy` resolves.
  Unknown keys 422 loudly rather than silently no-op (a swept
  `max_allocation_pct` would never change an engine outcome today).
- **A grid requires `walk_forward`**: the queue serves no plain-sweep path, so
  a top-level `risk_limits_grid` on a single-engine run would be a silent
  no-op — rejected at the API edge (422) and again in the worker
  (defence in depth against direct queue injection).
- **Precedence**: a grid embedded in the `walk_forward` dict wins over the
  top-level `BacktestRequest` field (more specific wins); identical resolution
  at the API edge and worker, pinned by tests on both sides.
- **Budget composes multiplicatively**: combos = rule_combos × risk_combos ≤
  100 (`WALK_FORWARD_MAX_PARAM_COMBOS`); windows × combos ≤ 1,000
  (`MAX_TOTAL_RUNS`). The check now also lives INSIDE `run_sweep`, which
  retroactively bounds the previously uncapped service-local
  `POST /backtest/sweep` (registry row added).
- **IS/OOS threshold identity**: the winning `(params, risk_params)` pair's
  bands are string-merged (Decimal-safe, `DEFAULT_RISK_LIMITS` convention)
  into the window's OOS-eval `risk_limits` — in-sample selection and
  out-of-sample evaluation run identical thresholds by construction.

### Trade-off

Sweeping exit bands per window raises the overfit surface (more dimensions to
fit in-sample). Mitigated by the OOS-only parent row (EN-W1) and the budget
caps; the honest read of any sweep remains the OOS aggregate, never the
in-sample winner.

### Approved by

Claude Code (handler), executing locked decision #3 (first half); contract
judgment calls flagged for architect review with this session's brief.

## 2026-06-12 — EN-W2 edge triage verdicts: MACD killed, no re-band rescue, sim convergence confirmed

### Context

Locked decision #3 (per-profile edge triage), executed with the honest
walk-forward machinery (EN-W1) + the new exit-band sweep (EN-W2). All runs:
1m candles (live evaluation timeframe per `services/strategy/src/hydrator.py`),
2026-04-18 → 2026-06-12 (~57k bars), 14d train / 7d test / 7d step (4 windows),
profiles' real `risk_limits`, coverage 99.85%. Numbers + method:
`docs/EN-W2-EDGE-TRIAGE-2026-06-12.md`; runner: `scripts/en_w2_edge_triage.py`.

### Decision 1 — KILL all three MACD profiles (no rebuild)

Trend Following (MACD), Demo · Pullback Long, Oversold Uptrend: every
symbol×profile run has negative OOS sharpe (−2.7 to −8.2), profit factor
0.14–0.62, negative avg return. Of 24 walk-forward windows, only 3 had even
positive IN-SAMPLE sharpe. There is no edge to rebuild or re-band. The
profiles stay `is_active=false` permanently; closed-trade history retained;
their honest baselines persisted (latest `backtest_results` row per profile).
No further engineering effort goes to MACD signal families.

### Decision 2 — exit-band re-banding does NOT rescue the soak strategy; bands stay

The 18-combo sweep (SL {2,4}% × TP {1,2,3}% × hold {6,12,24}h) over the soak
profile's RSI<35 rules produced OOS sharpe −5.41 — WORSE than the plain
baseline (−4.00) — and the per-window winning bands were unstable (24h-hold
won early windows, 12h+tight-SL won late ones). The time-exit-dominated close
mix is a symptom of a signal with no directional edge, not of wrong bands.
The soak profile's bands stay as-is (the soak measures instrument fidelity,
not edge). Strategy replacement is the EN-W3/EN-W4 work, not band tuning.

### Decision 3 — close-reason convergence CONFIRMED (PR7 cross-check)

Live soak (30 closes): time_exit 93% / stop_loss 7%. Backtest OOS
(101 trades, end_of_data filtered): time_exit 90% / stop_loss 5% /
take_profit 5%. The sim's exit behavior matches live within a few points —
the EN-W1 exit-policy unification is validated end-to-end. Decay tracking now
runs against an honest OOS baseline (`en-w2-soak-baseline`); "no decay" going
forward means live matches the (honestly negative) baseline.

### The headline for the master plan

The platform is now honest, and it honestly reports that ALL current signal
families (RSI mean-reversion soak + 3 MACD variants) have negative
out-of-sample edge on Apr–Jun 2026 data. Phase 4–5 work (EN-W3 Tokyo
substrate, EN-W4 Yield Harvester) is not an enhancement — it is the path to
the first strategy with a defensible edge. Flagged for architect prioritization.

### Approved by

Claude Code (handler), executing locked decision #3. Kill verdicts +
prioritization flag for architect sign-off with this session's brief.

## 2026-06-13 — D-A: direction-aware EWMA agent scoring + meta-learning state reset

### Context

`AgentPerformanceTracker.recompute_weights` (`libs/core/agent_registry.py`)
scored each agent's contribution to a closed trade as `hit = 1.0 if outcome
== "win"` — direction-blind (TECH-DEBT row 50). An agent that voted SELL was
credited for a winning BUY trade; agent weights converged on "was the trade a
win", not "was this agent right". Direction-aware scoring was intended from
the start (the dead `direction` read removed in the 2026-06-10 lint cleanup)
but never implemented.

### Decision — scoring semantics (pre-made ruling D-A, debt burn-down handoff 2026-06-13)

Score each agent on whether ITS OWN call was right:

- `hit = 1.0` iff (agent direction == executed trade direction AND outcome
  == win) OR (agent direction == opposite of executed direction AND outcome
  == loss); otherwise `hit = 0.0` (wrong call, breakeven, unknown outcome).
- If the agent's direction is missing or ABSTAIN, that agent is SKIPPED for
  that trade — no EWMA update, no sample counted.

Executed-direction resolution is defensive, because today's producer
(`services/execution/src/executor.py::_record_agent_scores`) stamps every
agent's `direction` with the EXECUTED side (not the agent's own vote) and
the `agent:closed:{symbol}` entry carried no executed-direction field:

1. Prefer the new explicit `trade_direction` stream field
   (`record_position_close` now accepts and writes it, normalized BUY/SELL).
2. Legacy entries: infer the executed side from the recorded agent
   directions — unanimous non-empty direction IS the executed side (the
   historical stamp guarantees unanimity).
3. Neither resolvable (e.g. mixed directions, no field): the trade is
   unscorable — skipped for every agent.

The contrarian-correct branch becomes reachable for real once producers (a)
pass `trade_direction` at close (`services/pnl/src/closer.py`) and (b) record
each agent's OWN vote instead of stamping the executed side (executor) —
both flagged as follow-ups in the burn-down report, out of lane B6 ownership.

### Decision — EWMA state reset at the Wave-2 relaunch

Per the 2026-05-05 clean-baseline precedent: the interpretation of every
prior sample changed, so the accumulated EWMA state is semantically stale.
The ruling's floor is flushing `agent:tracker:*` (per-agent EWMA accuracy /
sample_count / last_updated; 6 live keys: {BTC/USDT,ETH/USDT} ×
{ta,sentiment,debate}) and `agent:weights:*` (computed weights; 15-min TTL
anyway — hot path falls back to `AGENT_DEFAULTS`). But deleting trackers
ALONE is not a clean baseline: legacy `agent:closed` entries re-score
IDENTICALLY under the new rule (the executor stamped every agent with the
executed side, so direction-match-on-win == plain win), and a deleted
tracker resets `last_updated` to 0 — the next ~5-min analyst recompute
would re-consume the retained last-500 window and rebuild the old
outcome-based EWMA. The precedent's actual mechanism already handles this:
`python scripts/reset_clean_baseline.py --apply` ARCHIVES
`agent:closed:{symbol}` / `agent:outcomes:{symbol}` via atomic RENAME to
`agent:archive:<ts>:…` (history preserved for diagnostics) and DELETES
`agent:tracker:{symbol}:*` + `agent:weights:{symbol}` (plus the
sentiment/debate caches). The orchestrator runs that script at the Wave-2
relaunch.

### Approved by

Claude Code (lane B6), executing pre-made ruling D-A from the 2026-06-13
debt burn-down handoff (user-directed session); semantics pinned by
`tests/unit/test_dynamic_weights.py::TestDirectionAwareScoring`.
