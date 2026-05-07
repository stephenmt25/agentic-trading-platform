# Surface Spec — Hot Trading

**Mode:** HOT (cockpit)
**URL:** `/hot/{symbol}` (e.g., `/hot/BTC-PERP`)
**Backed by:** `api_gateway`, `ingestion`, `hot_path`, `validation`, `execution`, `pnl`
**Frequency:** the user spends 70%+ of their session here
**Density:** maximum

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
