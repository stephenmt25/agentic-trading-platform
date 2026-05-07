# Surface Spec — Backtesting & Analytics

**Mode:** COOL
**URL:** `/backtests` (list) / `/backtests/{run_id}` (detail) / `/backtests/compare?runs={a,b,c}`
**Backed by:** `backtesting`, `analyst`, `archiver`
**Frequency:** the user spends 5–15% of their session here (concentrated when iterating on a profile)
**Density:** medium — togglable per IA §5 (compact / standard / comfortable). Default is `standard`. Run-list page is a good candidate for `compact` when a user has many runs to scan.

---

## 1. Layout — Run List (`/backtests`)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ◀▶ 📊 Backtesting                                              [+ new backtest]  │
├──────────────────────────────────────────────────────────────────────────────────┤
│ filter: profile [v]  date range [v]  status [v]  ⌕ search                       │
├──────────────────────────────────────────────────────────────────────────────────┤
│  ☐ run-id     profile           range          ROI    sharpe  maxDD  status     │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  ☐ #9342    Aggressive-v3   2026-01..2026-04  +14.3% 1.84  -8.2%  ✓ done       │
│  ☐ #9341    Aggressive-v3   2025-10..2026-04  +27.1% 1.91  -11%   ✓ done       │
│  ☐ #9340    Conservative-v1 2025-10..2026-04  +6.4%  0.92  -3.1%  ✓ done       │
│  ☐ #9339    Aggressive-v2   2026-01..2026-04  -2.1%  0.18  -14%   ✓ done       │
│  ☐ #9338    Aggressive-v3   2026-01..2026-04   ──    ──    ──    ▣ running 64% │
│  …                                                                               │
├──────────────────────────────────────────────────────────────────────────────────┤
│  selected: 2 runs   [compare ▸]   [archive ▸]   [delete ▸]                      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

A dense Table at the heart of the surface. Selectable rows; selecting ≥2 enables the "compare" action. Each row shows headline metrics with PnLBadge for ROI, raw value for Sharpe and maxDD.

---

## 2. Layout — Run Detail (`/backtests/{run_id}`)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ◀▶ 📊 Backtests > #9342                              [view canvas as run]      │
│ Aggressive-v3 · 2026-01..2026-04 · 113 days · run 11m ago                       │
├──────────────────────────────────────────────────────────────────────────────────┤
│  ┌── HEADLINE ─────────────────────────────────────────────────────────────┐    │
│  │  ROI +14.3%   Sharpe 1.84   Sortino 2.42   maxDD -8.2%                  │    │
│  │  trades 247   win-rate 58%   avgR +0.42   profit-factor 1.71            │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  ┌── EQUITY CURVE ─────────────────────────────────────────────────────────┐    │
│  │  (line chart, equity vs time, drawdown overlay below)                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  ┌── TRADE DISTRIBUTION ─────────────┬── REGIME BREAKDOWN ──────────────┐       │
│  │  histogram of R-multiples         │  per-regime PnL                  │       │
│  │  long │█▍▎│ short │█▏│            │  trending +12%, choppy +1.4%, …  │       │
│  └────────────────────────────────────┴───────────────────────────────────┘       │
│                                                                                   │
│  ┌── TRADES TABLE (paginated) ──────────────────────────────────────────────┐    │
│  │  time      symbol  side  size   entry    exit    R   reason            │    │
│  │  …                                                                       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Sections:
1. **Headline** — KeyValue grid of headline metrics
2. **Equity curve** — line chart, with drawdown overlaid as a filled area below x-axis
3. **Trade distribution** — histogram of R-multiples, split long vs short
4. **Regime breakdown** — bar chart per regime (state from regime_hmm during the run)
5. **Trades table** — every trade, with link to canvas node that fired it
6. **(below the fold)** Per-agent attribution if the profile used agents — which agent's signals correlated with the best/worst trades

The "view canvas as run" button at top-right is critical: it opens the Pipeline Canvas in a *snapshot* mode showing exactly the canvas as it was at run time. This is non-negotiable — strategies evolve; backtest reproducibility requires snapshot view.

---

## 3. Layout — Compare (`/backtests/compare?runs=a,b,c`)

Side-by-side equity curves overlaid in distinct colors (using accent + neutral palette since these aren't agents). Headline metrics in a comparison KeyValue grid, with `Δ` columns showing differences from the first selected run as the baseline.

Below: trade-by-trade comparison for any trades that appear in multiple runs (same time, same symbol, different exits — e.g., when comparing two profiles on the same date range).

---

## 4. New backtest dialog

```
┌── New backtest ───────────────────────────────────┐
│  Profile:        [ Aggressive-v3            ▾ ]   │
│  Date range:     [ 2026-01-01 ] → [ 2026-04-30 ] │
│  Symbol(s):      [ BTC-PERP × ETH-PERP × +     ]  │
│  Starting equity:[ 10,000 USDC                ]   │
│  Slippage model: [ realistic-with-impact      ▾ ] │
│  Fees:           [ Hyperliquid-perp           ▾ ] │
│                                                    │
│  ┌── Advanced ─────────────────────────────────┐  │
│  │  Random seed:    [ 42                    ]  │  │
│  │  Walk-forward:   [ off                  ▾ ]  │  │
│  │  Multi-symbol weighting: [ equal       ▾ ]   │  │
│  └────────────────────────────────────────────┘   │
│                                                    │
│  [Cancel]                              [Run ▶]     │
└────────────────────────────────────────────────────┘
```

Modal — one of the few. Critical because misconfigured backtests are the #1 source of false confidence. Slippage model and fees are *required* selections, not defaults to a happy path.

---

## 5. Live behaviour

- A running backtest emits progress events (`progress`, `current_equity`, `trades_so_far`); the run row in the list shows a live progress indicator and current ROI.
- Once complete, the run becomes immutable. Any "rerun" creates a new run-id (no overwrite, ever — auditability).

---

## 6. Empty states

| Region | Empty state |
|---|---|
| No backtests yet | "No backtests yet. Backtests let you evaluate a profile against historical data without risking capital." [+ Run your first backtest] |
| Run failed to start | Row shows `✗ failed`; click to see diagnostic with link to logs |
| Compare view with one run | "Select 2 or more runs to compare." (offer to navigate back) |

---

## 7. Critical-path note

The "view canvas as run" feature requires the canvas snapshot to be archived with the run. The harness must enforce this — a backtest record without a canvas snapshot is not valid. This is part of P4 (canvas as source of truth).
