# Canvas Components

The Pipeline Canvas is the *most distinctive* surface of Praxis. It's where the user composes trading profiles. Visual conventions borrow from n8n / Langflow / Figma, with departures noted because we're rendering trading semantics, not generic workflows.

> **Authority note (per CLAUDE.md §2C and Philosophy P4):** the canvas is the source of truth for `trading_profiles.pipeline_config`. Saving the canvas atomically updates `strategy_rules` via `pipeline_compiler`. Therefore the canvas is *not* a visualization; it is the editor.

---

### Node
**Used on:** Pipeline Canvas

**Anatomy:**
```
┌───────────────────────────────────────┐
│ ┌─[port-in]                          │   ← input ports (top edge)
│                                        │
│  ⊡  ta_agent                  ⓘ ⋮     │   ← icon + title + info/menu
│  ─────────────────────────────────    │
│   in: candles 1m × 240                 │   ← input summary
│   out: signal {long|short|hold}        │   ← output summary
│   ─────────────────────                │
│   running · 23ms last · 1.2k qps       │   ← live stats footer
│                              [port-out]│   ← output ports (bottom edge)
└───────────────────────────────────────┘
```

Each node is a card, ~220×120 minimum. Header icon comes from the agent identity (or generic gear for utility nodes). Title is the agent / step name. Info button opens an inspector drawer. Ports along edges (top = inputs, bottom = outputs by default; left/right for branching).

**States:**
- `idle` — neutral border, dim footer text
- `running` — live: agent identity color border, footer pulses faintly with `last latency` updating
- `paused` — desaturated, "paused" badge in header
- `errored` — `ask.500` border, error ring + last error in footer
- `selected` — `accent.500` 2px border + drop shadow `--shadow-md`
- `executing-now` — momentary 180ms `accent.500/30%` glow on entry/exit, marks the moment data flowed through

**Tokens:** card bg `--bg-panel`, headers `scale.label`, footer `scale.caption`, agent identity colors for running borders, accent for selection.

**Variants:**
- `kind`: `agent` (uses agent identity), `data-source` (e.g., ingestion → uses neutral.400 border), `decision` (strategy_eval → uses accent), `sink` (execution → uses bid/ask split icon), `transform` (utility — no identity color)
- `size`: `small` (icon + title only), `medium` (default, with summaries), `large` (with embedded mini-chart of recent activity)
- `embeddable` — when shown on Hot Trading as "what's running," nodes shrink to small variant in a horizontal strip

**Accessibility:** each node is keyboard-focusable with arrow keys for navigation between adjacent nodes (graph traversal); `Enter` opens the inspector; `Delete` removes; `Cmd+D` duplicates.

**Don't:**
- Use a different shape for different node kinds (rectangles vs hexagons vs ellipses) — that's a Visio antipattern. All nodes are rectangles; differentiate via icon, color accent, and content.
- Show full configuration on the node itself. Configuration lives in the inspector drawer. Nodes show only what helps the user *read the flow*.
- Pulse running nodes loudly. The pulse is a soft 0.06 opacity oscillation — present but not demanding.

**Reference:** n8n nodes (general structure), Langflow (LLM-aware nodes), Figma's component variants (visual language for selection).

---

### Edge (wire)
**Used on:** Pipeline Canvas

**Anatomy:** Bezier curve from output port → input port. 1.5px stroke, color depends on source kind:
- agent edges → source agent's identity color, 30% saturation
- data flow → `--color-neutral-500`
- decision flow (entering strategy_eval or execution) → `--color-accent-400`

When data is actively flowing through this edge (in live mode), a small dot animates along the curve at `--duration-ease`. In paused mode, the dot is static at midpoint.

**States:**
- `default` — as above
- `hover` — stroke 2px, slight glow
- `selected` — `accent.500` 2.5px stroke, dot color matches
- `errored` — `ask.500` stroke, dot replaced with ✗
- `inactive-branch` — when a conditional has selected a different branch, the inactive edge dims to 30% opacity

**Tokens:** stroke colors as above; dot animation `--duration-ease ease-in-out infinite`.

**Don't:**
- Render right-angle (orthogonal) edges. Bezier curves are easier to follow on a graph this size and signal "this is signal flow," not "this is a circuit diagram."
- Auto-route through other nodes. Edges go directly source → target; if it's ugly, the layout is wrong, not the edge.

**Reference:** Figma component connection lines, n8n edges, Excalidraw arrows.

---

### NodePalette
**Used on:** Pipeline Canvas (left rail when canvas is active)

**Anatomy:** searchable categorized list of node types. Top: search input. Below: collapsible categories.

```
┌── Search nodes ──── Cmd+/ ────────────┐
│ [ search input                       ] │
├────────────────────────────────────────┤
│ ▾ AGENTS                                │
│   ⊡ ta_agent                            │
│   ⊡ regime_hmm                          │
│   ⊡ sentiment                           │
│   ⊡ slm_inference                       │
│   ⊡ debate                              │
│ ▾ DATA SOURCES                          │
│   ⊡ ingestion (market data)             │
│   ⊡ archived candles                    │
│ ▾ TRANSFORMS                            │
│   ⊡ ta_indicator (sma/ema/rsi/…)        │
│   ⊡ feature_engineer                    │
│ ▾ DECISIONS                             │
│   ⊡ strategy_eval                       │
│   ⊡ risk_check                          │
│ ▾ SINKS                                 │
│   ⊡ execution (live)                    │
│   ⊡ paper                               │
│   ⊡ logger                              │
└────────────────────────────────────────┘
```

Drag to canvas to instantiate. Click to read description in popover.

**Don't:** allow ordering/reordering. Categories and within-category order are fixed by the node registry — the palette is a *map of capabilities*, not a personalized list.

**Reference:** Langflow component palette, Figma assets panel.

---

### MiniMap
**Used on:** Pipeline Canvas (bottom-right)

**Anatomy:** small (160×120) representation of the entire canvas, with a draggable viewport rectangle showing what's currently visible. Nodes shown as filled rects in their semantic color (or running/errored hue).

**States:**
- `default` — visible
- `collapsed` — collapses to a 24×24 chevron in the bottom-right; click to re-expand
- `pulse-running-far` — when a node off-screen is `running` or `errored`, its position on the minimap pulses to draw attention back

**Don't:** make the minimap interactive beyond viewport drag. Clicking nodes on the minimap is a feature trap — users misclick and lose context.

**Reference:** Figma minimap, Excalidraw minimap.

---

### NodeInspector
**Used on:** Pipeline Canvas (right drawer when a node is selected)

**Anatomy:** drawer 380px wide, organized in collapsible sections:
1. **Header** — node title (editable), kind, "running"/"paused" toggle
2. **Inputs** — declared input ports + their current upstream
3. **Configuration** — typed form for the node's parameters; uses primitives (Input, Select, Toggle)
4. **Outputs** — declared output ports + their downstream consumers
5. **Live activity** — small chart of last 100 emissions; `[trace ▸]` link to Observatory
6. **Tests** — per-node sample-input runner, with diff against last result (for transform/decision nodes)

**Tokens:** drawer bg `--bg-panel`, sections separated by `--border-subtle`. Form controls use primitive specs verbatim.

**Variants:** different node kinds expose different configuration sections. The inspector shape is consistent; the *content* of section 3 varies.

**Don't:** render the inspector as a modal. It's a drawer — the user must be able to keep canvas in view while editing. Modals interrupt the editing flow.

**Reference:** Figma right panel, Linear issue detail drawer.

---

### RunControlBar
**Used on:** Pipeline Canvas (top of canvas surface)

**Anatomy:** horizontal bar at the top of the canvas viewport.

```
┌────────────────────────────────────────────────────────────────┐
│  Aggressive-v3   ▾    │  ▶ run paper   ▶ run live   ▶ backtest │
│  saved 3m ago    ◯    │                                         │
└────────────────────────────────────────────────────────────────┘
```

Left: profile selector + dirty/saved indicator. Right: three big run buttons. Run-live is the only one with `intent="primary"` color treatment, and it requires confirmation when clicked.

**States:**
- profile `dirty` — orange dot in saved indicator, "save" button appears
- run `paper-active` — paper button in `bid.500/15%` bg + `bid.300` text
- run `live-active` — live button in `accent.500` solid (the "this is real money" color)
- run `backtesting-active` — modal-like overlay on canvas with progress + cancel

**Don't:** put run-live and run-paper in the same visual style. Different colors, different sizes (live is larger), different confirmation paths. The user should *never* be able to mistake one for the other.

**Reference:** Figma's "Play" prototype button, Replit's run/deploy buttons.
