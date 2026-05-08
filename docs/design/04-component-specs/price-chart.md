# PriceChart

The OHLC + volume chart. Used on Hot Trading (primary) and Backtesting (replay). Distinct from `Chart` (line/area/bar XY for COOL-mode analytics) because OHLC has its own primitive concerns: wicks, gap rules, live-tick flash, time-axis behavior at the millisecond grain, and a volume sub-pane that lives *with* the candles, not next to them. Specifying both as one component would force compromises in either direction — see `chart.md` "What's intentionally not in this spec".

> **Implementation engine.** PriceChart is a thin Praxis-themed wrapper around [TradingView Lightweight Charts](https://www.tradingview.com/lightweight-charts/) (`lightweight-charts` on npm; already in `frontend/package.json`). Their license covers our use. The wrapper is custom — the timeframe tabs and drawing tools are Praxis components, not TradingView's shipping toolbar. Theming flows through `applyOptions` reading `getComputedStyle(document.documentElement)` so token changes (mode swaps, theme tweaks) propagate without rerunning the wrapper.
>
> **Hand-roll vs library trade-off.** Chart was hand-rolled SVG because XY analytics fit a small, dependency-free abstraction. PriceChart isn't that — accurate OHLC time-axis, zoom/pan, crosshair, and pixel-snapped wick rendering are tens of thousand lines of work to do well. The library is small (~75 KB gz), token-themable, and the spec already prescribed it.

---

### PriceChart
**Used on:** Hot Trading (primary), Backtesting (replay). HOT-mode primary. Not for COOL/CALM.

**Anatomy:**
```
┌── header ─────────────────────────────────────────────────────────────────────┐
│  [1m][5m][15m][1h][4h][1d]    BTC-PERP ▾    ◯ live · last $42,318.27         │
├──────────────────────────────────────────────────────────────────────────────┤
│  ┌──┐                                                                          │
│  │  │   ← drawing tools strip (left, inside chart) — Pending v2                │
│  │ ✎│       pencil, line, fibonacci, eraser                                    │
│  │  │                                                                          │
│  │↕ │   candles (with wicks, color = up/down)                                  │
│  │  │                                                                          │
│  └──┘                                                                          │
│  volume histogram (thin strip pinned to bottom of price pane)                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │   depth chart (optional, when withDepthChart=true)                       │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

Subparts:
- **Header** — timeframe tab strip (left), symbol selector (center), status pills (right: live | replay | stale | last-price). The header is rendered by the wrapper, not the library.
- **Plot area** — candlesticks rendered by `lightweight-charts`. Up candles use `--color-bid-500`; down candles `--color-ask-500`; wick + body match. Background is `--bg-panel`.
- **Volume sub-pane** — histogram pinned to the bottom 18% of the price pane (using lightweight-charts' `priceScaleId='volume'` overlay — not a separate pane). Bars take their candle's tone at 50% saturation.
- **Crosshair tooltip** — vertical + horizontal hairline; readout in the header strip on hover (price, OHLC, volume, time).
- **Drawing tools strip** — left-edge inside the plot area. v1 surface as Pending; v2 implementation tracked separately.
- **Optional DepthChart strip** — appears below the price pane when `withDepthChart` is set; uses the existing `DepthChart` component.

---

**States:**
- `default` — series rendered, time-axis tracking caller's data.
- `live` — most-recent candle updates in place via `series.update()`. The body of the in-progress candle flashes `bid.tick-flash` (up) or `ask.tick-flash` (down) for `--duration-tick` on each tick, then settles to its tone.
- `replay` — playback mode for Backtesting. Drawing tools hidden; symbol selector frozen; instead a playback control strip (play/pause/scrub) is rendered in the header slot. Crosshair follows the replay cursor.
- `loading` — header renders, plot area shows a skeleton bar across the y-mid + a centered `--fg-muted` "Loading candles…" label.
- `error` — header renders, plot area shows a centered `--color-ask-500` caption + last successful render dimmed underneath if available.
- `empty` — plot area centered `--fg-muted` caption "No candles for this range." (used when range/timeframe combo returns nothing).
- `stale` — top-right of header shows a `warn.500` "stale Xs" pill when ticks haven't arrived for ≥10 seconds while in `live` mode. The chart does not re-color candles; the staleness lives only in the chrome.

---

**Tokens:**
- Background plot: `--bg-panel`. Header: `--bg-panel`. Border: `--border-subtle`.
- Up candle: `--color-bid-500`. Down candle: `--color-ask-500`. Wicks match the body (no separate wick color).
- Volume bars: `--color-bid-500` / `--color-ask-500` at 50% saturation (`color-mix(in oklch, … 50%, transparent)`).
- Crosshair: `--color-neutral-400` dashed 0.5px.
- Price-scale labels: `scale.caption` (11px tabular), `--fg-muted`.
- Time-scale labels: `scale.caption`, `--fg-muted`.
- Timeframe tab: `scale.label` (12px); active tab uses `--fg` + bottom border `--color-accent-500`.
- Status pills: existing `Pill` primitive — `intent="bid"` for live, `intent="warn"` for stale, `intent="neutral"` for replay.
- Tick-flash: `bid.tick-flash` / `ask.tick-flash` for `--duration-tick`.
- Motion: tick updates snap (no tween); zoom/pan use the library's defaults (already snappy).

---

**Variants:**
- `mode`: `live` (default — appends + updates last candle) | `replay` (Backtesting playback). Mode is data-driven; the wrapper only renders the right chrome.
- `withVolume`: `true` (default) | `false`. When false, the volume sub-pane is suppressed.
- `withDrawingTools`: `true` (default in `live` mode) | `false`. v1: surface as Pending; v2: actual tools.
- `withDepthChart`: `false` (default) | `true`. Adds a DepthChart strip below.
- `density`: `compact` (300h plot, 9-tick price scale) / `standard` (420h, 11-tick) / `comfortable` (560h, 13-tick). HOT typically uses `standard`; Backtesting replay uses `comfortable`.
- `timeframe`: `'1m' | '5m' | '15m' | '1h' | '4h' | '1d'`. The component renders tabs but doesn't fetch candles itself — caller swaps the `candles` prop on tab change. (Caller-owned data fetching keeps the component dumb.)

---

**Accessibility:**
- The wrapper is `role="region"` with `aria-label` `${symbol} candle chart, ${timeframe}`. The library canvas is `aria-hidden`.
- Timeframe tabs are real buttons in a `role="tablist"`; arrow keys move between them; Enter activates.
- Status pills are inert (decorative); their content is read only by hovering.
- Keyboard chart navigation (left/right step a candle) is **deferred** — pending lightweight-charts' first-class keyboard API. Surface as a Pending tag in the wrapper. (The spec'd `Chart` primitive has full keyboard support; see `chart.md`.)
- Crosshair motion announcements via live region: deferred until keyboard nav lands.

---

**Don't:**
- Embed the full TradingView hosted widget. It's branded, has features we don't want, and breaks our token system. Use `lightweight-charts` (the unbranded SDK).
- Create a new candle series on every prop update. Use `series.setData()` for full replacements (timeframe change, range change) and `series.update()` for in-place tick updates.
- Render multi-pane indicator panels by default. Volume pinned to the bottom of the price pane is allowed (it's an overlay, not a separate pane); RSI/MACD/etc. are out of scope for v1.
- Color candles by anything other than open-vs-close. The eye expects up=green/down=red (or in our palette, bid/ask) and breaking that hurts read speed.
- Animate tick updates. Snap. Backtesting replay scrubbing should also snap to the cursor's candle.
- Theme by hard-coded hex. All colors flow from token CSS vars via `applyOptions`. If you find yourself reaching for `#22c55e`, you're wrong.

---

**Reference:**
- `chart.md` — sets the SVG-render and tone-discipline pattern we deliberately diverge from for OHLC.
- `trading-specific.md` §DepthChart — composes alongside PriceChart when `withDepthChart` is set.
- `trading-specific.md` §TapeRow + §OrderBook — share the `tick-flash` motion pattern.
- TradingView Lightweight Charts examples — for the candle / volume rendering and time-axis ergonomics.
- Hyperliquid chart presentation — header layout (timeframe tabs + symbol + status pills row) and overall density.
- Bookmap — for the CVD strip / volume reading we're not building yet but should leave room for.

---

## What's intentionally not in this spec (deferred to v2)

1. **Drawing tools** — pencil / line / fibonacci / eraser. Surface as `withDrawingTools` Pending tag in v1; spec the actual tool affordances when Hot Trading (6.5) starts using them.
2. **Multi-pane indicators** — RSI / MACD / Bollinger Bands sub-panes. Out of scope for HOT v1; revisit when the strategy editor needs visual confirmation of indicators.
3. **Replay playback controls** — play / pause / scrub strip. v1 ships `mode="replay"` as a state hook; the actual control strip lands when Backtesting replay (post-6.5) needs it.
4. **Range selection (brush)** — drag a window over the time axis to drill in. Phase 6.5 will reveal whether this lives here or in a wrapping component.
5. **Keyboard candle navigation** — left/right steps a candle, with crosshair tracking. Deferred until lightweight-charts ships first-class keyboard support; for now the time scale is mouse-only.

When any of these come up, extend this file rather than scattering ad-hoc behavior across surface code.

---

## Composition tier

PriceChart is **trading-specific**. It composes primitives + data-display (Pill, StatusDot, Tag) + optionally `DepthChart`. It does not depend on agentic / canvas; cross-domain composition is a code smell.
