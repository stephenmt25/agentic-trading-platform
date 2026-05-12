# Chart

A general-purpose XY chart primitive for line, area, and bar visualizations. Sits alongside `Sparkline` in the data-display tier — Sparkline is shape-only and inline; Chart is full-blown with axes, gridlines, legend, and tooltip. Both share the same SVG-first, dependency-free implementation pattern.

This is the visualization workhorse for COOL-mode analytics surfaces (Backtesting, Observatory, Risk timelines). It is **not** the price/candle chart for HOT mode — that is `PriceChart` in `trading-specific.md` (deferred until Phase 6.5 reveals exact requirements). Specifying both as one component would force compromises in either direction.

---

### Chart
**Used on:** Backtesting (run detail, compare) — primary; Agent Observatory (score timelines), Risk Control (limit timelines), Profiles (recent activity beyond Sparkline) — secondary. **Not for HOT-mode price/candle charts** (see `PriceChart`, deferred).

**Anatomy:**
```
┌── header (optional) ────────────────────────────────────────┐
│ Equity Curve                          ◯ Run-A   ◯ Run-B    │  <- title + legend
├─────────────────────────────────────────────────────────────┤
│ 12.0k ┤                                       ╱─────         │
│       ┤                              ╱──────╱                │  <- y-axis ticks + line series
│ 10.5k ┼────────·──────·──────·──────·──────·──────·────     │  <- baseline (zero line / start)
│       ┤        ╲___╱                                        │
│  9.5k ┤                                                      │
│       └────·──────·──────·──────·──────·──────·──────────   │
│        Jan 1   Jan 15  Feb 1   Feb 15  Mar 1   Mar 15        │  <- x-axis ticks
│        ┌──────────────────────────────┐                       │
│        │ Mar 4  ·  Run-A 11,240  +12%  │  <- crosshair tooltip │
│        │         Run-B 10,890  +8.9%  │                       │
│        └──────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

Subparts:
- **Plot area** — the main rectangle. SVG. Strokes/fills are token-bound; never literal hex.
- **Axes** — left (y) and bottom (x). Auto-formatted ticks. Optional; for compact embeds (KeyValue cards) the chart can be axis-less and grow into "fat sparkline" territory.
- **Gridlines** — horizontal only by default (vertical reads as price-discipline noise per `Table` Don't). Stroke `border.subtle` at 0.5px.
- **Series** — one or more, each `line`, `area`, or `bar`.
- **Legend** — top-right. One row per series. Suppressed when series count = 1.
- **Crosshair tooltip** — vertical hairline + boxed value readout on hover/keyboard focus. Tabular figures, label/value pairs per visible series.
- **Empty/loading/error states** — see below.

**States:**
- `default` — series rendered at full opacity.
- `hover` — crosshair tracks pointer; nearest x-bucket highlights; non-hovered series dim to 50% (only when ≥2 series).
- `focus` (keyboard) — chart receives focus; left/right arrows step the crosshair across data points; `Esc` exits.
- `dimmed` — explicit prop to render at 60% opacity (used in compare view for non-baseline runs).
- `loading` — series stroke replaced by a pulsing skeleton path along the plot baseline; axes still render.
- `empty` — plot area shows a centered `fg.muted` caption "No data" + neutral baseline.
- `error` — plot area shows a centered `ask.500` caption + the last successful render dimmed underneath if available.

**Tokens:**
- Series stroke / fill (semantic mapping):
  - `bid` — `--color-bid-500` stroke, `--color-bid-500/12%` fill (area), `--color-bid-500` bar
  - `ask` — `--color-ask-500` stroke, `--color-ask-500/12%` fill, `--color-ask-500` bar
  - `accent` — `--color-accent-500` stroke, `--color-accent-500/12%` fill, `--color-accent-500` bar
  - `neutral` — `--color-neutral-300` stroke, `--color-neutral-700/40%` fill, `--color-neutral-400` bar
  - `auto` — sign-based: positive → `bid`, negative → `ask`, zero → `neutral`. Used for PnL bars and signed-magnitude charts.
- Axes / gridlines: `--border-subtle` (gridlines), `--fg-muted` (tick labels), `--fg-secondary` (axis titles when shown).
- Plot background: transparent — inherits from parent (`--bg-panel` or `--bg-canvas`).
- Crosshair: `--border-strong` 0.5px dashed; tooltip surface `--bg-raised`, border `--border-subtle`, shadow `--shadow-popover`, type `scale.body-dense` mono for values, `scale.caption` for labels.
- Type: tick labels at `scale.caption` (11px) tabular; legend label at `scale.label` (12px); title at `scale.body-dense` (13px).
- Motion: series cross-fade on data change uses `--duration-ease` (220ms) in COOL, instant in HOT (HOT shouldn't be using this primitive anyway). Crosshair tracking is `--duration-instant`.

**Variants:**

*Series shape:*
- `line` — single-pixel-precise stroke, optional `area` fill below. Stroke 1.25px (single series) / 1px (≥3 series).
- `area` — filled region between line and a baseline. Baseline = `zero`, `min`, or numeric. Used for drawdown overlays where the baseline is the prior peak.
- `bar` — categorical bars. Width derived from x-band width × `barInset` (default 0.6).

*Layout:*
- `axes`: `both` (default) / `x-only` / `y-only` / `none`
- `gridLines`: `horizontal` (default) / `none` / `both`
- `barLayout`: `grouped` / `stacked` (when multiple bar series)
- `xType`: `time` (date-based, auto-format ticks) / `numeric` / `categorical`
- `yScale`: `linear` (default) / `log` / `signed-symmetric` (centers zero — for PnL distributions)
- `density`: `compact` (160h, smaller type, fewer ticks) / `standard` (240h, default) / `comfortable` (320h, more breathing)

*Behaviors:*
- `tooltip`: `crosshair` (default) / `nearest` / `none`
- `legend`: `auto` (shown when ≥2 series) / `always` / `never`
- `downsample`: integer `N` — render at most N x-positions; downsamples by min/max bucketing. Required for any series with > 2,000 points.
- `dimmed`: boolean — render at 60% opacity (compare view non-baseline).

**Accessibility:**
- Outer `<svg>` carries `role="img"` and an `aria-label` summarizing series and value range (e.g., "Equity curve from 10,000 USDC to 11,430 USDC over 113 days").
- Optional `tableFallback` prop renders a visually-hidden `<table>` of the data after the SVG so screen readers can read every point. Required on the equity-curve usage in Backtesting; optional on regime/distribution charts.
- Chart container is keyboard-focusable (`tabIndex=0`). When focused: left/right arrow steps the crosshair across x-buckets; `Home`/`End` jump to first/last; `Esc` blurs.
- Hover tooltip text duplicates onto a polite live region when crosshair moves under keyboard control (so SR users hear values).
- Color is never the only encoding. `auto` tone bars use color for sign + sign symbol prefix in tooltip ("+" / "−"). Series legend pairs color swatch with label.

**Don't:**
- Use this for OHLC candlesticks. Candles need wick handling, gap rules, and live-tick flash mechanics that this primitive deliberately doesn't have. That's `PriceChart` (deferred).
- Pull in `recharts`, `victory`, `chart.js`, etc. SVG path generation matches the `Sparkline` pattern — bundle stays small, theming stays token-bound. `d3-shape` (line/area path generators only) is acceptable if the inline math becomes meaningful complexity; avoid the rest of d3.
- Use chromatic series colors outside the `bid` / `ask` / `accent` / `neutral` palette. Agent identities alias to `accent` (per ADR-012); compare-view runs differentiate by stroke style and label, not hue. If you find yourself reaching for purple/orange/teal, you're violating the 3-color discipline.
- Render axes labels in HOT mode. If you need a chart in HOT mode, render axis-less and assume the surrounding KeyValue carries values. (HOT-mode price charts: see `PriceChart`.)
- Animate on data updates faster than `--duration-ease`. Backtest-replay scrubbing and live tick updates should snap, not tween.
- Show >2,000 raw points without `downsample`. The DOM cost is real and the visual gain is zero past the screen's pixel width.
- Stack a histogram on top of a line series. Mixed series shapes are allowed (line + area is fine; bar + line is allowed for "bars with rolling-average overlay") but bar + bar overlays are reserved for `barLayout="stacked"`.

**Reference:**
- `Sparkline` (this folder) — sets the SVG-render and trend-tone pattern that Chart extends.
- TradingView Lightweight Charts — for the line/area ergonomics; not for the candle implementation.
- Linear Insights timeline — header + legend treatment, axis discreetness.
- Stripe Dashboard graphs — type discipline and crosshair tooltip restraint.
- d3-shape — `line()` and `area()` generators (small, ESM-friendly subset of d3) are fair game.

---

## What's intentionally not in this spec

This is the first cut of the Chart primitive — sized for what Backtesting (6.2b/c), Observatory (6.4), and Risk Control (6.6) need. Three things are deferred:

1. **OHLC / candlesticks → `PriceChart` in `trading-specific.md`** — different problem (gap rules, wicks, live-tick flash, volume sub-pane, range selection at the millisecond grain). Phase 6.5 (Hot Trading) will reveal whether to build this on top of TradingView Lightweight Charts or hand-roll. Don't try to extend Chart there; the abstractions diverge.
2. **Heatmaps / 2D density (rule-fingerprint heatmaps, agent agreement matrices)** — needs `<rect>` grids with continuous color scales; treat as a separate `Heatmap` component when the surface that needs it (Trade Forensics) is repainted.
3. **Brush / range-selection interaction** — when a surface needs to scrub a window over a long series (e.g., picking a date range from the equity curve to drill into specific trades), spec a `range` prop in a follow-up. The 6.2b/c usages don't need it yet.

When any of these come up, extend this file rather than scattering ad-hoc charts across surface code.

---

## Composition tier

Chart is **data-display**. It composes only primitives (no upward dependencies). Trading-specific charts (`DepthChart`, `PriceChart`) and the canvas's MiniMap may compose Chart, never the reverse.
