# Praxis Trading Platform — UI Walkthrough (Redesign)
**Partner Brief — May 2026**

This document walks through the redesigned Praxis dashboard one surface at a time. The frontend was rebuilt over Phases 1–9 of the redesign program; the merged design portfolio (`docs/design/`) governs visual and IA decisions. Every behavior described below is grounded in source code — file paths and line ranges are listed under each section.

The redesign is organized around **five canonical surfaces** and a shared chrome:

| # | Surface | URL | Mode | Time budget |
|---|---|---|---|---|
| 1 | Hot Trading | `/hot/{symbol}` | HOT — cockpit, maximum density | 70%+ |
| 2 | Agent Observatory | `/agents/observatory` | COOL → HOT when watching live | 15–25% |
| 3 | Risk Control | `/risk` | HOT — kill switch must work when other surfaces are degraded | 2–10% |
| 4 | Backtesting | `/backtests` (+ `/backtests/{id}`, `/backtests/compare`) | COOL | 5–15% |
| 5 | Settings | `/settings/{section}` | CALM — office space, low density | 1–5% |

**Mode contract.** Every surface declares `data-mode="hot|cool|calm"` on its root. The three modes share a token vocabulary but differ in density, visual budget, and tone. HOT mode is the cockpit; COOL mode is the analyst's workbench; CALM mode is the office where you configure intent rather than react to markets.

**Scope tags used throughout.** Where the legacy dashboard tagged panels with `PROFILE`, `SYSTEM`, `SYMBOL` scope chips, the redesign embeds scope in IA: each surface owns its own scope, so the tags are implicit. The exceptions are noted inline.

---

## Contents

**Chrome**
- Sidebar, top bar, connection pill, kill-switch shortcut

**Surface 1 — Hot Trading**
- 1.1 Default state (chart + book + tape + order entry)
- 1.2 Paper-order submission flow
- 1.3 Connection states (live / degraded / stale)
- 1.4 Kill-switch armed overlay

**Surface 2 — Agent Observatory**
- 2.1 Three-column default (roster + event stream + focus panel)
- 2.2 Agent trace expanded in focus panel
- 2.3 Debate panel (live debate cycle)
- 2.4 HITL approval queue

**Surface 3 — Risk Control**
- 3.1 Default state (kill switch + exposure + active limits)
- 3.2 Kill-switch modal (`Cmd+Shift+K`)
- 3.3 Per-profile risk monitor cards

**Surface 4 — Backtesting**
- 4.1 Run list (`/backtests`)
- 4.2 Run detail (`/backtests/{id}`)
- 4.3 Compare view (`/backtests/compare`)
- 4.4 New-backtest flow

**Surface 5 — Settings**
- 5.1 Settings nav (the CALM-mode shell)
- 5.2 Profiles
- 5.3 Exchange keys
- 5.4 Risk defaults *(newly wired)*
- 5.5 Notifications *(partial — wired booleans + Pending events)*
- 5.6 Tax *(Pending — backend in design)*
- 5.7 Account
- 5.8 Sessions *(newly wired)*
- 5.9 Audit log *(kill-switch wired; other sources pending)*

**Appendices**
- A. What's shipping next (transparency on Pending items)
- B. Architecture-at-a-glance (19 services, the redesign's contract)

---

## Chrome

**Screenshot file:** `chrome_sidebar_topbar.png`

The chrome is the only UI that persists across every surface. It is split into:

- **Left sidebar** — collapsible (56px ↔ 220px). Logo + surface nav (Hot, Observatory, Backtests, Risk, Pipeline Canvas, Settings). Active surface is highlighted with `bg-bg-panel`. The sidebar is one of the few zones that uses the same look across HOT / COOL / CALM modes — the user always knows where they are.
- **Top bar** — three slots, left-to-right: route crumb + active symbol/profile breadcrumb, **connection pill** (live/degraded/stale; polls `/ready`), command-palette trigger (`Cmd+K`). Far right: kill-switch shortcut affordance (`Cmd+Shift+K`), avatar, sign-out.

**What the screenshot is showing:**
* Praxis branding (left-rail logo) and global nav rendered by the root layout. The default surface after sign-in is `/hot/BTC-USDT` — root redirect.
* The connection pill on the top bar is `/ready`-aware (ADR-017): green = engine fully healthy, amber = degraded but tradable, red 503 = at least one critical dependency down. Poll cadence is 5 s.
* Kill-switch trigger key (`Cmd+Shift+K`) is universal — the modal opens from any surface. The shortcut is the canonical kill path; the on-screen button on `/risk` is the fallback for users without a keyboard.

**Source of truth (code):**
* `frontend/app/page.tsx:1-5` // redirect('/hot/BTC-USDT')
* `frontend/app/layout.tsx:1-60` // global providers (Auth, AppShell, ModeProvider, ErrorBoundary)
* `frontend/components/providers/AppShell.tsx` // sidebar + top bar composition
* `frontend/components/shell/ConnectionPill.tsx` // /ready-aware pill (ADR-017)
* `frontend/components/shell/KillSwitchModal.tsx` // Cmd+Shift+K modal

---

# Surface 1 — Hot Trading (`/hot/{symbol}`)

The cockpit. 70%+ of the user's session lives here. Maximum density, HOT mode tokens, three-column layout that compresses at narrow viewports per ADR-006 (the tablet/mobile "monitor-only" stance — at ≤1024 px, order entry is intentionally hidden because we don't want fat-finger fills on a phone).

## 1.1 Default state — chart + book + tape + order entry

**Screenshot file:** `hot_trading_default.png`
**Route:** `/hot/BTC-USDT`

This is the surface that opens on sign-in. The grid is left-rail + center + right-panel:

- **Center column** — top: TradingView-class candle chart (lightweight-charts). Bottom: split into order book on the left and trades tape on the right. Below those: a tab strip for **Positions / Open Orders / Fills** (the tab auto-switches to *Fills* for 4 s after each fill so the user always sees confirmation).
- **Right column** (360 px fixed) — **Order Entry Panel** at the top, then **Agent Summary** at the bottom (up to 3 compact AgentTrace cards + 0–1 embedded DebatePanel + a "see all in Observatory" link).
- **Left rail** — surface nav, collapsible. Default expanded on first load.

**What the screenshot is showing:**
* **Chart** — symbol header (mark price flashes on tick), timeframe selector (1m / 5m / 15m / 1h / 4h / 1d), `fluid` mode so the candles paint correctly across viewport sizes (fix shipped in commit `86b81c9`).
* **Order book** — 50 price levels per side, 1.0-tick aggregation default, mid + spread anchored in the center. DOM rendering is virtualized; never more than ~60 rows live at once.
* **Trades tape** — TapeRow stream, max 200 buffered, newest at top. Auto-scroll lock if the user scrolls up (releases on scroll-to-top).
* **Positions** tab — every open position for the active profile, refreshing on every tick. Negative unrealized is `text-ask-500`, positive is `text-bid-500`.
* **Order entry** — side toggle (B / S keys), market/limit type (M / L), size, leverage, post-only / reduce-only flags. The big bid/ask button submits.
* **Agent summary** (right column, below order entry) — recent AgentTrace cards (TA, regime, sentiment). The composite is wired in `AgentSummaryPanel`. Empty state explicitly says "No agents emitting — check Pipeline Canvas, your profile may be paused."

**Source of truth (code):**
* `frontend/app/hot/[symbol]/page.tsx` // surface composition
* `frontend/components/trading/PriceChart.tsx` // chart + fluid + timeScale().fitContent() fix
* `frontend/components/trading/OrderBook.tsx` // virtualized DOM rendering
* `frontend/components/trading/TapeRow.tsx` // tape stream
* `frontend/components/trading/PositionsPanel.tsx` // positions table
* `frontend/components/trading/OrderEntryPanel.tsx` // order entry (composes Button + Tag + Input)
* `frontend/components/agentic/AgentSummaryPanel.tsx` // right-column agent summary
* `docs/design/05-surface-specs/01-hot-trading.md` // surface spec

## 1.2 Paper-order submission flow

**Screenshot file:** `hot_trading_order_submitted.png`
**Route:** `/hot/BTC-USDT` (after submission)

The redesign ships in **paper-trading mode by default** (`PRAXIS_PAPER_TRADING_MODE=false` on `main` but the default UI is paper; flipping to live requires explicit operator action). After clicking *Submit Buy/Sell* on a valid order, the panel:

1. POSTs to `/orders` (api_gateway) with the canonical OrderRequest schema
2. The order traverses validation → execution → fills (~milliseconds end-to-end in paper)
3. The Fills tab auto-focuses; the toast confirms the fill price and slippage

**What the screenshot is showing:**
* **Toast** — `sonner`-styled success with the symbol, side, qty, fill price, slippage %, and fill-latency ms.
* **Fills tab** — auto-tabs to *Fills* for 4 s, the new fill is at the top with `bg-bid-900/20` flash that fades.
* **Positions tab** — if this was an opening fill, a new row appears; if it was a closing fill, the existing row's qty decrements and the closed-trade ledger ticks.
* **Order entry panel** — clears on successful submit; size resets to the user's last-used; side stays as-is for chained orders.

**Source of truth (code):**
* `frontend/components/trading/OrderEntryPanel.tsx` // submit handler + validation
* `frontend/lib/api/client.ts:~250-300` // api.orders.create
* `services/api_gateway/src/routes/orders.py` // POST /orders
* `services/validation/src/main.py` // 4 CHECKs (regime / bias / circuit-breaker / risk) before approval
* `services/execution/src/main.py` // paper fill simulation

## 1.3 Connection states — live / degraded / stale

**Screenshot file:** `hot_trading_connection_states.png` *(may take 3 sub-screenshots for the 3 states)*

The connection pill in the top bar is `/ready`-aware (ADR-017). It polls every 5 s and renders one of three states:

| State | Color | Trigger |
|---|---|---|
| `LIVE` | `bg-bid-700/20 text-bid-300` | `/ready` returns 200 — engine + downstream healthy |
| `DEGRADED` | `bg-warn-700/20 text-warn-400` | `/ready` returns 503 — at least one non-critical dep down |
| `STALE` | `bg-ask-700/20 text-ask-400` | Pill hasn't received a successful poll in >15 s |

**What the screenshot is showing:**
* Left tile: green LIVE pill (typical state during normal operation).
* Middle tile: amber DEGRADED pill — taken during a Redis blip; the cluster `/health` stayed 200 for k8s liveness, the pill reflected reality.
* Right tile: red STALE pill — taken with the api_gateway stopped; the FE keeps trying.

**Source of truth (code):**
* `frontend/components/shell/ConnectionPill.tsx` // pill + poll loop
* `services/api_gateway/src/routes/health.py` // /ready endpoint
* `docs/design/09-decisions-log.md` // ADR-017 (pill polls /ready, not /health)

## 1.4 Kill-switch armed overlay

**Screenshot file:** `hot_trading_killswitch_armed.png`
**Route:** `/hot/BTC-USDT` (with KillSwitch toggled ON via Cmd+Shift+K)

When the kill switch is `armed-hard`, the cockpit takes a `bg-bg-canvas` overlay tinted with the danger token. The order entry panel disables and shows the kill-switch banner; the chrome pill flashes red.

**What the screenshot is showing:**
* Full-surface tint indicating "engine is paused".
* Order entry panel locked, banner reads "Kill switch armed (hard) — orders disabled. Disarm in `/risk` or with `Cmd+Shift+K`."
* Top-bar kill-switch indicator pulses.
* Open positions remain visible — the user must always be able to see exposure even when trading is paused.

**Source of truth (code):**
* `services/hot_path/src/kill_switch.py` // KillSwitch Redis key + reasoned arm/disarm log
* `services/api_gateway/src/routes/commands.py` // /commands/kill-switch endpoint
* `frontend/components/shell/KillSwitchModal.tsx` // confirm modal
* `frontend/lib/stores/killSwitchStore.ts` // shared kill-switch state

---

# Surface 2 — Agent Observatory (`/agents/observatory`)

The analyst's workbench. Three columns: agent roster on the left, chronological event stream in the middle, focus panel on the right. The default mode is COOL (calm enough for analysis) but the surface shifts to HOT mode density when an event stream is actively scrolling.

## 2.1 Three-column default

**Screenshot file:** `observatory_default.png`
**Route:** `/agents/observatory`

**What the screenshot is showing:**
* **Left rail — agent roster** (220 px). Each entry: `[AgentAvatar | name | StatusDot | last-emit time]`. Status dots: `live` (emitted within the liveness window, ~5 min), `idle` (emitted >5 min ago), `error` (last emit was an error trace), `disabled` (toggled off by the user).
* **Center column — event stream** (virtualized). Chronological feed of AgentTrace cards: regime_hmm → ta_agent → sentiment → debate → analyst. Each card shows the symbol, the agent's decision, confidence, and a one-line summary. Click expands the card in place; click the avatar zooms the right column into that agent's focus view.
* **Right column — focus panel** (460 px). When nothing is selected: a *summary dashboard* showing per-agent status cards, the current debate state (or "no debate in flight"), regime probabilities as a ConfidenceBar, and a 24h sentiment sparkline. When a specific event is selected: the full agent trace (see 2.2).
* Filter facets at the top: agent type, symbol, time window (last 1h / 4h / 24h / 7d), event type (decision / debate / abstain).

**Source of truth (code):**
* `frontend/app/agents/observatory/page.tsx` // surface composition
* `frontend/app/agents/observatory/_components/AgentRoster.tsx` // roster + filters
* `frontend/app/agents/observatory/_components/EventStream.tsx` // virtualized stream
* `frontend/app/agents/observatory/_components/FocusPanel.tsx` // focus + summary view
* `docs/design/05-surface-specs/02-agent-observatory.md` // surface spec

## 2.2 Agent trace expanded in focus panel

**Screenshot file:** `observatory_focus_panel_trace.png`
**Route:** `/agents/observatory` (after clicking a `ta_agent` trace)

A single selected agent trace, expanded in the right column. The trace lays out the full reasoning chain: inputs the agent saw, intermediate outputs, the final signal, and the downstream wiring (which gates this signal touched).

**What the screenshot is showing:**
* **Trace header** — agent name + avatar, symbol, timestamp (HH:MM:SS), confidence score, direction (BUY/SELL/HOLD), outcome chip (passed / abstained / blocked).
* **Inputs** — the snapshot the agent evaluated: indicator values for TA, regime probabilities for HMM, sentiment score for sentiment_agent, etc.
* **Tool calls** (LLM-based agents only) — for slm_inference and debate agents, the structured tool calls (prompt, response, model used, latency).
* **Downstream wiring** — which strategy condition this signal influenced, what the resolved confidence-after-adjustment was, and which gate (if any) blocked or approved.
* **Source view** — link to the source file that produced this agent's output (e.g., `services/ta_agent/src/main.py`). Devs can jump directly to the code.

**Source of truth (code):**
* `frontend/components/agentic/AgentTraceCard.tsx` // collapsed card
* `frontend/components/agentic/AgentTraceDetail.tsx` // expanded trace view
* `frontend/components/agentic/DebatePanel.tsx` // debate-cycle live panel
* `services/analyst/src/main.py` // trace aggregator that feeds the panel

## 2.3 Debate panel — live cycle

**Screenshot file:** `observatory_debate_live.png`
**Route:** `/agents/observatory` (with an active debate in flight)

Debates are multi-round LLM exchanges between the slm_inference and analyst agents when the engine wants a second opinion on a high-stakes signal. The DebatePanel renders the debate as it streams.

**What the screenshot is showing:**
* **Topic header** — what's being debated ("Open BTC long at 67,432?"), the symbol, the initiating signal's confidence.
* **Round counter** — `round 3 / 5  ▶ live` (live indicator pulses while streaming).
* **Per-round entries** — each round shows the position taken by each agent (e.g., `slm_inference: pro` / `analyst: con`) with a one-paragraph reasoning. Reasoning streams token-by-token while live.
* **Resolution chip** at the bottom — `approved` / `abstain` / `escalate-to-hitl` once the debate ends.
* **Transcript link** — full debate transcript is persisted in `debate_transcripts` (migration 016) for audit.

**Source of truth (code):**
* `frontend/components/agentic/DebatePanel.tsx` // panel composition + streaming
* `services/debate/src/main.py` // debate orchestrator
* `services/slm_inference/src/main.py` // primary debater
* `services/analyst/src/main.py` // adversarial debater
* `libs/storage/repositories/debate_repo.py` // transcript persistence

## 2.4 HITL approval queue

**Screenshot file:** `observatory_hitl_approval.png`
**Route:** `/agents/observatory` (with at least one pending HITL request)

When a profile's HITL gate is enabled, signals above a confidence threshold are held for human approval. The HITL queue lives in the Observatory because the operator needs the full agent context to decide.

**What the screenshot is showing:**
* **Pending requests** — each row: symbol, direction, confidence, suggested qty, age (`13s`, `1m 42s`). Right side: `[Approve]` / `[Reject]` / `[See full trace]` buttons.
* **Time-out** — pending requests auto-reject after the profile's `hitl_timeout_seconds` (default 5 min) to prevent stale orders from filling at moved prices. The age indicator shifts color as the timeout approaches.
* **Empty state** — "No pending approvals." This is the most common state and is the correct empty state per ADR-013 (render structure, never fake; don't ghost-fill a queue that's intentionally empty).

**Source of truth (code):**
* `frontend/app/agents/observatory/_components/HITLQueue.tsx` // queue panel
* `services/api_gateway/src/routes/hitl.py` // HITL approve/reject endpoints
* `libs/core/schemas.py` // HITLApprovalRequest / HITLApprovalResponse

---

# Surface 3 — Risk Control (`/risk`)

The highest-stakes surface. Per the surface spec: this surface **must remain interactive when other parts of the app are degraded**. The kill-switch keyboard shortcut (`Cmd+Shift+K`) and the positions read must work even if the agent system, the canvas backend, or the pipeline compiler is unavailable.

## 3.1 Default state — kill switch + exposure + active limits

**Screenshot file:** `risk_control_default.png`
**Route:** `/risk`

The page is a single vertical column at standard density (we explicitly resist compact mode on this surface — legibility under stress wins). Three stacked cards:

**What the screenshot is showing:**
* **Kill Switch card** — top. Shows the current state (`OFF` / `ARMED (soft)` / `ARMED (hard)`), who set it, when, and the reason if provided. Two buttons: `[Soft-arm]` blocks new orders, existing positions remain. `[Hard-arm]` blocks new orders AND auto-flattens all positions at market. `Cmd+Shift+K` shortcut also opens this from any surface.
* **Exposure card** — middle. Leverage utilization as a RiskMeter (`●────────────● 2.4× / 5.0×`), portfolio Value-at-Risk (1-day, 95% confidence) in USDC and as % of equity, concentration breakdown per symbol, current drawdown vs. peak-to-trough.
* **Active limits card** — bottom. Live status per limit: max position size (per symbol, current vs. cap), max leverage (current vs. cap), daily loss limit (with utilization %), rate limit (orders/min, last-1m count). Limits that are >60% utilized turn amber; breached limits turn red and a callout appears.
* **Recent violations** strip below — last 5 rejected orders with the rule that blocked them and the timestamp.

**Source of truth (code):**
* `frontend/app/risk/page.tsx` // surface composition
* `frontend/components/risk/KillSwitchCard.tsx` // arm/disarm with confirm
* `frontend/components/risk/ExposureCard.tsx` // exposure + RiskMeter
* `frontend/components/risk/ActiveLimitsCard.tsx` // live limit status
* `services/risk/src/main.py` // risk gate enforcement
* `services/hot_path/src/kill_switch.py` // KillSwitch state + log
* `docs/design/05-surface-specs/05-risk-control.md` // surface spec

## 3.2 Kill-switch modal — `Cmd+Shift+K`

**Screenshot file:** `risk_killswitch_modal.png`
**Route:** any surface (modal is global)

The kill-switch is the load-bearing safety control. The keyboard shortcut is the canonical path; the modal is intentionally heavyweight (two-step confirm) to prevent accidental triggers, but the shortcut itself is fast.

**What the screenshot is showing:**
* **Modal header** — large, accent-tinted: "Arm Kill Switch?"
* **Two arm options** — `Soft-arm` (blocks new orders only) and `Hard-arm` (also flattens positions). Each option spells out the consequences below it.
* **Reason field** — optional but recommended. Logged to the audit feed (`praxis:kill_switch:log` Redis list, surfaced on `/settings/audit`).
* **Confirm / Cancel buttons** — `Confirm` is `intent="danger"` to make the gravity visible. Escape and clicking the backdrop both cancel.

**Source of truth (code):**
* `frontend/components/shell/KillSwitchModal.tsx` // the modal
* `frontend/components/shell/KillSwitchModal.test.tsx` // covers Cmd+Shift+K binding, two-step confirm
* `services/hot_path/src/kill_switch.py` // KILL_SWITCH_LOG_KEY (Redis list for audit)

## 3.3 Per-profile risk monitor cards

**Screenshot file:** `risk_per_profile_cards.png`
**Route:** `/risk` (scroll to per-profile section)

Below the global cards, each active profile gets its own RiskMonitorCard summarizing its current standing against its risk limits. Useful when running multiple profiles concurrently to see which one is closest to a circuit-breaker trip.

**What the screenshot is showing:**
* **Per-card** — profile name, scope chip (live/paused), daily PnL vs. circuit-breaker limit (as a progress bar tinted bid/ask), current drawdown, allocation used.
* **Sorted** by closest-to-breach descending — the profile most likely to trip the circuit breaker is at the top.
* **Click-through** — clicking a profile card opens that profile's settings page in a new route (`/settings/profiles/{id}`).

**Source of truth (code):**
* `frontend/components/risk/RiskMonitorCard.tsx` // single card
* `frontend/app/risk/page.tsx` (per-profile section) // multi-card layout

---

# Surface 4 — Backtesting (`/backtests`)

The COOL-mode workbench for validating profile changes before they go live. Three sub-routes: list, detail, compare.

## 4.1 Run list — `/backtests`

**Screenshot file:** `backtests_list.png`
**Route:** `/backtests`

A dense Table-driven view of every backtest run. Selectable rows; selecting ≥2 enables the **Compare** action that opens `/backtests/compare?runs=A,B,C…`.

**What the screenshot is showing:**
* **Filter bar** — profile, date range, status (done / running / failed). Search by run ID.
* **Row columns** — run-id, profile name, date range, ROI (PnLBadge), Sharpe, maxDD, status.
* **Running rows** — show progress (`▣ running 64%`) and disable selection; only completed runs can be compared.
* **Selection footer** — `selected: N runs   [Compare ▸]   [Archive ▸]   [Delete ▸]`. Compare is the primary action; archive/delete are secondary.
* **New backtest** — top-right `[+ new backtest]` opens a side drawer with the run config (see 4.4).

**Source of truth (code):**
* `frontend/app/backtests/page.tsx` // list surface
* `frontend/app/backtests/_components/RunListTable.tsx` // table + selection
* `services/api_gateway/src/routes/backtest.py` // GET /backtest (list)
* `services/backtesting/src/main.py` // backtest worker

## 4.2 Run detail — `/backtests/{run_id}`

**Screenshot file:** `backtests_detail.png`
**Route:** `/backtests/{run_id}`

The post-mortem view for a single completed run. Headline metrics at the top, equity curve below, per-trade table at the bottom.

**What the screenshot is showing:**
* **Headline** — ROI / Sharpe / Sortino / maxDD / trades / win-rate / avgR / profit-factor. Each rendered as a StatCell.
* **Equity curve** — line chart of equity over time with drawdown overlay below (negative-bar histogram).
* **Per-trade table** — every simulated trade with entry, exit, hold duration, P&L $/%, reason for close, outcome chip. Paginated (43 pages for a multi-week 1-min run is typical).
* **Open in canvas as run** — opens the profile's pipeline canvas with the backtest's exact agent weights and rules pinned, so the user can inspect *the wiring that produced this result*.

**Source of truth (code):**
* `frontend/app/backtests/[run_id]/page.tsx` // detail surface
* `frontend/components/backtest/EquityCurveChart.tsx` // equity + drawdown chart
* `frontend/components/backtest/TradesTable.tsx` // paginated trades
* `libs/storage/repositories/backtest_repo.py` // backtest result persistence (migration 008 → 009 Decimal precision)

## 4.3 Compare view — `/backtests/compare`

**Screenshot file:** `backtests_compare.png`
**Route:** `/backtests/compare?runs=A,B,C`

Multiple runs overlaid on the same equity curve so divergence is visible at a glance. Below the chart is a comparison table — one row per run, sortable on any metric.

**What the screenshot is showing:**
* **Overlaid equity curves** — each run gets a distinct color; legend at the top. Hover shows synchronized cross-hair across all runs.
* **Comparison table** — trades, win %, avg return, max DD, Sharpe, profit factor; one row per run. Cells are colored relative to the best run in the column (the winner gets `bg-bid-700/20`).
* **Add more runs** — `[+ Add run]` button preserves the existing comparison set when adding new runs (`?compare=A,B,C&add=D`). This is the fix from commit `06dbb4a` — previously, adding a run would reset the comparison set.
* **Pin highlighted run** — clicking a run's row in the table makes that run the "highlighted" one in the simulated-trades table at the bottom.

**Source of truth (code):**
* `frontend/app/backtests/compare/page.tsx` // compare surface
* `frontend/components/backtest/ComparisonTable.tsx` // sortable comparison
* `frontend/components/backtest/EquityCurveChart.tsx` // multi-run overlay

## 4.4 New-backtest flow

**Screenshot file:** `backtests_new_drawer.png`
**Route:** `/backtests` (with the New Backtest drawer open)

Clicking `[+ New backtest]` opens a right-side drawer with the run config. Symbol, date range, timeframe (1m / 5m / 15m / 1h / 1d), slippage %, profile picker. Clicking *Run Backtest* queues the job; the drawer shows the live job ID and polling cadence (2 s) with a soft timeout of 10 minutes for multi-month 1-min runs.

**What the screenshot is showing:**
* **Symbol selector** — every market the engine ingests, with sub-search.
* **Date range picker** — two date inputs; defaults to "last 30 days".
* **Timeframe selector** — radio group (1m default).
* **Slippage** — basis points, defaulted to the engine's average observed slippage for the symbol.
* **Profile picker** — the saved trading profile to test; clicking *Edit rules first* opens `/canvas/{profile_id}` so the user can tweak before running.
* **Job status** — appears once queued: `Running… 0:43 elapsed  •  2 s poll`. On completion, a link to the run detail.

**Source of truth (code):**
* `frontend/app/backtests/_components/NewBacktestDrawer.tsx`
* `services/api_gateway/src/routes/backtest.py:~POST /backtest` // queue endpoint
* `services/backtesting/src/main.py` // 2 s poll, 10-min soft timeout

---

# Surface 5 — Settings (`/settings/{section}`)

CALM mode. The user is configuring intent here — not reacting to markets. Visual budget is generous: 15 px body baseline, larger form controls, more whitespace, one accent color, **no agent-identity colors anywhere**, no live updates beyond standard save acknowledgments.

The left rail is a section nav: Profiles → Exchange keys → Risk defaults → Notifications → Tax → Account → Sessions / API → Audit log. Content area is centered, max-width 720 px.

## 5.1 Settings nav (the CALM-mode shell)

**Screenshot file:** `settings_nav.png`
**Route:** `/settings` (lands on `/settings/profiles` by default)

**What the screenshot is showing:**
* Left rail with 8 section links (matches the spec's section order). Active link is `bg-bg-panel` with `text-fg`. Inactive: `text-fg-secondary`.
* Header row at the top of every section page: title (22 px, `font-semibold`) + one-line description.
* Save-bar at the bottom of editable sections — sticky-bottom strip that appears only when there are unsaved changes. CALM mode forms use **explicit Save buttons** (no auto-save, deliberately).
* Tone is *officespace, not chatbot* — no "Hi! Ready to set up?" copy. Direct, professional, considered.

**Source of truth (code):**
* `frontend/app/settings/layout.tsx` // shell + section nav
* `frontend/app/settings/page.tsx` // landing redirect → profiles
* `docs/design/05-surface-specs/06-profiles-settings.md` // surface spec

## 5.2 Profiles — list + edit

**Screenshot file:** `settings_profiles.png`
**Route:** `/settings/profiles`

The list of all trading profiles. Each card shows: profile name, status badge (Live / Paused), last-updated, node count, 7-day P&L / trades / win-rate, three buttons: `[Open in canvas]` `[Edit settings]` `[Run backtest]`.

**Important:** profile *editing is split*. Pipeline structure → Pipeline Canvas. Settings/identity → here. The split is by *domain*: behavior versus configuration.

**What the screenshot is showing:**
* Card per profile with summary metrics.
* Empty state (if no profiles): "No profiles yet. Create one in Pipeline Canvas to start trading." + `[Open canvas]` CTA.

**Source of truth (code):**
* `frontend/app/settings/profiles/page.tsx`
* `frontend/components/settings/ProfileCard.tsx`
* `services/api_gateway/src/routes/profiles.py` // CRUD endpoints

## 5.3 Exchange keys

**Screenshot file:** `settings_exchange_keys.png`
**Route:** `/settings/exchange`

API keys for connected exchanges. Per CLAUDE.md security: never enter sensitive financial data on the user's behalf — direct them to enter it themselves. The form makes that explicit.

**What the screenshot is showing:**
* **List of connected keys** — masked (`hl_••••••••3a4f`); never re-displays a saved secret.
* **Add exchange form** — exchange dropdown, label, API key, secret, permissions checkboxes (trade / withdraw — recommend leaving withdraw off).
* **Info banner** — "Praxis never stores keys with withdraw permissions enabled by default. Confirm withdraw is off in your exchange API settings before saving."
* **Test connection** button — calls CCXT `fetch_balance` to confirm the key works and asserts withdraw is disabled (skipped on testnet).

**Source of truth (code):**
* `frontend/app/settings/exchange/page.tsx`
* `services/api_gateway/src/routes/exchange_keys.py` // list + create + test
* `libs/core/secrets.py` // GCP Secret Manager wrapper

## 5.4 Risk defaults *(newly wired — May 2026)*

**Screenshot file:** `settings_risk_defaults.png`
**Route:** `/settings/risk`

User-level risk caps that apply to **newly created profiles**. This page was previously "shipped shell, awaiting backend"; it was wired end-to-end in this push (migration `021_user_risk_defaults.sql`, repository + API + form). The form persists; what it doesn't yet do is *propagate to running profiles* — that's the recompile fan-out, scoped as a separate project. The page discloses that inline.

**What the screenshot is showing:**
* **Five caps**, each as a labeled input:
  * **Max position size** (% of free capital × signal confidence)
  * **Max leverage** (× notional / margin)
  * **Max daily loss** (% halt threshold)
  * **Rate limit** (orders / minute)
  * **Auto-pause drawdown** (% drawdown trip)
* **Inline note** at the top: "Defaults apply to newly created profiles. Propagation to *running* profiles (the recompile fan-out) ships in a follow-up. Existing profiles keep whatever caps they were created with until then."
* **Last-saved timestamp** below the form. If never saved, "No saved defaults yet. Showing canonical fallbacks."
* **Sticky save bar** at the bottom (only visible when dirty).

**Source of truth (code):**
* `frontend/app/settings/risk/page.tsx` // rewritten in this push
* `frontend/lib/api/client.ts` // `api.riskDefaults` wrapper
* `services/api_gateway/src/routes/risk_defaults.py` // GET/PUT /risk-defaults
* `libs/storage/repositories/user_risk_defaults_repo.py`
* `libs/core/schemas.py` // UserRiskDefaultsPayload + UserRiskDefaultsResponse
* `migrations/versions/021_user_risk_defaults.sql`

## 5.5 Notifications *(partial — wired booleans + Pending events)*

**Screenshot file:** `settings_notifications.png`
**Route:** `/settings/notifications`

Per the spec, this is the per-event delivery matrix: each event × email/push/audible. Today, the backend exposes two coarse booleans (`email_alerts`, `trade_notifications`) — those are wired. The richer matrix (5 spec'd events × 3 channels) is Pending — the page lists each future event with a one-line reason, so the partner sees exactly what's coming.

**What the screenshot is showing:**
* **Active toggles** — Daily summary email, Trade fills.
* **Pending events** section below, each tagged `Pending` with the gating dependency:
  * Kill-switch state changes — critical-path event; high-signal in-app + audible.
  * Large fills (size threshold) — needs per-symbol UX spec.
  * Agent override events — sourced from analyst; needs a delivery schema.
  * Profile drawdown trigger — currently surfaced only in Risk Control.
  * Monthly tax report ready — pairs with the tax-export action.
* **Anti-pattern note** — *no* "all on/off mega-toggle"; each event toggles separately so a stressed user can't silence everything by accident.

**Source of truth (code):**
* `frontend/app/settings/notifications/page.tsx`
* `services/api_gateway/src/routes/` — `/preferences` route is Pending (the FE has the client wrapper; the backend route lands with the matrix schema)

## 5.6 Tax *(Pending — backend in design)*

**Screenshot file:** `settings_tax.png`
**Route:** `/settings/tax`

The form is rendered to spec. The tax microservice exists (port 8089) but currently only exposes `/calculate` and `/health` — it's a tax estimator, not a report generator. Full report generation (persistence, FIFO/HIFO/LIFO export, year-by-year history) is its own project. The page surfaces this honestly with an inline note and a disabled generate button.

**What the screenshot is showing:**
* **Generate form** — Year selector (last 5 years), Jurisdiction (US / UK / EU / CA / AU), Method (FIFO / HIFO / LIFO — intentionally no default; the user must pick the one their jurisdiction allows).
* **Disabled Generate button** — clicking it shows a toast pointing to the inline note.
* **Prior reports** section — empty state.
* **Manual lot adjustments** — Pending.

**Source of truth (code):**
* `frontend/app/settings/tax/page.tsx`
* `services/tax/src/main.py` // current scope: `/calculate` + `/health`

## 5.7 Account

**Screenshot file:** `settings_account.png`
**Route:** `/settings/account`

User identity + display preferences. Per CLAUDE.md security: never auto-fill or auto-set passwords; the user types directly.

**What the screenshot is showing:**
* Display name + avatar (avatar comes from the OAuth provider).
* Email + verified-state pill.
* Password (manual reset only; OAuth users see "Sign-in via {provider}").
* 2FA setup.
* Theme preference (system / dark / light — though light is a future commitment, not v1).
* Density preference per-surface (set here as defaults).

**Source of truth (code):**
* `frontend/app/settings/account/page.tsx`
* `services/api_gateway/src/routes/auth.py` // /auth/me + provider data

## 5.8 Sessions / API *(newly wired — May 2026)*

**Screenshot file:** `settings_sessions.png`
**Route:** `/settings/sessions`

Active sessions list. This page was previously single-session-only ("only the current browser appears" with a Pending tag); it was wired end-to-end in this push. Cross-device session listing now reflects reality — every browser that has authenticated shows up with device/browser/IP/last-seen, and any session can be revoked individually.

API tokens and webhooks remain Pending — they're each their own project (API tokens needs a token-issuance system with hashed storage + scoped permissions; webhooks pair with the notification matrix).

**What the screenshot is showing:**
* **Active sessions list** — each row: device icon + browser/device label, IP + last-seen timestamp, `[Sign out]` button on the current session and `[Revoke]` on others.
* **"This session" pill** — green StatusDot marks the row representing the current browser (matched via the `session_id` claim on the access token).
* **Revoke action** — flips `revoked_at` on the row; the next `/auth/refresh` for that session fails and the affected browser is forced back to `/login`.
* **API tokens** section — empty, marked Pending with the note that it builds on the session-revocation infrastructure that landed today.
* **Webhook destinations** section — empty, marked Pending, paired with the notification matrix.

**Source of truth (code):**
* `frontend/app/settings/sessions/page.tsx` // rewritten in this push
* `frontend/lib/api/client.ts` // `api.sessions` wrapper
* `services/api_gateway/src/routes/auth.py` // /auth/sessions + /auth/sessions/{id}/revoke
* `services/api_gateway/src/middleware/auth.py` // create_refresh_token now returns (token, jti)
* `libs/storage/repositories/user_session_repo.py`
* `migrations/versions/022_user_sessions.sql`

## 5.9 Audit log *(kill-switch wired; other sources pending)*

**Screenshot file:** `settings_audit.png`
**Route:** `/settings/audit`

Read-only feed of significant user actions. The endpoint is wired against `services/api_gateway/src/routes/audit.py::list_user_audit_events`. Today's emitted source: **kill-switch transitions** (from the `praxis:kill_switch:log` Redis list). Spec'd-but-not-yet-emitted sources: profile changes, API key rotations, agent overrides, failed sign-ins — these stay tagged Pending on the page itself.

**What the screenshot is showing:**
* **Filter row** — event type, from-date, to-date.
* **Partial-feed banner** — "N of M event sources are wired. Pending sources will start appearing here as their producers land — no UI change needed."
* **Event list** — each row: type chip, description, ISO timestamp, actor. CSV export available.
* **"What gets recorded" section** at the bottom — per-source `Recorded` / `Pending` tags so the user knows precisely which sources are emitting.

**Source of truth (code):**
* `frontend/app/settings/audit/page.tsx`
* `frontend/lib/api/client.ts` // `api.audit.userEvents`
* `services/api_gateway/src/routes/audit.py` // /user-events aggregator
* `services/hot_path/src/kill_switch.py` // KILL_SWITCH_LOG_KEY (today's only emitter)

---

# Appendix A — What's shipping next

The redesign branch merged to `main` on 2026-05-12. Five Pending items remain — each scoped as its own backlog project. Two of the five were wired in this push (Risk defaults, Sessions); three remain:

| Surface area | Pending | What lands next |
|---|---|---|
| Settings / Risk defaults | Recompile fan-out | Mechanism to propagate user-level defaults to *running* profiles. Today defaults apply to new profiles only. |
| Settings / Notifications | Per-event delivery matrix | Schema change replacing two coarse booleans with email × push × audible per event. |
| Settings / Tax | Report generator | Service-side persistence, FIFO/HIFO/LIFO export, year-history. |
| Settings / Sessions | API tokens + webhooks | Token issuance with hashed storage + scoped permissions; webhook destination CRUD. |
| Settings / Audit | Per-source emitters | Profile changes, API-key rotations, agent overrides, failed sign-ins — each adds one block to the audit aggregator. |

Tracked in `docs/TECH-DEBT-REGISTRY.md` row 22.

# Appendix B — Architecture at a glance

The frontend talks to a single API gateway (`api_gateway` on port 8000) that fans out to 18 backend services. The redesign is a frontend-only initiative — no backend services were renamed or restructured during the cutover. The services are:

| Service | Port | Role in the UI |
|---|---|---|
| api_gateway | 8000 | All FE → BE traffic, including WebSocket fan-out |
| ingestion | 8080 | Source of market data displayed on every chart and orderbook |
| validation | 8081 | The 4-CHECK pipeline (regime / bias / circuit-breaker / risk) that gates every order |
| hot_path | 8082 | Owns the KillSwitch state |
| execution | 8083 | Paper-fill simulation (live trading flips a flag, same code path) |
| pnl | 8084 | Per-tick PnL recompute; stop-loss monitor |
| logger | 8085 | Audit event sink |
| backtesting | 8086 | Backend for the Backtests surface |
| analyst | 8087 | Agent attribution + decision narratives |
| archiver | 8088 | Daily report generation |
| tax | 8089 | Tax calculator (report generator pending) |
| ta_agent | 8090 | TA-based signal generation |
| regime_hmm | 8091 | Regime classification (HMM) |
| sentiment | 8092 | Sentiment signal |
| risk | 8093 | Position-level risk enforcement |
| rate_limiter | 8094 | Sliding-window order-rate cap |
| slm_inference | 8095 | LLM-based inference (debate, override analysis) |
| debate | 8096 | Multi-agent debate orchestrator |
| strategy | worker | Final signal assembly |

The control plane (api_gateway) is the only service the FE directly addresses. WebSocket connections route to `/ws` on api_gateway for orderbook/tape/positions/decisions streams.

For the partner: the redesign was a deliberate 9-phase initiative ending in a `--no-ff` merge that's preserved in git history. The legacy frontend is recoverable via the `pre-redesign-cutover` git tag if needed.

---

*This walkthrough is the source for the PDF deliverable at `docs/PRAXIS-UI-WALKTHROUGH-REDESIGN.pdf` (built via `scripts/build_ui_walkthrough_redesign_pdf.py`). Screenshots referenced above should live in `scrnshts/redesign/` and follow the filename convention indicated under each section. The legacy walkthrough at `docs/praxis_ui_walkthrough.md` and `docs/PRAXIS-UI-WALKTHROUGH_updated.pdf` remains in place as audit trail.*
