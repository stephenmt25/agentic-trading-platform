# Stitch Outputs

Log of Stitch runs against the prompts in `06-stitch-prompts/`. Each entry captures the prompt used, references uploaded, the Figma export URL, and a one-paragraph review of the result vs. the portfolio specs.

| Date | Surface | Prompt file | Figma URL | Notes |
|------|---------|-------------|-----------|-------|
| 2026-05-07 | Profiles & Settings (calibration v1) | `06-stitch-prompts/06-profiles.prompt.md` | _HTML output, no Figma export_ | Iteration #1 — see audit below. Structure right, color/icon systems drifted to Material Design defaults, paused cards abbreviated. Iteration prompt staged below. |

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

## Calibration v1 — audit (2026-05-07)

**Verdict:** good baseline; structure is right; needs one focused iteration to fix color/icon drift and restore abbreviated content. Not yet usable as visual grounding for component generation.

**What landed correctly:**
- Two-column nav (56px rail + 220px settings column), main content bounded to 720px and centered.
- Background `#0f0f12`, card `#18181b`, border `#27272a`.
- IBM Plex Sans loaded (design system override worked end-to-end).
- All three card titles, status pills, meta rows; the kill-switch tooltip on Edit settings.

**Drift to fix in v2:**
1. Accent: design system tokens emit `primary: #c0c1ff` (Material You light indigo); only raw hex literals use `#6366f1`. Force `#6366f1` for all primary roles.
2. Card 1 "Open in canvas" is solid primary indigo. Spec says all three actions are ghost; indigo on hover only.
3. Material Symbols icons everywhere — pulls toward Google MD3 aesthetic. Switch to single-stroke 1.5px line icons (Lucide grammar).
4. Left rail has 4 + Help icons. Spec wants all six surfaces: Hot Trading, Agent Observatory, Pipeline Canvas, Backtesting, Risk Control, Settings (active).
5. Tabular font mapped to JetBrains Mono. Should be IBM Plex Mono.
6. Card 2: only 2 metrics (missing Win Rate). All three metrics required, with `--` for paused state.
7. Card 3: 0 metrics, only one action. Restore three metrics + the same three actions as card 1.
8. Card 2 has "Resume" instead of "Edit settings + Run backtest". All three cards share the same three actions; paused state can swap "Run backtest" for "Resume" only.
9. Settings nav has 9 items including extra "Security". Spec lists 8 — remove Security.
10. Output includes a 64px top header with breadcrumb + notifications. The surface starts BELOW the chrome bar (chrome lives in `RedesignShell`). Drop the top header from the surface output.
11. LIVE pill / PnL green is `#22c55e` (Tailwind default). Use `#10b981` exactly (our `--color-bid-500`).
12. Card hover changes border but no shadow. Add a subtle shadow on hover.

### Iteration #2 — refinement prompt to paste into Stitch

Tell Stitch (via natural-language edit on the same screen):

```
Refinements to the Profiles & Settings screen — please apply ALL of these:

COLOR (strict):
- The accent color must be exactly #6366f1, not a Material You derived primary. Wherever the design system emits primary tones like #c0c1ff or #8083ff, replace with #6366f1. The accent appears in: the active settings nav indicator bar, hover states on ghost buttons, the active filter tab underline, and the "+ New profile" button hover. Nowhere else.
- The LIVE status pill dot and the positive PnL value use exactly #10b981 (not #22c55e).
- Replace "primary" / "primary-container" / "secondary-container" semantic tokens with literal hex on the elements that use them, so no Material You derived tones appear.

ICONS (strict):
- Replace ALL Material Symbols Outlined icons with single-stroke 1.5px outline line icons (Lucide grammar). Square 20x20px optical-aligned. Do not use filled or rounded variants. The tone is "engineered" — closer to Heroicons outline or Lucide than to Google's Material set.

LEFT RAIL (six icons, not four):
- The 56px rail must contain SIX surface icons in this order from top:
  1. Hot Trading (lightning / zap)
  2. Agent Observatory (cpu / bot)
  3. Pipeline Canvas (workflow / nodes)
  4. Backtesting (bar chart)
  5. Risk Control (shield)
  6. Profiles & Settings (gear) — currently active, indigo bar on left
- Below them (separated by a thin line), keep two utility icons: keyboard reference (?) and session switcher (user circle).
- No "Home" or "Help" icon.

SECONDARY NAV (settings column, 220px):
- Must be exactly these eight items in this order: Profiles (active), Exchange keys, Risk defaults, Notifications, Tax, Account, Sessions / API, Audit log.
- Remove the "Security" item — it is not in the spec.
- No section divider between them.

CARDS — all three must be structurally identical:
- All three cards show three metrics under "Last 7 days": PnL, Trades, Win rate. For paused cards 2 and 3, the values are em-dash "—" not blank.
- All three cards show the same three action buttons in the same order: "Open in canvas", "Edit settings", "Run backtest". On paused cards, "Run backtest" is replaced with "Resume" but the other two are unchanged.
- ALL three buttons on EVERY card are ghost (transparent background, #27272a border, off-white text). On hover the border becomes #6366f1 and the text becomes #6366f1. None of the three is a solid primary button.
- Card hover state: border darkens from #27272a to #3f3f46 AND a small shadow appears (0 4px 12px rgba(0,0,0,0.4)). Currently only the border changes.

CHROME (remove):
- Drop the entire 64px top header bar (with breadcrumb + notifications + avatar). The Profiles surface starts directly at the page header "Profiles" with subtitle and "+ New profile" button. The chrome lives outside this surface.

TYPOGRAPHY:
- The mono font must be "IBM Plex Mono" (not "JetBrains Mono") wherever tabular figures appear (PnL value, Trades count, Win rate, meta row).

Do not introduce new sections. Do not add empty-state illustrations or hero banners. Keep the rest unchanged.
```

After applying, re-export and update the table at the top of this file with the v2 result + a fresh audit row.

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
