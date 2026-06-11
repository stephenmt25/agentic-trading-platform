# Platform Viability Plan — Cloud Move + Strategy Readiness

> **Date:** 2026-05-18
> **Scope:** Directional correction after partner review. Three questions: (1) is the laptop a fit substrate for honest paper trading; (2) what cloud setup is needed and at what cost; (3) what plan first fixes existing tech debt and then enables Yield Harvester + Mean Reverter strategies. HFT / Latency Exploiter is explicitly deferred.
> **Companion docs:** `STRATEGY_FOLLOWUP_DISCUSSION.md`, `STRATEGY_GAP_ANALYSIS.md`, `TECH-DEBT-REGISTRY.md`, `DOCUMENTATION-GAPS.md`.

> **Status update (2026-06-11).** Two items below are superseded by later locked
> decisions (see `DECISIONS.md` entries of 2026-06-11 and
> `NEXT-SESSION-PLAN-2026-06-10.md` §2):
>
> - **§4 Decision 1 (cloud region) is RESOLVED — AWS Tokyo (`ap-northeast-1`).**
> - **§3 Phase 3 (risk + ops maturity) is SATISFIED** by the Risk-Truth
>   Hardening slice (`feat/risk-truth-hardening`, PR0–PR7): portfolio-level risk
>   + stress-correlation concentration (PR4), tiered kill-switch verbs with the
>   defense-in-depth executor check (PR3), BalanceReconciler live and real
>   exchange-side close (PR0–PR2), net-of-cost accounting (PR5). The one Phase-3
>   item not yet built — the scheduled-jobs framework (APScheduler) — moves to
>   the next slice (EN-W3 in the next-session plan).

---

## 1 · Is the laptop-only setup unable to mirror live trading?

**Mostly yes, with important nuance.** The follow-up doc's framing was *"for current Praxis, cloud adds reliability but no edge"* — correct for medium-frequency signal generation, but the question here is different: **can paper trading on a laptop produce measurements you can trust to predict live behavior?** For multi-day-hold strategies like Yield Harvester and Mean Reverter, the laptop is a poor measurement instrument for four specific reasons:

1. **Network latency from a home connection.** ISP → Binance Spot (Tokyo) RTT is ~150–300 ms. An AWS Tokyo VM is 1–5 ms. For entry signals this rarely matters at minute-bar cadence; for **stop-loss firing and drawdown response** it's the difference between hitting your stop and skidding through it. Paper PnL on the laptop will systematically look *better* than live PnL would, because adverse fills are softened by stale prices.
2. **Uptime — the killer for hold-strategies.** Yield Harvester holds across funding cycles (8h each, position life measured in days/weeks). Mean Reverter holds until z-revert (hours to days). A lid-close, Windows update, or ISP blip means the system isn't there for the exit signal — funding accrues silently, z-score drifts past your exit band. The strategies you're targeting are *specifically* hold-strategies, which is the worst possible class for laptop hosting.
3. **Data-record integrity.** Tech debt row 15 (testnet volume contamination) shows how easy it is to silently poison the historical record from a partial local run. Backtests against contaminated history give false signals. A 24/7 cloud puller hitting mainnet keeps the DB clean.
4. **What does *not* change.** Decimal precision, exchange API contracts, fill behavior, retail-size slippage — these are identical local vs. cloud. Backtests over already-clean historical data are the same either way. So we're not throwing the laptop away; we're moving the *measurement substrate* to where the answer is honest.

**Net:** the platform's correctness is fine on the laptop. The platform's *fidelity as a measurement instrument* for multi-day-hold paper trading is not.

---

## 2 · What needs to be cloud-hosted, and what it costs

Phase 2 Readiness items P-1 (k8s manifests) and P-2 (Terraform modules) imagine the eventual production shape. **Don't start there** — it's overkill until we have a strategy that's earning. Start with a single VM that runs the existing `bash run_all.sh` near the exchange.

**Compute target:** one Linux VM, 4–8 vCPU, 16–32 GB RAM, in **AWS Tokyo (ap-northeast-1)** or **GCP asia-northeast1**. Both regions co-locate well with Binance Spot. Cuts WS RTT from ~200 ms → <10 ms.

**Service layout:** all 19 services + Redis + Postgres (with TimescaleDB extension) in Docker Compose on that one box, same as `deploy/docker-compose.yml` is set up for today. Frontend on the same box, fronted by Caddy/nginx for TLS. No public ingress beyond the frontend + SSH. This is exactly the architecture we're already running locally — just on a machine that doesn't sleep.

**Secrets:** exchange API keys move out of `.env` into **AWS Secrets Manager** or **GCP Secret Manager** (~$0.40/secret/month). Partial P-5; doesn't automate rotation yet, but gets keys off disk. G-7 (rotation procedure) gets documented but stays manual until we go live.

**Backups:** daily VM snapshot + nightly `pg_dump` to S3/GCS. ~$5/mo.

**Observability:** start with the free tier of Grafana Cloud or Better Stack. Don't build a stack until something breaks loudly enough that the free tier can't show it.

**Cost (realistic monthly):**

| Item | On-demand | Reserved 1y |
|---|---|---|
| Compute (e2-standard-4 / t3.xlarge) | $120–180 | $60–90 |
| Storage (~100 GB SSD + snapshots) | $15 | $15 |
| Secret manager | $5 | $5 |
| Egress (low; WS is mostly inbound) | $5–15 | $5–15 |
| Observability (free tier) | $0 | $0 |
| **Total** | **$145–215/mo** | **$85–125/mo** |

When we eventually move to managed Postgres (Aiven Timescale or Timescale Cloud) and managed Redis: add ~$100–200/mo. That's the post-validation upgrade, not the starting point.

The follow-up doc's *"$50–200/month = 6–24% annual drag on $10k"* math still applies — but the comparison is no longer cloud-vs-local for live-trading EV; it's **cloud-vs-broken-data for measurement honesty**. Different problem.

---

## 3 · The plan — fix existing issues first, then add the new capability

Anchored on `STRATEGY_GAP_ANALYSIS.md` Section 6 (Phase A → B → C → D), with two pre-phases (P0, P1) per the directive to fix what's broken first. HFT / Latency Exploiter stays deferred.

### Phase 0 — Make the laptop measurement honest before we move it (~1 week)

Goal: confirm our cloud baseline isn't measuring against a broken local baseline. Open tech debt that actually distorts paper-trading numbers:

- **TECH DEBT row 18 — backtester does not honor `preferred_regimes`.** Critical for any regime-gated strategy (both Yield Harvester and Mean Reverter will be gated). MEDIUM / M. Fix first or every backtest of these strategies overstates trade frequency.
- **TECH DEBT row 27 — orderbook WS dropout.** Doesn't block low-freq strategies but means we can't *see* what's happening on `/hot` during paper trading. MEDIUM / M.
- **TECH DEBT row 31 — WS auth: expired JWTs accepted for ~50 min.** Hygiene fix before any cloud exposure. MEDIUM / S, est. ~5 LOC.
- **TECH DEBT row 32 — OrderBook "stale Xs" badge UI lies.** LOW / S; do while we're in the area.
- **DOC GAP G-10 — `strategy_rules` JSON schema is undocumented.** Required for confidently editing strategy nodes via the canvas during Phases 4–5.

**Deferred (don't do opportunistically):** rows 12, 16, 36, 37, 38, 39, 40 — backlog items, none block measurement.

**Exit criterion:** run a 14-day paper-trading sweep on current Praxis with an **autonomous hold-style profile** — slow entry cadence, exit via stop-loss + opposing-signal, typical hold measured in *hours, not seconds*. (A scalping profile would close before any laptop-downtime event and so wouldn't exercise the substrate at all.) Confirm the system produces a coherent PnL distribution, **and keep a logged record of every laptop downtime event** (sleep / restart / ISP blip) — uptime is the property under test, so downtime is soak *data*, not automatically a soak failure. Set the laptop to never sleep for the duration. If the PnL distribution is incoherent, fix before moving.

> **Note (2026-05-19) — see the §4 correction.** This criterion originally read "a hold-style profile (manual trigger, hour-scale hold, manual exit)." Praxis has no manual profile mode; the wording above is the reconciled version.

### Phase 1 — Move to cloud and re-establish the baseline (~1–2 weeks)

- Provision the single VM described in §2. Docker Compose, not k8s.
- Migrate `.env` secrets to Secret Manager. Address P-5 (basic version) and G-7 (write the manual rotation runbook).
- Address G-1, G-3, G-5, G-6 narrowly: write a single 1-pager per topic *for this single-VM deployment*. Don't try to write SRE-grade documentation for infrastructure we don't have yet.
- Re-run the Phase 0 paper-trading sweep on the cloud box for 14 days.
- **Document the local-vs-cloud PnL delta.** This becomes the calibration constant we apply to every future paper-trading number.

**Exit criterion:** cloud runs `bash run_all.sh` cleanly for 14 days without operator intervention; we have a measured delta between local and cloud paper PnL.

### Phase 2 — Strategy Gap Analysis Phase A: schema + primitives (~2–3 weeks)

Straight from `STRATEGY_GAP_ANALYSIS.md` Section 6 Phase A. These unblock ≥80% of downstream work and don't break existing behavior because defaults stay unchanged:

- Add `OrderType`, `TimeInForce`, `MarginMode`, `MarketType` to `libs/core/enums.py`.
- Extend `ExchangeAdapter.place_order` signature and `OrderApprovedEvent` / `OrderExecutedEvent` schemas with `order_type`, `time_in_force`, `leg_group_id`, `leg_index`.
- Wire through `OrderExecutor` and the Binance adapter (default behavior unchanged for existing profiles).
- Add `accounts` table; migrate `exchange_keys` to reference an account row; add `market_type` to accounts.
- Implement `transfer_between_accounts` on the Binance adapter (Universal Transfer).

### Phase 3 — Strategy Gap Analysis Phase B: risk + ops maturity (~1–2 weeks)

> **SATISFIED 2026-06 by the Risk-Truth Hardening slice** (see status update at
> top) — except the scheduled-jobs framework, which moves to the next slice.

`STRATEGY_GAP_ANALYSIS.md` Section 6 Phase B. Get the safety perimeter in place before any new strategy is live-eligible:

- Portfolio Risk aggregator that consumes `pubsub:pnl_updates`, sums drawdown across profiles, calls `KillSwitch.activate` on threshold breach.
- Defense-in-depth kill-switch check inside `OrderExecutor.run()` (closes the gap `CLAUDE.md` §5B already calls out).
- Periodic balance-reconciler comparing exchange balances vs. internal ledger, emitting `SYSTEM_ALERT` on drift.
- Scheduled-jobs service (or APScheduler embedded in an existing service) hosting: weekly compounding sweep, cointegration recompute, balance reconciliation, funding-rate poller.

### Phase 4 — Yield Harvester (~3–5 weeks)

Gap analysis Phase C. Highest-EV strategy at $10k; best fit for current architecture; smallest delta:

- Binance USDⓈ-M perp adapter (separate class; new `MarketType.PERP_USDM`).
- Funding-rate ingestion + `funding_payments` table + `funding_payments_repository`.
- `position_groups` table; `pair_id` column on `positions`.
- `yield_harvester` strategy-class node (entry/exit on funding-rate trigger) OR dedicated `yield_harvester` service.
- Wire weekly compounding sweep into the scheduled-jobs service.
- **Entry/exit policy on funding rate** (gap analysis §4.1) — not in the original strategy doc, but required so the strategy doesn't bleed in inverted-funding regimes.

**Paper-trade for 60 days in cloud before discussing live.**

### Phase 5 — Mean Reverter (~3–4 weeks)

Gap analysis Phase D:

- Cointegration test pipeline (statsmodels `coint`) + `pair_definitions` table.
- Pair-ratio z-score indicator + multi-symbol joined-evaluation primitive (extends `HotPathProcessor` to consume joined tick streams).
- `pairs_eval` strategy-class node.
- Pair-aware exit monitor (current `services/pnl/src/exit_monitor.py` exits per-position; needs pair semantics).

**Paper-trade for 60 days in cloud before discussing live.**

### Phase 6 — Live decision gate (no engineering)

After Phase 4 and Phase 5 have each accumulated 60 days of cloud paper-trading data:

- Compare measured PnL distribution to follow-up doc projections (Yield Harvester +3–8%, Mean Reverter +5–15% in a good regime).
- For each strategy: if measured EV ≥ cost floor (fees + cloud + capital opportunity cost), proceed to live with a small capital tranche (e.g., $1k of the $5k sleeve). If below floor, descope and document why.
- HFT / Latency Exploiter remains explicitly deferred per follow-up doc Q1 and §3.3 of gap analysis (no Rust code exists; negative-EV at retail fee tier; reassess only after VIP-tier qualification).

---

## 4 · Two decisions to confirm before Phase 0 starts

1. **Cloud region.** AWS Tokyo and GCP asia-northeast1 are both reasonable. AWS is cheaper at scale and has more secrets / security primitives; GCP has marginally simpler ops. Either works. → **RESOLVED 2026-06-10: AWS Tokyo (`ap-northeast-1`)** — locked decision #1, recorded in `DECISIONS.md` (2026-06-11).
2. **Phase 0 scope.** Five fixes listed above distort measurement. If you want a hard 1-week ceiling, drop rows 27, 31, 32 and ship with just row 18 (regime gating) + G-10 (schema docs). Everything else can move with us to cloud and get fixed there.

> **Correction (2026-05-19, post-Phase-0 implementation).** The §3 Phase 0 exit criterion originally specified a *"hold-style profile (manual trigger, hour-scale hold, manual exit)."* That describes a workflow Praxis does not have — every profile is **autonomous signal-driven**: `hot_path` evaluates `strategy_rules` per tick and fires; exits come from `StopLossMonitor` / opposing-signal, not a human. There is no manual-trigger or manual-exit profile mode. The §3 criterion has been reworded to an **autonomous hold-style profile** — the load-bearing requirement is only that the profile *holds* (hour-scale, not scalping), so the 14-day soak genuinely exercises the laptop-uptime hypothesis from §1. Choosing or building that profile (an existing slow profile such as `Trend Following (MACD)`, or one deliberately-slow regime-gated profile as a proxy for the eventual Yield Harvester / Mean Reverter holds) is a setup step before the soak clock starts.
>
> **Soak profile — built 2026-05-19.** The autonomous hold-style profile now exists: **`Phase 0 Soak — Hold Baseline`** (`a05adba2-5128-4bef-bb92-a3cb429b55e1`). Entry `rsi < 35` → BUY (`base_confidence` 0.6); exits SL 4% / TP 3% / `max_holding_hours` 6h — with SL/TP deliberately wide, the 6h time-exit dominates, so holds are reliably hour-scale by construction. `exchange_key_ref=paper`. The other five profiles were deactivated so the soak measures this profile alone. Rationale: live exits are SL/TP/time only (from `risk_limits`, via `services/pnl/src/exit_monitor.py`) — there is no opposing-signal exit — so hold duration is fully controlled by `risk_limits` and a purpose-built profile is the honest, documented measurement instrument.
>
> **Phase 0 status:** the five code/doc items are **done and committed** (`fix(phase-0)` — tech-debt rows 18/27/31/32 + G-10; plus `fix(daily_report)` — a cold-start daemon-resilience fix found during the boot smoke-test). Decision 1 (cloud region) was **deferred**; Decision 2 (scope) resolved as **all five items**. The 14-day soak is **not yet started** — remaining is the operational kickoff: set the laptop to never-sleep, boot `run_all.sh`, and begin the downtime log.

---

## 5 · Total timeline estimate

| Phase | Duration | Exit state |
|---|---|---|
| 0 — Honest local baseline | 1 week | Trustworthy laptop paper-trade numbers |
| 1 — Cloud move + baseline delta | 1–2 weeks | 24/7 cloud runtime + measured local↔cloud delta |
| 2 — Schema + primitives (Gap A) | 2–3 weeks | Multi-leg / multi-market primitives in place |
| 3 — Risk + ops (Gap B) | 1–2 weeks | Safety perimeter live |
| 4 — Yield Harvester (Gap C) | 3–5 weeks | Profile 1 paper-trading in cloud |
| 5 — Mean Reverter (Gap D) | 3–4 weeks | Profile 2 paper-trading in cloud |
| 6 — Live decision gate | (60-day soak) | Live capital tranches OR descope w/ reasoning |
| **Total engineering** | **11–17 weeks** | + 60-day paper soak before live |

HFT / Latency Exploiter is **not** in this timeline.
