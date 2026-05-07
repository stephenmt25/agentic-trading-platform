# Stitch Outputs

Log of Stitch runs against the prompts in `06-stitch-prompts/`. Each entry captures the prompt used, references uploaded, the Figma export URL, and a one-paragraph review of the result vs. the portfolio specs.

| Date | Surface | Prompt file | Figma URL | Notes |
|------|---------|-------------|-----------|-------|
| _pending_ | Profiles & Settings (calibration) | `06-stitch-prompts/06-profiles.prompt.md` | — | First calibration run |

---

## How to log a run

When you finish a Stitch run:

1. Add a row to the table above with date (YYYY-MM-DD), surface name, prompt file path, and the Figma export URL.
2. If the result needs iteration, leave the row in place and add a sub-bullet beneath it describing the divergence and what changed in the next run.
3. If the result is good enough to use as Claude Code visual grounding, also drop a screenshot into `images/` with a descriptive name like `stitch-NN-surface-vN.png` (these supplement the canonical inspiration captures, they don't replace them).

---

## Calibration run — Profiles & Settings (pending)

The plan calls Profiles the calibration surface (simplest, lowest iteration cost). Steps:

1. Open <https://stitch.withgoogle.com/>. Pick **Thinking with 3.1 Pro** as the model — its deliberate reasoning is what we want for a heavily-anchored prompt with three references and a long anti-prompt. Reserve **3 Flash** for iteration tweaks after the layout is right. **Redesign** and **Ideate** are not applicable here (we're generating from scratch with anchored constraints, not reimagining or brainstorming).
2. Configure the design system before generation:
   - Color mode: **Dark**
   - Custom color (accent): **`#6366f1`** (per ADR-014)
   - Body / headline font: **IBM Plex Sans** (per ADR-011)
   - Roundness: **Round 4** (closest to our `--radius-md` 6px)
3. Paste **all three sections** of `06-stitch-prompts/06-profiles.prompt.md`:
   - `## VIBE`
   - `## DETAILED PROMPT`
   - `## ANTI-PROMPT`
4. Upload reference images. The prompt's "REFERENCE NOTES" lists three priority references:
   - `13-stripe-dashboard.png` — **present** ✅ (the metric-cards / calm-dashboard reference; upload this first)
   - `17-linear-settings.png` — **not yet captured** (Linear's settings IA is the missing piece). Use `03b-linear-inbox.png` or `03-linear-app.png` as the closest stand-in for typographic restraint and sidebar-with-bounded-content layout.
   - `18-mercury-dashboard.png` — **not yet captured** (calm fintech monochrome). No direct stand-in; the Stripe ref above carries most of this mood.

   Recommended upload set for this run: `13-stripe-dashboard.png` + `03-linear-app.png` + `03b-linear-inbox.png`. Three references is enough; more dilutes the signal.
5. Iterate using Stitch's natural-language editing. When asking for changes, anchor with token names from `tokens.json` — e.g., "use `--bg-canvas` not `--bg-panel` for the page background", "indigo accent stays at `--color-accent-500` only for hover and the new-profile button".
6. When the result feels right, **export to Figma**, copy the Figma file URL, and log it in the table above.

If after a few iterations the output still looks generic-shadcn or marketing-page, re-anchor with `01-design-philosophy.md` §4 (Vibe + Anti-moods) and try again. The prompt is intentionally heavy on anti-references because Stitch defaults pull toward generic SaaS dashboards.

---

## Inventory snapshot

Canonical slots present (highest-leverage 5 = ⭐):

| Slot | File | Used by surface prompts |
|------|------|--------------------------|
| ⭐ 01 | `01-hyperliquid-trading.png` | 01 Hot Trading, 02 Agent Observatory |
| 02 | `02-dydx-trading.png` | 01 Hot Trading |
| ⭐ 03 | `03-linear-app.png` | 06 Profiles, 02 Observatory, anywhere needing typography restraint |
| ⭐ 05 | `05-claude-tool-use.jpg` | 02 Agent Observatory |
| ⭐ 08 | `08-n8n-canvas.png` | 03 Pipeline Canvas |
| 09 | `09-langflow-canvas.png` | 03 Pipeline Canvas (LLM-aware nodes) |
| 11 | `11-tradingview-strategy-tester.png` | 04 Backtesting (best-guess slot — rename to `11-tradingview-chart.png` if the capture is a chart, not the tester) |
| 12 | `12-quantconnect-results.png` | 04 Backtesting |
| ⭐ 13 | `13-stripe-dashboard.png` | 06 Profiles, 04 Backtesting, anywhere needing calm-mode metric cards |

Supplementary captures (not in canonical slot list — used as additional grounding):

- `01b/c/d/e-hyperliquid-*.png` — symbol picker, portfolio, staking, vaults
- `03b/c/d/e/f-linear-*.png` — inbox, initiatives, issues, projects, pulse
- `03g/h-linear-agent-*.png` — agent insights, agent task views (relevant for Agent Observatory)
- `08b-n8n-nodes.png`, `08c-n8n-node-menu.gif` — node palette + menu drilldown

Canonical slots still open:

| Slot | File | Source | Why we want it |
|------|------|--------|----------------|
| 04 | `04-bloomberg-tape.png` | Bloomberg time-and-sales screenshot | Density anchor for OrderBook / TapeRow |
| 06 | `06-cursor-agent-log.png` | cursor.com docs | Agent log multi-step plan (Observatory) |
| 07 | `07-perplexity-steps.png` | perplexity.ai Pro Search | Steps-panel pattern (Observatory) |
| 10 | `10-figma-component-vars.png` | figma.com any file | Right-inspector with component variants (component spec authoring) |
| 14 | `14-numeric-research-paper.png` | any quant finance PDF | Aesthetic ref — charts + tables |
| 15 | `15-aviation-cockpit.png` | "modern airliner glass cockpit" | Risk Control mood ref |
| 16 | `16-hyperliquid-margin.png` | hyperliquid margin section | Risk/margin display |
| 17 | `17-linear-settings.png` | linear.app settings | Settings IA reference (missing piece for the calibration run) |
| 18 | `18-mercury-dashboard.png` | mercury.com dashboard | Calm fintech monochrome (missing piece for the calibration run) |

Other surfaces' Stitch runs that the new captures unlock:

- **04 Backtesting** — has 11 + 12 (tradingview + quantconnect); 13 (stripe) for the metrics cards. Ready to run after Profiles calibration.
- **03 Pipeline Canvas** — has 08 + 09 (n8n + langflow). Ready.
- **02 Agent Observatory** — has 05 (Claude tool use) and supplementary 03g/h (Linear agent views). Missing 06 (Cursor) and 07 (Perplexity) — capturable when needed.
