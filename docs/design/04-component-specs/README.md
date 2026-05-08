# Component Specs — Reading Guide

This folder defines every reusable building block in Praxis. Each component spec follows the same shape so the coding harness can parse them uniformly.

## Files in this folder

| File | What it covers |
|---|---|
| `primitives.md` | Button, Input, Select, Checkbox, Toggle, Tag/Badge, Kbd, Tooltip, Avatar |
| `data-display.md` | Table (dense), List, KeyValue, Sparkline, Pill, StatusDot |
| `chart.md` | Chart (line / area / bar XY chart for COOL-mode analytics; not OHLC) |
| `trading-specific.md` | OrderBook, DepthChart, TapeRow, PnLBadge, RiskMeter, OrderEntryPanel, PositionRow |
| `agentic.md` | AgentTrace, ReasoningStream, ToolCall, DebatePanel, ConfidenceBar, AgentAvatar |
| `canvas.md` | Node, Edge, NodePalette, MiniMap, NodeInspector, RunControlBar |

## Spec format

Every component is documented with these sections, in this order:

```
### ComponentName
**Used on:** which surfaces (HOT/COOL/CALM)
**Anatomy:** ASCII or prose breakdown of subparts
**States:** default, hover, focus, active, disabled, loading, error
**Tokens:** which design tokens it consumes (color, type, space, motion)
**Variants:** size, density, semantic role
**Accessibility:** keyboard, screen reader, touch target
**Don't:** common misuses to avoid
**Reference:** which inspiration source(s) this draws from
```

The harness should treat the **Tokens** line as the contract — if a generated component reaches for a color outside its declared token list, that's a regression.

## A note on mode-scoped tokens

Components reference **semantic aliases** (`--bg-panel`, `--bg-raised`, `--fg-primary`, `--fg-secondary`, `--fg-muted`, `--border-subtle`, `--border-strong`), not raw color tokens. The actual values these aliases resolve to are mode-dependent — set by a `data-mode="hot|cool|calm"` attribute on a parent element (typically the surface root).

This means the same component renders correctly in HOT, COOL, or CALM mode without conditional code: it asks for `--bg-panel`; the runtime resolves to the right neutral step for the active mode. See `03-design-tokens/tokens.css` lines 223–256 for the per-mode mappings.

If a component is *only* valid in one mode (e.g., `OrderEntryPanel` is HOT-only), document that in its `Used on` line.

## A note on component composition

The hierarchy is: **primitives → data-display → domain (trading | agentic | canvas)**.

- Primitives never import from data-display or domain.
- Data-display may compose primitives.
- Domain may compose primitives, data-display, or other domain components **within the same domain** (e.g., a trading-specific component may use other trading-specific components).
- Domain may **not** reach across domain boundaries (agentic shouldn't render trading-specific; trading shouldn't render canvas-specific).

Cross-domain composition is a code smell — flag and ask before implementing.
