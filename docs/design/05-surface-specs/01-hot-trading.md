# Surface Spec — Hot Trading

**Mode:** HOT (cockpit) at `/hot/{symbol}`; COOL (observation) under `/hot/profiles[/...]`
**URLs:**
- `/hot/{symbol}` (e.g., `/hot/BTC-PERP`) — symbol-scoped execution cockpit (this document §1–§8)
- `/hot/profiles` — profile comparison grid (this document §9.1)
- `/hot/profiles/{id}` — per-profile observation cockpit with four tabs (§9.2)

**Backed by:** `api_gateway`, `ingestion`, `hot_path`, `validation`, `execution`, `pnl`, `analyst`
**Frequency:** the user spends 70%+ of their session here
**Density:** maximum on `/hot/{symbol}`; medium on `/hot/profiles[/...]`

The "Hot Trading" rail entry covers both **execution** (symbol-axis at `/hot/{symbol}`) and **profile observation** (profile-axis under `/hot/profiles[/...]`). The two are deliberately separated by URL because the axes differ: one is "this symbol across all profiles," the other is "this profile across all symbols." Mixing them on a single URL was rejected (see ADR-018). The surface header carries a scope-aware breadcrumb so the user always knows which axis they're on.

---

## 1. Layout (desktop, ≥1440px)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ◀▶ ⚡ Hot Trading > BTC-PERP   Profile: Aggressive-v3                   [search] │
│ ◉ live  ⚠ regime: choppy  ⏱ 12ms  🛡 armed-soft  🤖 5 agents  ⚖ +0.84%        │
├──────────┬───────────────────────────────────────────┬──────────────────────────┤
│          │                                            │                           │
│   left   │              CHART                          │      ORDER ENTRY        │
│   rail   │       (TradingView-class candle/depth)      │                           │
│          │                                            │      side / size /       │
│ ⚡        │                                            │      price / leverage    │
│ 🤖       │                                            │                           │
│ ⊕        │                                            │      ────────────        │
│ 📊       │                                            │                           │
│ 🛡       │                                            │      submit (bid/ask)    │
│ ⚙       │                                            │                           │
│          │                                            │                           │
│          ├───────────────────────────────────────────┤                           │
│          │                                            │      ────────────        │
│          │  ORDER BOOK   │  TRADES TAPE              │                           │
│          │   (split)     │   (streaming)              │      AGENT SUMMARY        │
│          │               │                            │      (collapsed traces)  │
│          │               │                            │                           │
│          ├───────────────┴────────────────────────────┤                           │
│          │  POSITIONS / OPEN ORDERS / FILLS (tabs)    │                           │
│          │                                            │                           │
└──────────┴───────────────────────────────────────────┴──────────────────────────┘
```

Three-column grid: left rail (collapsible to 56px), center column (chart + book/tape + positions), right column (order entry + agent summary). Right column is fixed 360px. Left rail is fixed 56/220px collapsed/expanded.

The center column is internally a 2-row split: chart on top (60% height), book/tape + positions on bottom (40%). Bottom subdivides further: book/tape side-by-side, positions/orders/fills as tabs at the very bottom.

**At ≤1280px**, right column collapses into a tab in the chart panel ("Trade") — full-screen chart on landing, tap "Trade" to expose order entry.

**At ≤1024px** (tablet/mobile), this surface enters monitor-only mode: positions, PnL, kill switch are visible; **order entry is hidden**. This is the "monitor-only" constraint formalized in ADR-006 — a values-driven safety stance, not a layout limitation. See IA §7.

---

## 2. Information ranking (top to bottom of the user's attention budget)

1. **PnL** — chrome top-bar pill, also displayed in display-sm in the right column header
2. **Mark price + last trade** — chart header, large, flashes on tick
3. **Order book mid + spread** — center of the book panel
4. **Open positions size and unrealized** — positions table, top row
5. **Agent debate output (if a fresh debate exists)** — top of the agent summary
6. **Open orders queue depth** — secondary chart layer or open-orders tab
7. **Recent fills** — fills tab (auto-tabs to "fills" for 4s after each fill)

Anything below #7 is not strictly Hot mode information — it's drillable.

---

## 3. Components used

| Region | Components |
|---|---|
| Chrome top-bar | StatusDot, Pill, PnLBadge, Avatar, command palette trigger |
| Chart | (chart library, e.g., TradingView Lightweight Charts) wrapped in a custom toolbar; uses StatusDot for live/replay |
| Order book | OrderBook (split, 50 levels, 1.0 tick aggregation default) |
| Trades tape | TapeRow stream, max 200 visible |
| Positions | Table dense + PositionRow + PnLBadge inline |
| Order entry | OrderEntryPanel + Tag (post-only/reduce-only flags) + Button (large bid/ask) |
| Agent summary | `AgentSummaryPanel` (composite — see `04-component-specs/agentic.md`) — wraps up to 3 compact AgentTrace cards + 0–1 embedded DebatePanel + "see all in Observatory ▸" link |

---

## 4. Live behaviour

- Order book updates at the source rate (no throttling). DOM rendering is virtualized — never more than ~60 visible rows.
- Trades tape inserts at top, max 200 buffered. Auto-scroll lock as described in `data-display.md`.
- Positions row "unrealized PnL" updates every tick *for the relevant symbol*, every 100ms for others.
- Chart updates 1m candles in real-time (latest candle ticks); other timeframes redraw on close.
- Agent summary refreshes when an agent emits a new trace; older traces collapse.

---

## 5. Keyboard map

| Key | Action |
|---|---|
| `B` | Toggle order side to Buy |
| `S` | Toggle order side to Sell |
| `M` | Switch order type to Market |
| `L` | Switch order type to Limit |
| `1–9` | Set size as a multiplier of last-used (1 = 1×, 2 = 2×, … 9 = 9×) |
| `+` / `-` | Adjust price by 1 tick |
| `Enter` | Submit current order (when valid) |
| `Esc` | Clear order entry |
| `Cmd+K` | Command palette |
| `Cmd+Shift+K` | Kill switch (modal confirm) |
| `O` | Focus the order entry side selector |
| `T` | Focus tape |
| `?` | Keyboard reference modal |

Every shortcut is also exposed in tooltips and the `?` modal. No hidden shortcuts.

---

## 6. Edge / failure cases

| Case | Treatment |
|---|---|
| Lost market data feed | Chrome `◯ replay` becomes `⚠ stale` in `warn.500`; chart shows stale-overlay; order entry disabled with explainer banner |
| Validation service unreachable | Order entry submit shows "validating service unreachable" inline; user can retry |
| Risk service flags violation | OrderEntryPanel goes to `risk-block` state; banner cites the rule (e.g., "would exceed max position size") |
| Kill switch armed (hard) | Entire surface gets `--color-danger-armed-bg` overlay; OrderEntryPanel is `kill-switch-armed`; the "🛡 armed-hard" pill in chrome flashes |
| Liquidation in progress on a position | The position row gets the `liquidating` state + a callout banner above the positions table linking to Risk Control |
| Agent service unreachable | Agent summary shows a placeholder "agent feed unreachable — using last cached output (3m ago)"; doesn't disable trading |

---

## 7. Empty states

| Region | Empty state copy |
|---|---|
| No open positions | "No open positions. Use the order entry panel to place your first order." (no illustration; this is HOT mode) |
| No recent fills | "No fills today." (single line in fills tab) |
| No active agents | "No agents emitting. Check Pipeline Canvas — your profile may be paused." (link to canvas) |
| No tape activity (illiquid symbol) | "Awaiting trades — last trade 14 minutes ago." |

Empty states in HOT mode are spartan — one line of copy, no graphics, no recommendations beyond the link if one is helpful.

---

## 8. Critical-path note

This surface must remain interactive when other parts of the app are degraded. Specifically: the kill-switch keyboard shortcut (`Cmd+Shift+K`) and the positions read MUST work even if the agent system, the canvas backend, or the pipeline compiler is unavailable. The harness should treat these two paths as having higher SLO than the rest of the surface.

---

## 9. Sub-routes — Profile observation under `/hot/profiles`

These routes cover profile-axis observation. Mode is **COOL** (review-while-things-happen), not HOT — there is no order entry, no kill switch interaction beyond visibility, and the density relaxes one step from the symbol cockpit. The rail entry, top bar, and engine-totals pill are shared with `/hot/{symbol}`. See ADR-018 for the placement rationale.

### 9.1 `/hot/profiles` — comparison grid

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ◀▶ ⚡ Hot Trading / Profiles                                            [search] │
│ engine totals: P&L +$1,234.56 · trades 287 · win 54.4% · max DD -3.2% · Sharpe 1.6 │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─ Mean-Reversion ──────────┐  ┌─ High-Volume-Breakout ────┐  ┌─ ETH-Momentum ─┐ │
│  │  ◉ live · paper            │  │  ◉ live · paper            │  │  ◉ live         │ │
│  │  P&L  +$412.30  ▁▂▄▆▇▆▅▄  │  │  P&L  -$118.42  ▆▅▄▃▂▁▁▂  │  │  P&L  +$84.10  │ │
│  │  trades today  18           │  │  trades today  41           │  │  trades today 6 │ │
│  │  win rate      55.6%       │  │  win rate      48.8%       │  │  win rate 66.7% │ │
│  │  drawdown      -1.2%       │  │  drawdown      -3.2%       │  │  drawdown -0.4% │ │
│  │  alloc / max   12% / 25%   │  │  alloc / max   18% / 25%   │  │  alloc 3%/25%   │ │
│  └────────────────────────────┘  └────────────────────────────┘  └─────────────────┘ │
│                                                                                   │
│  ┌─ + Add profile ─┐  (links to Pipeline Canvas to create or activate one)        │
│  └──────────────────┘                                                              │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

A virtualized grid of cards, one per active profile, sorted by net P&L since boot (descending). Each card carries:

- **Header** — profile name (clickable → `/hot/profiles/{id}`), mode pill (`paper` / `testnet` / `live`), live/idle StatusDot
- **P&L row** — net P&L since boot + 24-tick sparkline (positive bid-green, negative ask-red)
- **Today** — trades count + win rate today (UTC day)
- **Drawdown** — current drawdown from peak equity
- **Allocation** — current allocation %, with the profile's `risk_limits.max_allocation_pct` as the cap
- **Footer (hidden by default, hover-reveals)** — open positions count, blocked-decisions count today, last decision time

Sort order is fixed (net P&L desc); no column-sort UI on this surface — comparison view, not table view.

**Empty state:** "No active profiles. Activate one in Pipeline Canvas to begin observation." (links to `/canvas`)

**Cross-link rules** (per IA §3):
- Click profile name → `/hot/profiles/{id}` (this profile's cockpit)
- Click P&L sparkline → `/hot/profiles/{id}` Daily P&L tab
- Click drawdown → `/risk` (scrolled to the all-profiles matrix)
- Click open-positions count → `/hot/profiles/{id}` Positions tab

### 9.2 `/hot/profiles/{id}` — profile observation cockpit

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ◀▶ ⚡ Hot Trading / Profile / Mean-Reversion          [switch profile ▾] [search]│
│ engine totals: P&L +$1,234.56 · trades 287 · win 54.4% · max DD -3.2% · Sharpe 1.6 │
│ ─ this profile ────────────────────────────────────────────────────────────────  │
│ P&L +$412.30  ·  18 trades today  ·  win 55.6%  ·  DD -1.2%  ·  alloc 12% / 25% │
├──────────────────────────────────────────────────────────────────────────────────┤
│ [ Decisions ]  [ Positions ]  [ Daily P&L ]  [ Attribution ]                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│                              (active tab content)                                 │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Surface header carries two stat strips:
- **Engine totals** (shared chrome) — system-wide since boot
- **This profile** — net P&L, trades today, win rate today, drawdown, allocation vs. cap

Tabs are URL-routable: `/hot/profiles/{id}?tab=decisions` (default), `?tab=positions`, `?tab=daily-pnl`, `?tab=attribution`. Tab choice persists per-profile in localStorage (`praxis:profile-cockpit:tab:{id}`).

**The "switch profile" dropdown** in the breadcrumb is a Select that jumps to `/hot/profiles/{newId}` preserving the active tab.

#### 9.2.1 Decisions tab (default)

Lifts the legacy `frontend/components/decisions/DecisionFeed.tsx` component verbatim into this tab, scoped to the URL profile ID. The Feed shows engine signals as they're evaluated:

- approved entries (green left-border) → with the resulting order ID linking to `/hot/{symbol}`
- blocked entries (red left-border) → with the reason chain (gate / agent / rule that fired)
- pending entries (amber left-border) → for HITL approvals queue, linking to `/agents/observatory`

**Pending tag inline** if the backend doesn't yet expose a profile-scoped `/decisions/{profile_id}/stream` endpoint. The lift-and-shift uses whatever the legacy `DecisionFeed` already consumed; the spec-conformant rewrite is a separate polish pass (see Phase 10.3 in the execution plan).

#### 9.2.2 Positions tab

Cross-symbol positions for this profile. Reuses `frontend/components/trading/PositionRow.tsx` but bound to `api.positions.list({ profile_id })` instead of the current `{ status: 'open' }` filter. Symbol column is shown explicitly (in `/hot/{symbol}` it was implicit).

Columns: symbol · side · size · entry · mark · unrealized · margin · age · close-N% actions.

**Pending tag** for the close-N% actions if the backend `POST /positions/{id}/reduce` endpoint isn't profile-scoped — should accept either symbol or position_id and reject if not in this profile.

#### 9.2.3 Daily P&L tab

Lifts `frontend/components/performance/DailyReportDetail.tsx` and the legacy `/trade` daily-report drawer. Two panels:

- **Sparkline strip** — N-day net P&L bars + per-day click row
- **Drawer (opens on row click)** — full transparency report for the chosen day: summary metrics + every closed trade with full decision lineage (agent inputs → gates → final decision) + every blocked attempt with the reason that blocked it

Day rows are clickable; click opens the drawer (`?date=2026-05-12`) in-surface (right-side, not full-screen).

#### 9.2.4 Attribution tab

Lifts `frontend/app/analytics/PerformanceContent.tsx`. Three sections:

- **Gate efficacy** — for each gate in the profile's pipeline, the count of (signals seen / signals blocked / signals approved) over a configurable window, plus the realized P&L of trades the gate let through vs. (hypothetically) blocked trades' projected P&L
- **Weight evolution** — line chart of agent weights over time (`agent_weight_history` table), one line per agent in this profile's pipeline
- **Per-agent contribution** — bar chart of realized P&L attributed to each agent based on weighted-score contribution per trade

**Pending tag** for each section that lacks its backend feed. See TECH-DEBT-REGISTRY for the per-tab backend gaps.

### 9.3 Live behaviour (sub-routes)

- `/hot/profiles` — cards refresh on `pubsub:pnl_updates` ticks; full refetch every 30s
- `/hot/profiles/{id}` Decisions — appends new rows via the profile's decision stream
- Positions — re-polls `api.positions.list({ profile_id })` every 5s and on `pubsub:position_updates`
- Daily P&L — fetches `paper-trading/reports?profile_id=...` on mount; sparkline updates on day-rollover only
- Attribution — refreshes every 60s (analytical view, not real-time)

### 9.4 Empty states (sub-routes)

| Region | Empty state |
|---|---|
| No active profiles (`/hot/profiles`) | "No active profiles. Activate one in Pipeline Canvas to begin observation." (link to `/canvas`) |
| No decisions yet (cockpit Decisions tab) | "No decisions yet today. Agents may still be initializing; check Pipeline Canvas." |
| No positions (cockpit Positions tab) | "This profile has no open positions. Decisions tab shows what the engine is evaluating." |
| No daily reports (cockpit Daily P&L tab) | "No completed trading days yet. Reports generate at 00:00 UTC." |
| No attribution data (cockpit Attribution tab) | "Attribution requires at least 10 closed trades. Profile has N." |

### 9.5 Edge / failure cases (sub-routes)

| Case | Treatment |
|---|---|
| Decision-stream WS gap | Decisions tab shows "stream paused, retrying…" inline; the polled fallback fetches the last N decisions on mount |
| Profile deleted while user has it open | Cockpit redirects to `/hot/profiles` with a toast "Profile {name} was deleted." |
| Profile deactivated externally | Cockpit shows a "Paused" banner above the tabs; tab content remains visible (read-only) |
| Backend missing one of the per-tab endpoints | Tab renders structure + inline Pending tag per ADR-013 — never fakes data |

### 9.6 Keyboard map (sub-routes)

| Key | Action |
|---|---|
| `1` / `2` / `3` / `4` | Switch to Decisions / Positions / Daily P&L / Attribution tab |
| `P` | Open the "switch profile" dropdown |
| `G` then `H` | Go to `/hot/profiles` (grid) |
| `J` / `K` | Down / up in the active tab's list |
| `Cmd+K` | Command palette (includes "go to profile X" entries) |
