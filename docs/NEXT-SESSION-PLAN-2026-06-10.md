# THE PLAN — Next Ultracode Session

### Snappy-UX + Risk-Truth Surfacing + Honest-Edge Engine (Praxis)

**Date:** 2026-06-10  ·  **Author:** Claude Code (handler)  ·  **For:** partner sign-off before next ultracode session
**Status:** ready to execute — all 7 partner decisions locked to recommended options (see §2)

---

## 1 · Where we are

The **Risk-Truth Hardening slice (PR0–PR7) is COMPLETE and pushed on `feat/risk-truth-hardening`** — in sync with `origin`, 11 commits ahead of `origin/main`. It is **NOT yet merged to `main`**: the merge is the gated end-of-slice step (activate CI gating + branch protection — task #3, EN-W0 — which needs the partner's GitHub handle). Concretely the slice delivers:

- **Phantom-close killed** — real exchange close via reduce-only OMS routing, CAS-guarded `PENDING_CLOSE` lifecycle.
- **BalanceReconciler** live (was dead-wired).
- **Tiered kill-switch** — `STOP_OPENING / DE_RISK / NEUTRALIZE / FLATTEN` in `libs/core/enums.py`; `commands.py` accepts `level`.
- **PR4** portfolio + stress-correlation risk; **PR5** funding-aware net-of-cost accounting; **PR6** regime hysteresis; **PR7** live-vs-backtest decay tracking.
- This **satisfies Viability Plan Phase 3.** Full-stack soak passed (19 services, live Binance data, zero crashes).

The frontend redesign is **already merged to `main`** (commit `6112767`); `redesign/frontend-v2` is a stale divergence to delete. Stack: **Next.js 16.1.6 / React 19.2.3.**

### Verified this session (grounding, not vibes)

1. **Biggest FE latency multiplier is real** — `frontend/lib/api/client.ts:33-43` `getSessionToken()` does `fetch('/api/auth/session')` on **every** `apiRequest`, even though `useAuthStore.jwt` is already in memory (`wsClient` reads it directly).
2. `@tanstack/react-query` v5.90.21 is installed but has **zero usages**.
3. **Zero `loading.tsx`** across 35+ routes; **zero prefetch** in LeftRail/ChromeBar.
4. `/hot/[symbol]/page.tsx` — confirmed staggered fetch + positions **double-fetch**.
5. **Backtest truth gap is real** — `services/backtesting/src/simulator.py:193` closes on opposing-signal **only**; no SL/TP/time-exit parity with live `ExitMonitor` (`services/pnl/src/exit_monitor.py`).
6. **Decay auto-deprecation gap is real** — `services/analyst/src/decay_tracker.py` only `logger.warning` + AMBER alert on `decayed=true`; it **never** calls `KillSwitch.set_level(NEUTRALIZE)`.
7. **FE kill-switch is binary** — `killSwitchStore` is `'off'|'soft'|'hard'`; it does **not** carry the tiered levels the backend already accepts. Safety surface is effectively CLI/Redis-only.
8. **Migrations top out at 024** — perp/funding/`position_groups` (migration 025) do not exist yet. `run_all.sh` already supports `--stop` and `--local-frontend`. Canonical log is `docs/DECISIONS.md` (root `DECISIONS.md` is a pointer stub).

### What this plan is

One coherent plan running **two first-class lanes** — a **Frontend Snappy/Smooth-UX lane** (your new explicit focus) and an **Engine Honest-Edge lane** — sequenced so the Risk-Truth safety surface (decision #6) is elevated above the generic Phase-10 cockpit, and the engine stays honest to the real bottleneck: **edge + measurement-truth, not signal breadth or federation.**

---

## 2 · Locked decisions (settled inputs, not open questions)

All 7 partner decisions are locked to their **recommended** option:

| # | Decision | Locked outcome |
|---|----------|----------------|
| **1** | **Cloud region** | **AWS Tokyo (`ap-northeast-1`)** — co-located with Binance matching engine, <10ms WS RTT. Substrate for EN-W3/W4. Unblocks Viability Phase 1. |
| **2** | **Flatten authority** | **Tiered/graduated** (shipped PR3). Automate `STOP_OPENING/DE_RISK/NEUTRALIZE`; auto-`FLATTEN` **only** behind ≥2 concurrent severe triggers held ≥30s, else human auth. FE must expose all four verbs (currently binary). |
| **3** | **Strategy edge** | **Both, sequenced** — cheap per-profile edge-triage of EXISTING profiles first (kill/rebuild MACD, A/B exit bands to break the 100%-time-exit pathology), AND build toward **Yield Harvester** as the primary bet (funding edge, latency-insensitive). |
| **4** | **Backtest truth-pass** | **Mandatory BLOCKER** before the Phase-6 live-decision gate. Exit-fidelity (same SL/TP/time-exit as live `ExitMonitor`) + walk-forward / look-ahead / survivorship guards. |
| **5** | **Netting/margin** | Write into `docs/DECISIONS.md` NOW, before Phase-A schema: partition positions across horizons, **never hard-veto**, **forbid cross-horizon netting**; perp-leg margin = **ISOLATED**. |
| **6** | **Frontend priority** | **Elevate Risk-Truth UI surfacing** (tiered-halt control, portfolio-risk/correlation panel, net-of-cost + decay dashboards) ABOVE the generic Phase-10 cockpit. |
| **7** | **Capital/fees** | Working assumption **$10k @ Binance VIP0** — **FLAGGED for confirmation** (materially affects Yield Harvester EV). Surface as an explicit unresolved input in all EV/compounding math. Do **not** hardcode as confirmed. |

---

## 3 · Lane A — Frontend Snappy/Smooth-UX

### FE-W0 · Foundation primitives *(do first; everything compounds on these)*

Kill the systemic latency multipliers and add the caching/streaming substrate the rest of the lane depends on. Global wins, touch every page.

- **Token cache (highest-leverage single fix):** rewrite `client.ts` `getSessionToken()` to read `useAuthStore.getState().jwt` synchronously from memory (already populated; `wsClient` does this at `ws/client.ts:25`). Keep the `/api/auth/session` fetch only as a cold-start fallback memoized with a 30s in-memory TTL. Removes one full sequential roundtrip from **every** `apiRequest` — on a 5-call page that's ~5-10s reclaimed.
- **React Query provider:** add a `QueryClientProvider` in `app/layout.tsx` (or a `'use client'` Providers island) with `{ staleTime: 5000, gcTime: 300000, refetchOnWindowFocus: false, retry: 1 }`.
- **API hook layer:** create `frontend/lib/api/hooks.ts` with `useQuery` wrappers keyed by `[resource, ...args]` for hot reads first: `useProfiles`, `usePositions(profileId)`, `useKillSwitch`, `useCandles(symbol,tf)`, `useRisk(profileId)`, `useClosedTrades`. Polling → `refetchInterval`; auto-dedupes concurrent identical calls.
- **WS warm-start:** hoist `wsClient.connect()` out of `AppShell.tsx` useEffect into the auth/JWT-ready boundary so the socket initiates the moment `jwt` is set, survives route transitions, and is warm before first `/hot` paint. Verify no double-connect.
- **Root Suspense + streaming shell:** wrap `{children}` in `<Suspense fallback={<PageLoading/>}>` where `PageLoading` renders the chrome (LeftRail + ChromeBar) with a skeleton body. Render chrome faded/disabled during `status==='loading'` instead of the bare spinner.
- **Link prefetch:** add `prefetch` on the 6 primary LeftRail + ChromeBar links — ~200-300ms per nav click.

**Verify:** Chrome DevTools Network — `/api/auth/session` calls/page: target **1 cold, 0 warm**. Lighthouse (mobile, throttled) on `/hot/[symbol]` and `/backtests` — record TTI/TBT deltas. Performance trace: WS frames arrive **before** first PriceChart paint. Two tabs of `/hot/profiles/[id]` → duplicate GETs collapse to 1.

### FE-W1 · Risk-Truth UI surfacing *(LOCKED #6 — first-class, above generic cockpit)*

Make the safety surface that already exists in the engine operable from the UI. Today it's CLI/Redis-only. **Highest-priority feature work in the FE lane.**

- **Tiered halt control:** extend `killSwitchStore.ts` from binary to the four backend verbs (match `libs/core/enums.py`). Extend `api.commands.killSwitchToggle` to send `{level, reason}` (backend `commands.py` accepts `level`, validates at `:75`). Rebuild `KillSwitchModal.tsx` into a graduated control: `STOP_OPENING/DE_RISK/NEUTRALIZE` single-click; **`FLATTEN` requires an explicit confirm gate stating the locked policy** (decision #2). Optimistic toggle with reconcile-on-poll.
- **Portfolio-risk + correlation panel on `/risk`:** surface PR4 portfolio risk + stress-correlation concentration (concentration grid + correlation heatmap). Replace empty-state pop with `RiskPageSkeleton`. Memoize `ActiveLimitsRow`; move `num()` out of `useMemo`.
- **Net-of-cost dashboard:** surface PR5 per-strategy net-of-cost (gross vs net, fees, funding, slippage attribution) as a gross→net waterfall per profile on `/performance` or a `/risk` sub-tab.
- **Decay dashboard:** surface PR7 live-vs-backtest decay. Read the decay snapshot (`services/analyst` writes `SNAPSHOT_KEY` to Redis; add a thin api_gateway read endpoint if none exists). Render per-profile decay status with AMBER state + `reasons[]`. Human-facing companion to the auto-deprecation wiring (EN-W4).
- **Kill-switch page-visibility guard:** gate `/risk` and `/hot` kill-switch polls on `document.visibilityState`.

**Verify:** trigger each tiered level from UI → confirm via `redis-cli GET` the level matches and `orders.py:67` blocks entries at the right tiers. Confirm `FLATTEN` can't fire without the gate. Set synthetic `decayed=true` → panel renders AMBER + reasons. Profiler on `/risk` poll: <5 component updates per poll after memoization.

### FE-W2 · Snappy data-fetching + render-jank kill *(the 'smooth/snappy' core)*

Eliminate waterfalls, double-fetches, polling pile-ups, hot-path re-render storms. The bulk of the "smooth, snappy across ALL pages" ask.

- **Migrate hot read paths** to the FE-W0 React Query hooks: `/hot/[symbol]`, `/hot/profiles/[id]` + its tabs (move fetches to parent `ProfileCockpit`, share query keys so tabs dedupe), `/analysis`, `/performance`, `/backtests`, `/risk`. Replace bare `setInterval` polls with `refetchInterval` + in-flight dedupe.
- **Parallelize `/hot/[symbol]` mount:** candles + profiles + kill-switch fire in parallel; positions + orders gate on a separate effect keyed `[activeProfileId]` so they fire once when ready (fixes the confirmed double-fetch ~`page.tsx:194-214`).
- **Memoize hot-path rows:** `EventRow` (observatory `page.tsx:358-426`), OrderBook `BookRow` (extract `renderAsks/renderBids` to module-level fns + `useCallback itemContent`), `TapeRow`, `DecisionRow`, `PositionRow`, `MetricCard`, `PnLBadge` → `React.memo` + stable keys + `useCallback`. These are the 10-100Hz repaint sources.
- **Virtualize long tables:** apply the existing Virtuoso pattern (already in observatory) to `DecisionsTab`, `PositionsTab`, `/backtests` history.
- **Throttle portfolio store:** batch `pubsub:pnl_updates` ingestion to ≤2-10Hz (coalescing timer) instead of per-tick `setState`.
- **Sticky-header CLS fix:** bump sticky headers to `z-40+`, reserve header height.
- **agentViewStore dedupe:** 50-entry LRU on `ingestEvent` to drop duplicate telemetry ids.

**Verify:** Performance trace under live telemetry on `/hot/[symbol]` + `/agents/observatory` — sustained 60fps, no long tasks >50ms. Profiler: single telemetry event commits only the affected row. Network: one in-flight request per resource; no undefined-profileId positions call on first paint. Lighthouse CLS = 0 on tables during scroll.

### FE-W3 · Perceived-performance polish *(lower priority; completes the mandate)*

- **`loading.tsx` skeletons** for >500ms routes (`/backtests`, `/backtests/[run_id]`, `/settings/profiles`, `/hot/profiles`, `/risk`, `/performance`, `/analysis`) — mirror final layout to hold CLS=0.
- **Progressive Suspense** on data-heavy pages — per-section boundaries + skeletons so sections stream independently.
- **Optimistic mutations** beyond orders: profile edits, position close (202-pending → "closing" tag + poll reconcile), tiered kill-switch toggle — all with rollback.
- **Dynamic-import recharts:** wrap `GateBlockAnalytics`, `WeightEvolutionChart`, `EquityCurveChart`, analysis `AgentScoreOverlay` in `next/dynamic({ ssr:false })` — ~200KB off `/analysis`, `/performance`, `/backtest` bundles.
- **PriceChart prefetch** on LeftRail hover of `/hot` — shave the ~15s cold-load tail.
- **Persist transient UI state:** zustand `persist` on `analysisStore`/`tradingModeStore`; move `/hot` timeframe + `/backtests` filters into URL searchParams.
- **JSON-editor debounce:** 300ms on `/profiles` `onChange`; validate only on blur/submit.

**Verify:** `next build` route report — initial JS bundle drops on `/analysis`/`/performance`/`/backtest`. Slow-4G video of `/backtests`/`/risk` — skeleton paints immediately, no blank-then-pop. Position-close shows "closing" instantly and reconciles. Timeframe/active-profile survive hard refresh.

---

## 4 · Lane B — Engine Honest-Edge

### EN-W0 · Cleanup + policy lock *(cheap, unblocks everything; runs alongside FE-W0)*

- **Merge the slice to `main`:** `feat/risk-truth-hardening` (PR0–PR7, pushed, 11 commits ahead of `origin/main`) lands via the first gated PR — this is the slice's actual merge-to-main, gated on the CI activation below.
- **Write decision entries to `docs/DECISIONS.md`:** netting/margin policy (#5) and cloud-region (#1). Must exist before migration 025 is designed.
- **Resolve stale branch:** delete `redesign/frontend-v2` (local + remote) — redesign already merged at `6112767`. Diff against main first to confirm nothing un-merged lives only there.
- **Fix stale Viability doc:** reconcile `docs/PLATFORM_VIABILITY_PLAN_2026-05-18.md` (Phase 3 satisfied; region = Tokyo).
- **Activate CI gating (task #3, pending):** turn the `edit-validator`/`security-scan`/`float-guard` hooks into CI gates (pre-commit mirroring CI lint) so truth-pass work can't regress financial-precision or channel contracts. *(Needs partner's GitHub handle for the CODEOWNERS placeholder + branch protection.)*

**Verify:** `git branch -a` confirms `redesign/frontend-v2` gone. `docs/DECISIONS.md` has both new entries. A deliberately-bad PR (a `float(` in `services/execution`) fails the gate.

### EN-W1 · Backtest truth-pass *(LOCKED #4 — mandatory BLOCKER, headline deliverable)*

Make backtest projections honest enough to gate capital.

- **Exit fidelity:** refactor `simulator.py` so the in-position close path mirrors `exit_monitor.py` — stop-loss, take-profit, AND time-exit, same precedence and price basis as live. **Extract the exit-decision logic to a shared lib** so live and sim can't drift. This is what breaks the invisible 100%-time-exit pathology.
- **Look-ahead guard:** audit for bar-close/future data in intrabar decisions; enforce decision-time-only information.
- **Walk-forward:** rolling train/test windows so a single in-sample fit can't masquerade as edge.
- **Survivorship guard:** symbol universe reflects what was tradeable at the time (no delisted-pair bias).
- **All-Decimal:** every new calc in `Decimal` (`backtest_results` was DOUBLE PRECISION historically, resolved in migration 009 — do not regress).

**Verify:** same profile through backtest + paper-soak → close-reason distributions converge (PR7 decay tracker is the cross-check). Unit test: a position that hits SL live hits SL (not opposing-signal) in the sim on identical bars. Out-of-sample Sharpe reported separately. **BLOCKER — no Phase-6 live-decision gate passes until exit-fidelity tests are green.**

### EN-W2 · Per-profile edge triage *(LOCKED #3a — right after truth-pass makes results trustworthy)*

- **MACD kill/rebuild** against the honest backtest + closed-trade attribution.
- **A/B exit bands** to break the all-time-exit pathology (PR2 rule-heatmap / close-reason endpoints are the measurement substrate).
- **Feed results** to the FE decay/net-of-cost dashboards (FE-W1) so triage is visible and auditable.

**Verify:** close-reason taxonomy before/after — time-exit share drops, SL/TP exits appear. Net-of-cost (PR5) — rebuilt profiles net-positive after fees/funding/slippage, not just gross.

### EN-W3 · Substrate + Phase-A primitives + scheduler *(uses LOCKED region #1)*

- **Cloud substrate:** provision AWS Tokyo VM + Secret Manager (laptop ~200ms → <10ms co-located). Keep `run_all.sh` as the single boot path.
- **Phase-A primitives:** add `OrderType/TimeInForce/MarginMode/MarketType` enums to `libs/core/enums.py` (only place enums live); add `order_type/leg_group_id/leg_index` to `place_order` + order events; create `accounts` table as **migration 025** + Universal Transfer. **Schema FIRST** (no dependent code before schema exists).
- **Scheduler framework:** introduce APScheduler for compounding / cointegration / reconciler-cadence / funding-poller jobs, consistent with the startup-ordering contract.
- **Margin policy in code:** implement ISOLATED perp-leg margin per the EN-W0 DECISIONS entry; partition across horizons; forbid cross-horizon netting.

**Verify:** migration 025 applies cleanly, `accounts` uses NUMERIC (never DOUBLE PRECISION). New enums referenced, not string-literal'd. A no-op scheduled job fires on cadence in logs. WS RTT from Tokyo VM <10ms vs laptop baseline.

### EN-W4 · Yield Harvester + auto-deprecation + soak *(LOCKED #3b — the primary bet, capstone)*

- **Perp adapter + funding ingestion:** perp adapter, funding-rate ingestion + `funding_rate` table, `position_groups` table, funding-trigger pipeline node, weekly compounding (EN-W3 scheduler).
- **Auto-deprecation wiring (objective F — confirmed gap):** in `decay_tracker.py`, when `assessment.decayed`, in addition to the existing log + AMBER alert, **call `KillSwitch.set_level(NEUTRALIZE)`** for that profile. Closes the loop between PR7 decay detection and PR3 tiered halt; engine counterpart to the FE decay dashboard. Targets `NEUTRALIZE`, **never `FLATTEN`.**
- **60-day cloud soak** on Tokyo substrate; gate live-capital decisions on EN-W1 truth-pass + soak evidence.
- **Capital/fees flag (#7):** carry $10k VIP0 as an explicit surfaced assumption in all EV/compounding math; do not hardcode as confirmed.

**Verify:** force `decayed=true` → `redis-cli` confirms profile kill-switch becomes `NEUTRALIZE` + FE dashboard reflects it. Funding rows ingest on cadence; net-of-cost attributes funding correctly. 60-day net-of-cost equity curve positive after fees+funding+slippage; close-reason distribution matches backtest.

**DEFER (do NOT build this session):** federation split, sub-account/margin beyond ISOLATED perp leg, capital allocator, signal families E/F/H/I/J.

---

## 5 · Integrated sequence

Two parallel lanes; an ultracode session can fan these out. Ordering puts global FE primitives and engine cleanup first (independent, unblock the most), then the two first-class priorities in parallel, then the snappy-UX bulk + edge triage, then substrate, then the Yield Harvester capstone.

| Phase | Weeks | Frontend lane | Engine lane |
|-------|-------|---------------|-------------|
| **1** | 1 | **FE-W0** token cache · React Query · WS warm-start · root Suspense · prefetch | **EN-W0** DECISIONS entries · delete stale branch · fix viability doc · activate CI |
| **2** | 1–2 | **FE-W1** Risk-Truth UI *(LOCKED #6)* | **EN-W1** backtest truth-pass *(LOCKED #4, BLOCKER)* |
| **3** | 2–3 | **FE-W2** snappy fetch + render-jank kill | **EN-W2** per-profile edge triage |
| **4** | 3–4 | **FE-W3** perceived-perf polish | **EN-W3** Tokyo substrate + Phase-A primitives + scheduler |
| **5** | 4–8+ | — | **EN-W4** Yield Harvester + auto-deprecation + 60-day soak |

**Dependencies:** FE-W0 precedes W1/W2/W3 (everything builds on token cache + React Query). EN-W0 precedes W3 (policy before schema). EN-W1 precedes W2 and gates W4. EN-W3 precedes W4. Cross-lane: EN-W2 wants FE-W1's dashboards; EN-W4's auto-deprecation pairs with FE-W1's decay dashboard. Otherwise the lanes are independent.

---

## 6 · Success criteria

- **FE token-fetch eliminated:** Network shows 0 `/api/auth/session` on warm nav (was 1/apiRequest); measurable TTI reduction on `/hot/[symbol]` + `/backtests`.
- **React Query deduping:** two components reading the same resource → ONE request.
- **Risk-Truth safety surface operable from UI (#6):** all four tiered halt verbs triggerable; FLATTEN behind a confirm gate stating the locked policy; correlation/net-of-cost/decay dashboards render real PR4/PR5/PR7 data — verified against redis-cli/engine state.
- **Backtest truth-pass green (#4):** a position that hits SL/TP/time-exit live hits the same exit in the sim on identical bars; out-of-sample metrics reported separately; close-reason distribution converges between backtest and paper-soak. Gates the live-decision gate.
- **Render-jank killed:** sustained 60fps, no >50ms long tasks during live telemetry on `/hot/[symbol]` + `/agents/observatory`; a single telemetry event commits only the affected row.
- **Skeletons + CLS:** every >500ms route has `loading.tsx`; Lighthouse CLS ≈ 0 on data-heavy pages and during scroll; no blank-then-pop on Slow-4G.
- **Edge triage executed (#3a):** time-exit share drops, SL/TP exits appear; rebuilt/killed profiles net-positive after fees/funding/slippage.
- **Auto-deprecation loop closed (objective F):** a forced `decayed=true` sets the profile kill-switch to `NEUTRALIZE` (redis-cli) and surfaces in the FE decay dashboard.
- **Policy + substrate landed:** `docs/DECISIONS.md` has netting/margin (#5) + region (#1); migration 025 (`accounts`) applies with NUMERIC; Tokyo VM WS RTT <10ms; APScheduler fires on cadence.
- **CI gating active (task #3):** a deliberately-bad PR (`float(` in `services/execution`) is rejected by the gate.

---

## 7 · Risks & open items

- **CAPITAL/FEES UNCONFIRMED (#7):** $10k VIP0 is a working assumption that materially changes Yield Harvester EV. Surface as an explicit flagged input in all EV/compounding math; **get partner confirmation before EN-W4 capital decisions.** Do NOT hardcode as confirmed.
- **WS/long-fetch leak root cause still open** (memory: `/hot` browser fetches 25-35s while curl returns ~220ms). FE-W0's token cache + React Query + WS warm-start will likely mask or fix it — but the next session must **MEASURE** (Performance + Network) to confirm the root cause is gone, not just hidden. If page-side fetches stay slow after FE-W0, escalate a focused WS/long-fetch leak investigation before declaring FE-W2 done.
- **Backtest/live exit drift:** the truth-pass stays honest only if sim and live `ExitMonitor` share exit-decision code. Extract a shared lib — don't copy-paste the precedence logic.
- **FLATTEN authority hazard:** FE must not make auto-FLATTEN one-click. Decision #2 requires ≥2 concurrent severe triggers held ≥30s OR human auth — the confirm gate must encode this; auto-deprecation (EN-W4) targets `NEUTRALIZE`, never `FLATTEN`.
- **Optimistic-update correctness:** optimistic kill-switch/position-close toggles must reconcile against the authoritative poll; a mis-reconcile on a SAFETY control is worse than a spinner. Test the rollback path explicitly.
- **Phase boundary:** Yield Harvester / perps must stay a funding-edge mechanical strategy — no Phase-2 ML / multi-agent patterns. Defer federation, capital allocator, sub-account/margin beyond ISOLATED perp leg, and signal families E/F/H/I/J.
- **Throttling portfolio store** to 2-10Hz must not hide a real PnL/risk move on the safety surface — verify kill-switch/risk reads stay responsive while cosmetic PnL badges coalesce.
- **Schema-first discipline:** migration 025 (`accounts`) + `funding_rate`/`position_groups` must exist and be verified BEFORE dependent Yield Harvester code. Missing schema = stop and report.
- **`redesign/frontend-v2` deletion:** confirm nothing un-merged lives only on that branch (diff against main) before deleting; reported merged at `6112767` but verify.

---

*Plan synthesized via a 6-agent ultracode workflow (5 frontend-UX auditors + 1 plan synthesizer); FE findings grounded in the live codebase (the `getSessionToken` root cause at `frontend/lib/api/client.ts:33-43` and the 8 verified facts in §1). Ready for the next ultracode session on partner sign-off.*
