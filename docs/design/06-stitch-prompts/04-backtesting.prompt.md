# Stitch Prompt — Backtesting & Analytics Surface

## VIBE

Design a screen that feels like a research lab notebook: rigorous, considered, and full of charts that earn their pixels. Restrained typography (Stripe-API-docs energy), with the calm-but-dense sensibility of a quant's terminal. The screen should make hindsight bias visually expensive — every claim must be backed by a chart, every chart should be reproducible. This is the surface where the user evaluates whether their strategy actually works; it should feel like reviewing scientific evidence, not like a marketing deck.

## DETAILED PROMPT

Generate a desktop analytics UI named "Backtests Detail" for the Praxis trading platform, showing the result of a single backtest run. Viewport 1440×900px.

**Background, typography, color rules:** identical to other surfaces. #0b0b0d background. Inter font. Same neutral/bid/ask/accent palette. No agent identity colors on this surface (this is COOL mode, but the focus is performance metrics, not agent attribution).

**Layout — single column, max-width 1280px centered, vertical scroll**:

1. **Top bar** — 44px tall. Breadcrumb "Backtests > #9342". Right side: "[view canvas as run ▸]" button (ghost, indigo on hover).

2. **Run header** (below top bar): "Aggressive-v3 · 2026-01..2026-04 · 113 days · run 11m ago" in 14px regular, muted. The profile name is a link.

3. **HEADLINE METRICS section** — a card with #0f0f12 bg, 1px #18181b border, 6px corner. Internal grid 4-up:
   ```
   ROI         Sharpe         Sortino        maxDD
   +14.3%      1.84           2.42           -8.2%
   ```
   Then a second row inside the same card (separated by a thin divider line):
   ```
   trades      win-rate       avgR           profit-factor
   247         58%            +0.42          1.71
   ```
   Each metric: label in 11px caption muted, value in 24px display semibold tabular. ROI value in emerald, maxDD in red, others in neutral primary. Right-align each metric block; add 32px gap between blocks.

4. **EQUITY CURVE section** — title "EQUITY CURVE" in 11px caption, 16px gap below. A wide chart panel: line chart of equity over time (113 days), with a subtle filled area below the line (10% opacity emerald for positive, red for periods below starting equity). Below the equity line, a SECOND ROW chart showing drawdown as a filled area below the x-axis (red area, with the deepest drawdown labeled "-8.2% at 2026-03-12"). X-axis: monthly tick labels Jan/Feb/Mar/Apr. Y-axis: minimal labels at 0, 10k, 12k, 14k. NO grid lines (the curve shape IS the information). Hover tooltip placeholder showing date + equity at one point.

5. **Two-column grid below equity curve:**

   **TRADE DISTRIBUTION** (left, ~50% width): a histogram of R-multiples. X-axis from -3R to +5R in 0.5R bins. Bars are split: positive R bars in emerald, negative R bars in red. Below the histogram, a small inline summary: "long: 156 trades · short: 91 trades · longest streak: 12 wins"

   **REGIME BREAKDOWN** (right, ~50% width): a horizontal bar chart with three rows: "trending +12.4%" (long emerald bar), "choppy +1.4%" (short emerald bar), "reversal -2.7%" (red bar). Each row labeled. To the right of each bar: count of trades during that regime ("trending: 142 trades, 64% win") in 11px caption.

6. **TRADES TABLE** section — title "TRADES" with a small filter bar (filter by symbol, side, R range). A dense Table:
   - Headers: time | symbol | side | size | entry | exit | R | reason
   - 8 example rows of varied trades, with:
     - time in mono format like "2026-04-12 14:32"
     - symbol like "BTC-PERP"
     - side as colored chip (emerald "LONG" or red "SHORT")
     - numbers right-aligned, tabular
     - R column with PnLBadge style (+1.4R emerald, -0.7R red)
     - reason as a small chip with the canvas node that fired it ("strategy_eval node #4")
   - One trade row should have a small "▸ trace" link visible on hover
   - Pagination footer: "1–8 of 247   ◀ prev  next ▶"

**Visual character:**
- Calm, reference-text energy
- Every chart axis has minimal labels — no overcrowding
- Every metric has its label clearly positioned (label ABOVE value, not inline)
- No drop shadows, no gradients, no decorative elements
- The page should feel like reviewing a research paper

## REFERENCE NOTES

Priority reference uploads:
1. `08-reference-library/images/11-tradingview-strategy-tester.png` — equity curve + metrics layout
2. `08-reference-library/images/12-quantconnect-results.png` — backtest result density
3. `08-reference-library/images/13-stripe-dashboard.png` — calm metric card treatment
4. `08-reference-library/images/14-numeric-research-paper.png` — the visual "research paper" feel

## ANTI-PROMPT

```
DO NOT generate:
  - dashboard widgets with rounded card-cards-cards layouts
  - oversized hero numbers in marketing colors (cyan, purple)
  - 3D charts, drop-shadows, animated counters
  - "🚀" or any emoji in metric cards
  - chart legends with colored squares (use direct labels instead)
  - generic "ROI 📈" iconography next to numbers
  - light-mode chart aesthetic ported into dark
```
