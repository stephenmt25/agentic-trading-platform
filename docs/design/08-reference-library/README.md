# Reference Library

This folder is where you curate the **visual** inspiration for the redesign — the screenshots that:
1. you upload to Google Stitch alongside the prompts in `06-stitch-prompts/`,
2. Claude Code can read (multimodal) for visual grounding when generating components.

## What goes in `images/`

You manually populate the `images/` subfolder with screenshots you take from the inspiration sources listed in `inspiration-catalog.md`. Filenames are listed in each Stitch prompt's "REFERENCE NOTES" section and follow the convention:

```
NN-source-screen.png
```

Example: `01-hyperliquid-trading.png`, `08-n8n-canvas.png`.

## How to capture screenshots well

A reference image is *useful* when:
- It's at native resolution (≥1280px wide for desktop screens)
- It captures the *whole* screen surface (not a cropped detail unless you want a single-element reference)
- Dark theme (where applicable)
- Real production data, not loading/empty states (unless that IS the reference)
- No personal account info visible — blur or crop out

A reference image is *not* useful when:
- It's a marketing splash page rather than the real product UI
- It's been auto-cropped by your screenshot tool
- It contains your real positions/keys (don't upload those)

## Suggested capture list

The following are the numbered files referenced across the Stitch prompts. Capture each from the source's live product (or, where impractical, from a high-quality YouTube screenshare or design write-up).

| # | Filename | Source URL | What to capture |
|---|---|---|---|
| 01 | `01-hyperliquid-trading.png` | app.hyperliquid.xyz | Main perp trading screen with order book, chart, trades, positions, all visible |
| 02 | `02-dydx-trading.png` | dydx.trade | Main trading screen, same composition as Hyperliquid |
| 03 | `03-linear-app.png` | linear.app (or your Linear instance) | Issue list view with sidebar, density visible |
| 04 | `04-bloomberg-tape.png` | (search "Bloomberg time and sales screenshot") | The classic time-and-sales window, monospace, dense |
| 05 | `05-claude-tool-use.png` | claude.ai during a tool-use turn | A response with a tool-use expansion block visible |
| 06 | `06-cursor-agent-log.png` | cursor.com (their docs/showcase) | The agent execution log with multi-step plan |
| 07 | `07-perplexity-steps.png` | perplexity.ai during Pro Search | The steps panel showing plan execution |
| 08 | `08-n8n-canvas.png` | n8n.io (their demo workflows) | A canvas with multiple nodes, edges, and panels visible |
| 09 | `09-langflow-canvas.png` | langflow.org showcase | An LLM-aware canvas with prompt/agent nodes |
| 10 | `10-figma-component-vars.png` | figma.com (any Figma file) | The right inspector with component variants |
| 11 | `11-tradingview-strategy-tester.png` | tradingview.com — a public strategy backtest result | Equity curve + headline metrics |
| 12 | `12-quantconnect-results.png` | quantconnect.com/research/algorithm | A backtest result page with metrics + equity |
| 13 | `13-stripe-dashboard.png` | dashboard.stripe.com (your account) | The home dashboard with metric cards and chart |
| 14 | `14-numeric-research-paper.png` | (any quantitative finance paper PDF) | A page with charts + metric tables — pure aesthetic reference |
| 15 | `15-aviation-cockpit.png` | (search "modern airliner glass cockpit") | A photo or rendering of a cockpit panel |
| 16 | `16-hyperliquid-margin.png` | app.hyperliquid.xyz margin section | Risk/margin display |
| 17 | `17-linear-settings.png` | linear.app settings | Settings IA reference |
| 18 | `18-mercury-dashboard.png` | mercury.com (your account or marketing) | Calm fintech dashboard reference |

You don't need ALL of them to start — the highest-leverage are 01, 03, 05, 08, and 13.

## How Claude Code uses these

When generating a component, prefix prompts with:
```
Look at docs/design/08-reference-library/images/01-hyperliquid-trading.png and 03-linear-app.png — these are the density and typography references. Generate the component to fit.
```

Claude Code's multimodal capability will use the images as visual grounding alongside the textual specs in `04-component-specs/`.
