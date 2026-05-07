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

1. Open <https://stitch.withgoogle.com/>, switch to **Experimental Mode** (Gemini 2.5 Pro).
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
   - `13-stripe-dashboard.png` — **not yet captured**
   - `17-linear-settings.png` — **not yet captured**
   - `18-mercury-dashboard.png` — **not yet captured**
   Until those land, upload `03-linear-app.png` as the closest available stand-in (Linear's typographic restraint is the right mood for the Profiles surface even if the layout differs).
5. Iterate using Stitch's natural-language editing. When asking for changes, anchor with token names from `tokens.json` — e.g., "use `--bg-canvas` not `--bg-panel` for the page background", "indigo accent stays at `--color-accent-500` only for hover and the new-profile button".
6. When the result feels right, **export to Figma**, copy the Figma file URL, and log it in the table above.

If after a few iterations the output still looks generic-shadcn or marketing-page, re-anchor with `01-design-philosophy.md` §4 (Vibe + Anti-moods) and try again. The prompt is intentionally heavy on anti-references because Stitch defaults pull toward generic SaaS dashboards.
