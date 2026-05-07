# Stitch Prompt — Pipeline Canvas Surface

## VIBE

Design a node-based editor that feels like the dashboard of a research vessel — controls everywhere, dim instrumentation, every wire labeled. Like n8n had a child with Figma and was raised in a Linear-aesthetic household. Composing trading pipelines, not generic workflows; the nodes know they're trafficking in real money. Calm, precise, and obviously NOT a marketing-template "creative tool." The user feels like an engineer drafting a circuit, not a no-code dabbler.

## DETAILED PROMPT

Generate a desktop node-based editor UI named "Pipeline Canvas" for the Praxis trading platform. Viewport 1440×900px.

**Background, typography, color rules:** identical to Hot Trading prompt. Dark #0b0b0d canvas. Inter font. Same neutral/bid/ask/accent/agent palette.

**Layout — three columns:**

1. **Far-left rail** (56px, six-icon stack; the ⊕ plus-in-circle icon highlighted with indigo bar)

2. **Node Palette column** — 240px wide. Top: a search input "Search nodes ⌘/" placeholder. Below, a vertical list of collapsible categories with a "▾" chevron each:
   - **AGENTS** (expanded): six rows each with a small abstract glyph + name (ta_agent, regime_hmm, sentiment, slm_inference, debate, analyst)
   - **DATA SOURCES** (expanded): "ingestion (market data)", "archived candles"
   - **TRANSFORMS** (collapsed): chevron right
   - **DECISIONS** (collapsed): chevron right
   - **SINKS** (collapsed): chevron right
   - Each item is draggable (cursor: grab)

3. **Center: the canvas** — flexible width. The canvas has a faint dotted grid background (every 12px, dot color #18181b, very subtle).

   **Top bar of the canvas (RunControlBar):** Profile selector "Aggressive-v3 ▾" on left with "saved 3m ago ◯" indicator (small check icon in muted gray). Right side: three buttons: "▶ Run paper" (medium size, ghost with bid-tinted hover), "▶ Run live" (LARGE, indigo solid, primary intent), "▶ Run backtest" (medium, neutral solid).

   **The canvas content** — a directed acyclic graph of nodes connected by Bezier curve wires. Show this exact pipeline:
   - Top: a single "ingestion" node (kind: data-source, neutral border, glyph: stream-lines)
   - From ingestion, 4 wires fan out to FOUR agent nodes arranged horizontally:
     - "ta_agent" (blue ring border, glyph: bar-chart segments)
     - "regime_hmm" (violet ring, three connected nodes glyph)
     - "sentiment" (pink ring, wave glyph)
     - "slm_inference" (teal ring, brackets glyph)
   - All four agents wire down to a "debate" node (orange ring, three radiating lines glyph). The debate node is slightly larger/wider than agents.
   - Debate wires to "strategy_eval" (decision kind, indigo accent, glyph: gear)
   - strategy_eval wires to "risk_check" (decision kind, indigo accent, glyph: shield)
   - risk_check wires to "execution" (sink kind, neutral with bid+ask split icon)

   **Each node**: card with thin border (1.5px), rounded 6px corners, 220×120px sized. Internal layout: top section with a small icon glyph in a 24×24 box on the left + node title in 13px medium + a "ⓘ" info button + "⋮" menu button on the right. Then a thin horizontal divider. Then "in: candles 1m × 240" and "out: signal {long|short|hold}" labels in 11px caption muted. Bottom footer: "running · 23ms last · 1.2k qps" in even smaller caption text.

   **One node should be SELECTED** — give "ta_agent" a 2px indigo border + subtle drop shadow.
   **One node should be in error state** — give "sentiment" a 2px red border + a small "✗" badge in the top-right.
   **The "execution" node** has a bid-emerald + ask-red split chevron icon to suggest it routes orders.

   **Wires (edges)**: thin 1.5px Bezier curves. Color depends on source: agent edges use a desaturated tint of the source agent's identity color (30% saturation). Decision edges (going INTO strategy_eval and risk_check) are indigo accent. Show small animated dots at the midpoint of two of the wires (active flow).

   **Inactive branch dimming**: NONE in this layout — all branches active.

   **Bottom-right corner of the canvas**: a 160×120px MINI-MAP showing a tiny representation of the entire graph — small filled rectangles in their semantic colors connected by thin lines, with a subtle viewport rectangle indicating the current view.

4. **Right: Node Inspector panel** — 380px wide. Open because "ta_agent" is selected. Sections from top:
   - "Header": title input "ta_agent", small kind badge "agent", a "running" toggle (ON, indigo)
   - "Inputs": list of 1 connected input "← from ingestion (candles)"
   - "Configuration": form fields specific to TA — "Indicator(s): RSI ✓ MACD ✓ EMA20 ✓", "Lookback: 240", "Confluence threshold: 3/7" (slider), "Confidence floor: 0.55" (number input)
   - "Outputs": list "→ to debate", "→ to strategy_eval"
   - "Live activity": a small sparkline showing emissions per minute over last hour, plus "[trace ▸]" link
   - "Tests": collapsible section with a "Run with sample input ▸" button

**Visual character:**
- Looks like a flight planning tool, not Canva
- All nodes feel grounded, weighted; no floating-card gimmicks
- The grid is subtle — present but not loud
- Wires curve gracefully, don't right-angle
- Dim and serious; one indigo accent runs through (selection, run-live button, decision edges, decision nodes)

## REFERENCE NOTES

Priority reference uploads:
1. `08-reference-library/images/08-n8n-canvas.png` — node anatomy, edges, palette
2. `08-reference-library/images/09-langflow-canvas.png` — LLM-aware node patterns
3. `08-reference-library/images/03-linear-app.png` — the typographic restraint
4. `08-reference-library/images/10-figma-component-vars.png` — selection/inspector patterns

## ANTI-PROMPT

```
DO NOT generate:
  - colorful no-code-tool aesthetics (Zapier, Make.com, Bubble)
  - 3D node icons or shadows
  - blue rainbow color palette
  - emoji-heavy node types
  - overly large or floating cards
  - right-angle/orthogonal edges
  - a lighter-than-canvas grid (the grid should be SUBTLE)
  - generic admin "create new" empty-state illustrations
```
