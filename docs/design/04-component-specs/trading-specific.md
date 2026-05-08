# Trading-Specific Components

These do not exist outside Praxis. Each is a distillation of conventions from Hyperliquid, dYdX, Kraken Pro, TradingView, with deliberate departures noted.

---

### OrderBook
**Used on:** Hot Trading

**Anatomy:**
```
┌── header [bid │ ask] ─────────┐
│ price    size    cum   │ same │
├──┴───────────────────┴─┴──────┤
│  ASKS (top, descending price) │
│  ↑ ↑ ↑                         │
│  ─────────── mid ─────────────  │   spread badge centered here
│  ↓ ↓ ↓                         │
│  BIDS (bottom, descending price)│
└───────────────────────────────┘
```

Two columns (split style) or stacked (single-column with mid in middle). Each row: `price | size | cumulative-size`. Background fill on each row goes left→right proportional to cumulative size at that level (subtle — `bid.500/12%` on bid rows, `ask.500/12%` on ask rows).

**States:**
- row `default` — text only, with cumulative-fill bg
- row `flash` — full row flashes `bid/ask.tick-flash` on update for `--duration-tick`
- row `large-print` — when size > 95th percentile of last 1m, row gets a left bar 2px in the side color
- mid `wide-spread` — when spread > X bps (configurable), spread badge turns `warn.500`

**Tokens:**
`--color-bid-{500,tick-flash}`, `--color-ask-{500,tick-flash}`, `--font-tabular`, `--size-12`, `--bg-canvas`, `--duration-tick`, `--space-1`

**Variants:**
- `style`: `split` (default) / `stacked`
- `aggregation`: tick-size dropdown (e.g., 0.1, 0.5, 1.0, 5.0)
- `depthRows`: 10 / 20 / 50 / unlimited (virtualized)
- `groupingHighlight`: when aggregation is coarser than native, a faint `accent.500/8%` bar marks the bucket

**Accessibility:** ARIA grid; arrow keys move between price levels. Each row's `aria-label` is "Bid 42318.27, size 0.5, cumulative 1.2."

**Don't:**
- Animate row insertion/removal — at typical update rates this becomes seizure-inducing. Snap, don't animate.
- Use any color outside the bid/ask families on data rows. Mid spread badge can use `neutral.300` or `warn.500`; that's it.
- Show >50 levels per side without virtualization — DOM cost will tank scroll perf.

**Reference:** Hyperliquid orderbook panel (the gold standard); Kraken Pro for size-bar fill; Bookmap for cumulative reading.

---

### DepthChart
**Used on:** Hot Trading (companion to OrderBook), Backtesting (replay)

**Anatomy:** XY chart, x = price, y = cumulative size. Two stepped curves: bid (left, descending from mid) and ask (right, ascending from mid), filled below. Mid marker as a vertical dotted line.

**Tokens:** strokes `--color-{bid,ask}-500`, fills `--color-{bid,ask}-500/15%`, mid `--color-neutral-400` dotted, no axes labels (data labels in tooltip on hover).

**Variants:**
- `range`: ±0.5%, ±1%, ±5% from mid, "fit to book"
- `linearVsLog`: y-axis scale toggle (default linear; log useful for fat-tail markets)

**Don't:** show grid lines. The shape of the depth curve *is* the information; gridlines compete with that shape.

**Reference:** TradingView depth chart, Binance Futures depth.

---

### TapeRow
**Used on:** Hot Trading (trade tape feed)

**Anatomy:** single row in a streaming list — `[time | side | size | price]`. Side: subtle bg tint (`bid.500/10%` or `ask.500/10%`). Time: `HH:MM:SS.mmm` in mono.

**Behavior:**
- New rows insert at top, shift down via translateY (snap, no animation in HOT)
- Auto-scroll lock: pinned to top by default; user scrolls down → lock disengages and a "▲ jump to live" pill appears at top

**Tokens:** as Table dense rows + `--font-mono` for time + side bg tints.

**Don't:** show side as just text "BUY"/"SELL" — color the row. The eye's parsing of color-coded direction is far faster than text.

**Reference:** Bloomberg time-and-sales window, Hyperliquid trades column, BookMap CVD strip.

---

### PnLBadge
**Used on:** Hot Trading (chrome + position rows), Risk Control, Backtesting

**Anatomy:** `[arrow ▲▼ | value | suffix?]` — value in `display-sm` for chrome, `body-dense` for inline use.

**Variants:**
- `mode`: `absolute` ($1,234.56), `pct` (+2.34%), `bps` (+45 bps), `r-multiple` (+1.2R for backtests)
- `size`: `inline` (matches surrounding type) / `prominent` (display-sm)
- `signed`: when true, always show `+` for positive
- `flash-on-change`: when value updates, flash bg in tick-flash for `--duration-tick`

**Tokens:** `--color-bid-500` (positive), `--color-ask-500` (negative), `--color-neutral-300` (zero / null), tabular numerics.

**Don't:** use a green/red square as a "status indicator" instead of an actual value when space allows showing both — the value is the data.

---

### RiskMeter
**Used on:** Risk Control (centerpiece), Hot Trading (compact)

**Anatomy:** horizontal segmented bar, 0–100% utilization of a risk budget (e.g., portfolio leverage vs max). Segments: green-zone (`bid.500`, 0–60%), amber-zone (`warn.500`, 60–85%), red-zone (`danger.500`, 85–100%). Current value as a needle/marker on the bar plus numeric readout.

**Variants:**
- `kind`: `leverage`, `portfolio-var`, `concentration`, `drawdown`, custom
- `compact`: 8px tall with no thresholds visible — only the needle moves through the gradient

**Tokens:** segment colors as above, threshold lines `--border-subtle`, needle `--fg-primary`, type `scale.body-dense` for value, `scale.caption` for threshold labels.

**States:**
- in green-zone: needle `--fg-primary`
- in amber-zone: needle `--color-warn-500`, soft pulse
- in red-zone: needle `--color-danger-500`, faster pulse, the entire surface chrome shows `🛡 armed-soft` until cleared

**Don't:** make the bar smooth-gradient (e.g., green → amber → red blend) — segment thresholds are decisions, not preferences. Show them as discrete steps with visible boundaries.

**Reference:** automotive tachometers (the segmented redline pattern), aviation HUDs.

---

### OrderEntryPanel
**Used on:** Hot Trading

**Anatomy:**
```
┌── tabs: [Limit] [Market] [Stop] [TWAP/Algo] ───────┐
│  Side: ◉ Buy  ○ Sell                                │
│  Size:        [   0.0   ] [25%][50%][75%][100%]     │
│  Price:       [ 42318.27 ]   ⓘ within 0.3% of mid   │
│  Leverage:    [ 5x ──●────── 100x ]                 │
│  Reduce-only? [ toggle ]   Post-only? [ toggle ]    │
├─────────────────────────────────────────────────────┤
│  Cost: 211.59 USDC   Margin used: 42.32 USDC        │
│  ┌─────────────────────────────────────────────┐    │
│  │       Buy 0.005 BTC-PERP @ 42318.27         │    │
│  └──────────────────[bid intent]────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Critical UX rule (per dYdX learnings):** every input must be reachable in ≤3 keystrokes from any other. Tab order must be: side → size → price → leverage → submit. The submit button is `bid.500` if buying, `ask.500` if selling — it adopts the *consequence* color, not the action.

**States:**
- `validating` — submit button shows spinner, label "validating…"
- `ok` — submit ready
- `risk-block` — submit disabled, `warn.500` banner above with reason ("would exceed max position")
- `kill-switch-armed` — submit disabled, banner `danger.500`, "kill switch armed — disarm at /risk to trade"

**Tokens:** primitives + bid/ask color + leverage slider with track in `--color-neutral-700` and fill stop in the side color.

**Variants:**
- `density`: compact/standard/comfortable like the rest
- `keyboard-only`: layout when focus is keyboard — shortcut hints visible

**Accessibility:** every action has a shortcut. `B` toggles side to Buy, `S` to Sell. `M` switches to Market tab. `Enter` submits when valid.

**Don't:**
- Use a single brand-color submit button regardless of side — defeats the purpose of the bid/ask color contract.
- Hide leverage behind "advanced" — leverage is a primary input, not advanced.
- Show "your order has been placed" toast — the order appears in the position/orders list with a flash; that's the confirmation.

**Reference:**
- Hyperliquid order entry (compactness)
- dYdX leverage slider
- Phantom in-wallet swap (large-button intent)

---

### PriceChart
**Used on:** Hot Trading (primary), Backtesting (replay)

OHLC + volume chart. Full spec lives in [`price-chart.md`](./price-chart.md) — split out because OHLC concerns (wicks, gap rules, live-tick flash, volume sub-pane, time-axis at the millisecond grain) diverge from the line/area/bar `Chart` primitive in `chart.md`.

PriceChart wraps [TradingView Lightweight Charts](https://www.tradingview.com/lightweight-charts/) (`lightweight-charts` on npm) with Praxis tokens applied via `applyOptions`. Timeframe tabs and drawing tools are Praxis-built (not TV's shipping toolbar). See `price-chart.md` for the deferred-to-v2 list (drawing tools, multi-pane indicators, replay playback strip, range selection brush, keyboard candle nav).

---

### PositionRow
**Used on:** Hot Trading, Risk Control

**Anatomy:** wide row in a positions table. Cols: `[symbol | side | size | entry | mark | unrealized | margin | leverage | actions]`. Actions: `[close 25/50/100%]`, `[edit stop]`, `[trace to canvas]`.

**States:**
- `default` — bg `bg.canvas`
- `hover` — actions reveal (else hidden); subtle bg `bg.row-hover`
- `near-liq` (margin within 10% of maintenance) — left bar `warn.500`, mark price flashes `warn.tick-flash`
- `liquidating` — left bar `danger.500`, row dimmed but not hidden
- `closed-just-now` — appears in closed-positions list with a 6s `bid.tick-flash` for the row, then settles

**Tokens:** Table tokens + bid/ask + warn/danger.

**Don't:** auto-confirm partial-close clicks. Even quick-close buttons should require a 2nd click within 2s as confirmation, with the button changing label "click again to confirm." This is the only modal-equivalent in Hot mode.

**Reference:** dYdX positions table, GMX position management.
