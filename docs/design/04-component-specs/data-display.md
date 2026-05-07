# Data Display

Components that render data without action affordances. The bread-and-butter of every Praxis screen.

---

### Table (dense)
**Used on:** all surfaces — the workhorse component

**Anatomy:**
```
┌── header row (sticky) ────────────────────────────────────────┐
│  Col1 ↕   Col2 ↕   Col3 ↕   Col4              ⋯ density tools  │
├───────────────────────────────────────────────────────────────┤
│  data row 1                                                    │
│  data row 2                                                    │
│  …                                                            │
└── footer (totals, paging, optional) ─────────────────────────┘
```

Header: 32px tall in `standard` density, sticky on scroll, has small caret-up/down for sortable columns. Data rows: 28h `standard`, 24h `compact`, 36h `comfortable`.

**States:**
- row `default` — bg `bg.canvas`
- row `hover` — bg `bg.row-hover` (only one row per moment)
- row `selected` — left bar 2px `accent.500` + bg `bg.row-hover` slightly lifted
- row `flash-bid` / `flash-ask` — `bid.tick-flash` / `ask.tick-flash` background, decay over `--duration-snap`
- row `error` — left bar 2px `ask.500`

**Tokens:** `--bg-{canvas,row-hover}`, `--border-subtle`, `--color-{accent,bid,ask}-500`, `--space-{1,2,3}`, `--font-tabular` (numeric cells), `--size-{12,13}` (compact/standard), `--duration-snap`, `--duration-tick`

**Variants:**
- `density`: compact / standard / comfortable
- `striping`: `none` (default) / `every-other` (only Calm mode)
- `gridLines`: `none` / `horizontal` / `both` — Hot mode default `horizontal` only; Calm mode `none`
- `selectable`: `none` / `single` / `multi`
- `groupBy`: optional column key → grouped rows with collapsible group header

**Accessibility:**
- Use semantic `<table>` with `<thead>`/`<tbody>`. ARIA grid only if you need cell-level keyboard navigation (Hot mode does).
- Sortable headers are buttons with `aria-sort`.
- For Hot mode, support arrow-key cell navigation; `Enter` opens row detail; `Space` selects.

**Don't:**
- Wrap text in cells in Hot/Cool mode — overflow with `ellipsis`, full value in tooltip. Wrapping breaks the eye's vertical scan.
- Use background color stripes in Hot mode — it competes with the price-tick flash.
- Nest tables inside tables — use grouped rows with indent instead.

**Reference:**
- Hyperliquid trade history & position table (density)
- Linear issue list (sort, group, density modes)
- TradingView screener (sortable columns, sparklines in cells)

---

### List
**Used on:** Cool/Calm surfaces — Observatory feeds, profile lists, settings

**Anatomy:** vertical stack of items; each item is a row with `[avatar/icon | content | meta | action?]`. Spacing between items: `--space-1` (compact) / `--space-2` (standard) / `--space-3` (comfortable).

**Variants:**
- `dividers`: `none` / `between` (1px `--border-subtle`)
- `interactive`: rows act as buttons (hover, click) or as static
- `dense`: drops avatar, condenses to 1-line + meta

**Don't:** mix interactive and non-interactive rows in the same list. Either all rows do something or none do.

**Reference:** Linear sidebar + main panel rows.

---

### KeyValue
**Used on:** Hot, Cool, Calm — settings, position details, agent state inspectors

**Anatomy:** `[label] [value]` pair, label on left at `fg.muted`, value on right at `fg.primary`. In dense layouts, labels right-aligned in a fixed-width column for vertical scanning.

**Variants:**
- `layout`: `inline` (single line) / `stacked` (label above value)
- `align`: in inline, value right-aligned by default
- `weight`: `value-emphasis` (default — value bold, label muted) / `equal` (both `medium`)

**Tokens:** `--fg-muted` for label, `--fg-primary` for value, type `scale.{label,body-dense}`.

**Don't:** mix inline and stacked KeyValues in the same group — pick one.

---

### Sparkline
**Used on:** Hot Trading (per-symbol mini-trend), Backtesting (per-run summary), Profiles (recent activity)

**Anatomy:** small inline chart, 60–120px wide, 16–24px tall, single line, no axes, no labels.

**Tokens:**
- positive trend: stroke `--color-bid-500`, fill `--color-bid-500/8%`
- negative trend: stroke `--color-ask-500`, fill `--color-ask-500/8%`
- neutral: stroke `--color-neutral-400`
- last-point dot at end (1.5px, same color as stroke)

**Variants:**
- `area`: filled area below line (default in Hot mode) vs line-only (Cool/Calm)
- `with-mid`: faint horizontal at the series midpoint

**Don't:** label the y-axis. The sparkline is shape-only. If precise values are needed, show them in an adjacent KeyValue or on hover.

**Reference:** Stripe dashboard sparklines, TradingView watchlist mini-charts.

---

### Pill
**Used on:** all surfaces — chrome status, surface header, filter chips

**Anatomy:** smaller than a button, larger than a tag, fully rounded (`--radius-full`). `[icon? | label]`. 24h fixed.

**Variants:**
- `static`: not interactive (e.g., `regime: choppy` in chrome)
- `clickable`: opens detail drawer/popover; on hover, ring 1px `--border-strong`
- `removable`: `+ x` icon — for filter chips

**Tokens:** intent colors as `subtle` style by default. Active filters use `accent.500/15%` bg + `accent.300` fg + ring.

---

### StatusDot
**Used on:** all surfaces — pills, lists, audit, avatars

**Anatomy:** 6/8/10px circle with optional 2px ring matching bg.

**Variants:**
- `state`: `live` (`bid.500`, optional pulse), `idle` (`neutral.400`), `warn` (`warn.500`), `error` (`ask.500`), `armed` (`danger.500`, pulse)
- `size`: 6/8/10
- `pulse`: boolean — adds 1.4s pulse for `live` and `armed`

**Tokens:** uses semantic colors directly. Pulse animation: scale 1→1.6, opacity 0.6→0, `--duration-slow` cycle, infinite.

**Don't:** pulse for `idle` or `error` — these states should be visually present but not demanding attention. Reserve pulse for "good current state" and "demands action."
