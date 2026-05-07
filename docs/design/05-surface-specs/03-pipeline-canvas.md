# Surface Spec — Pipeline Canvas

**Mode:** COOL (the laboratory)
**URL:** `/canvas/{profile_name}` (e.g., `/canvas/Aggressive-v3`)
**Backed by:** `strategy`, `pipeline_compiler` (lib), profile settings via `api_gateway`
**Frequency:** the user spends 10–20% of their session here, more during profile authoring
**Density:** medium

> **Authority statement (load-bearing — read first):** The Pipeline Canvas is the source of truth for `trading_profiles.pipeline_config`. Saving the canvas triggers atomic recompilation of `strategy_rules` via `libs/core/pipeline_compiler.py` (per CLAUDE.md §2C). The canvas is **not a visualization** — it is the editor. Direct edits to `strategy_rules` (e.g., via legacy `PUT /profiles/{id}`) bypass the canvas; the long-term path is canvas-only edits via `PUT /agent-config/{profile_id}/pipeline`. Code generated for this surface MUST treat save as a compile event with corresponding error handling.

---

## 1. Layout

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ◀▶ ⊕ Pipeline Canvas > Aggressive-v3                              [search]     │
│ ◯ saved 3m ago  ⚠ 1 unsaved change                                              │
├────────────────┬───────────────────────────────────────────────┬─────────────────┤
│                │                                                 │                  │
│   NodePalette  │                  CANVAS                          │ NodeInspector  │
│                │             (infinite, pannable,                  │   (when a       │
│  ▾ AGENTS      │              zoomable)                            │    node is     │
│  ▾ SOURCES     │                                                  │    selected)    │
│  ▾ TRANSFORMS  │     [ingestion]──┬──[ta_agent]──────┐           │                  │
│  ▾ DECISIONS   │                  ├──[regime_hmm]────┤            │  Header         │
│  ▾ SINKS       │                  ├──[sentiment]─────┤            │  Inputs        │
│                │                  └──[slm_inference]─┘            │  Configuration │
│                │                                  │              │  Outputs        │
│                │                              [debate]            │  Live activity │
│                │                                  │              │  Tests          │
│                │                              [strategy_eval]    │                  │
│                │                                  │              │                  │
│                │                              [risk_check]       │                  │
│                │                                  │              │                  │
│                │                              [execution]        │                  │
│                │                                                 │                  │
│                │                                                 │                  │
│                │                                       [▣ minimap]│                  │
│                │   [▶ run paper]  [▶ run live]  [▶ run backtest] │                  │
└────────────────┴───────────────────────────────────────────────┴─────────────────┘
```

Three-column: 240px left (NodePalette), flexible center (Canvas), 380px right (NodeInspector, hidden when no selection — center reclaims its space). RunControlBar pinned at the top of the canvas viewport. MiniMap pinned bottom-right of the canvas.

---

## 2. The canvas surface

- Infinite plane, pannable (space + drag, or middle-click drag), zoomable (scroll, or `Cmd+0` to fit).
- Snap-to-grid (12px) when dragging nodes, with shift to disable snap.
- Multi-select via marquee (drag from empty space) or shift-click.
- Group nodes via `Cmd+G` — visually a translucent rounded rectangle behind a set of nodes; named, draggable as a unit.
- Layout assist: `Cmd+Shift+L` triggers an auto-layout pass (left-to-right, dagre-style).
- Comments (sticky-note style) can be placed on the canvas; rendered in `--bg-raised` rectangles with 13px caption type.

---

## 3. The save model

Saving is *atomic with strategy_rules compilation*. From the user's POV:
- "Saved 3m ago" indicator shows the last successful save+compile.
- "Unsaved change" means: edits not yet pushed to backend.
- "Compile error" means: edits saved but compiler refused (e.g., circular flow); banner explains, edits remain on canvas, profile stays at last-good rules.
- `Cmd+S` saves. Auto-save off by default (this is configural, not casual).

When the compiler fails, the offending node(s) get an `errored` border + an inline message in the inspector explaining the compile error. The user can revert with `Cmd+Z` per-node.

---

## 4. Run modes

The RunControlBar exposes three runs:

| Run | What it does | Visual treatment |
|---|---|---|
| **Run Paper** | Live data, simulated execution. Default before going live. | `bid.500/15%` button background |
| **Run Live** | Real money. The `intent="primary"` button. Confirmation dialog. | `accent.500` solid, larger than other buttons, modal confirm before activating |
| **Run Backtest** | Historical, configurable date range and starting equity. | `neutral.500` solid; opens a modal with date/equity inputs, then runs as a separate Backtest record |

Only one run mode can be active at a time per profile. When a profile is `live`, the canvas is *visually live*: nodes show running state, edges have flowing dots, the chrome top-bar shows `◉ live`.

---

## 5. Live overlay

When live, every node displays:
- a faint "running" border in its agent identity color,
- footer with `last latency · qps over 1m`,
- output port pulses on each emission.

Edges show flowing dots animated along the curve. Inactive branches dim to 30%.

The user can keep editing other parts of the canvas while live, with one rule: *changes don't take effect until next save+compile*. The compile re-deploys the running profile, which is announced via a banner ("Pipeline updated. New rules active in 2s.").

---

## 6. Templates

A "New profile" action opens a chooser:
- **Blank** — empty canvas
- **Conservative momentum** — pre-populated with ingestion → ta_agent (RSI+MACD) → strategy_eval → risk_check → execution
- **Multi-agent debate** — ingestion → 4 parallel agents → debate → strategy_eval → execution
- **Regime-aware mean reversion** — uses regime_hmm to gate strategy_eval
- **Backtesting only** — historical → ta_agent → strategy_eval → paper sink

These are starting points, not finished profiles. Each template includes a comment-card on the canvas explaining the pattern.

---

## 7. Comparison view

The user can open a "compare profiles" overlay (`Cmd+\\`) that splits the canvas vertically: left half shows current profile, right half shows another profile. Edges and node positions are diffed; new nodes highlighted `bid.500`, removed `ask.500`, modified configuration `warn.500`. This is the "design review" surface for profile changes.

---

## 8. Keyboard map

| Key | Action |
|---|---|
| `Space + drag` | Pan canvas |
| `Scroll` | Zoom |
| `Cmd+0` | Fit to viewport |
| `Cmd+1` | 100% zoom |
| `Cmd+S` | Save (compile) |
| `Cmd+Z` / `Cmd+Shift+Z` | Undo / redo (per-action) |
| `Cmd+D` | Duplicate selected nodes |
| `Cmd+G` | Group selected |
| `Cmd+Shift+L` | Auto-layout |
| `Cmd+\\` | Compare profiles |
| `Delete` | Remove selected |
| `R` | Run (cycles paper → live → backtest with confirmation) |

---

## 9. Empty states

| Region | Empty state |
|---|---|
| Empty canvas (new profile) | Centered card: "Start with a template or drag a node from the palette to begin." [browse templates] |
| No upstream connection on a node | Inspector shows "No upstream connected. This node won't receive data." |
| No downstream consumer | Inspector shows "No downstream consumer. Output will be discarded — connect to strategy_eval, logger, or another sink." |

---

## 10. Inspirational note (for the harness)

This canvas is *not* a generic n8n clone. It is a **trading-domain editor**. Specifically:
- Node kinds are fixed by the trading semantics; users cannot define arbitrary code nodes here (those go in code mode — out of scope for v1).
- Edge semantics carry types (signal, decision, execution) that affect what's allowable. The compiler enforces type-safety; the canvas should preview type errors visually before save.
- The canvas inherits the dark, restrained Praxis design language. **It should not look like Figma**. It should look like the bridge of the research vessel from `01-design-philosophy.md` §4.

If the harness produces a Canvas surface that looks bright, playful, or generically "creative-tool," that is a regression.
