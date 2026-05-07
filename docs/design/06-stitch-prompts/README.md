# Google Stitch Prompts

This folder contains paste-ready prompts for [Google Stitch](https://stitch.withgoogle.com/) — Google's AI tool that generates UI designs from natural-language prompts and reference imagery.

## How these are structured

Each `.prompt.md` file contains three sections you can use independently or combined:

1. **VIBE** — short emotional/intent description for Stitch's "Vibe Design" mode
2. **DETAILED PROMPT** — full screen description for Standard or Experimental mode
3. **REFERENCE NOTES** — pointers to inspiration images that should be uploaded as references (paths in `08-reference-library/images/`)

## Recommended Stitch workflow

1. Start with **Experimental Mode** (Gemini 2.5 Pro) for the highest fidelity. Only fall back to Standard for quick iterations.
2. Paste the **VIBE** + **DETAILED PROMPT** together in the prompt field.
3. Upload the suggested reference images from `08-reference-library/images/` (you populate that folder per `08-reference-library/README.md`).
4. Iterate using Stitch's natural-language editing — anchor each change with one of the design tokens or principles from this portfolio.
5. Export the resulting design as Figma → hand off to Claude Code via the surface spec in `05-surface-specs/`.

## What Stitch will struggle with

Be aware Stitch is good at static layout but tends to:
- Soften dense layouts toward generic SaaS aesthetics — counter by repeatedly emphasizing "high information density, financial terminal feel."
- Default to brighter color palettes — counter with explicit "near-black background #0b0b0d" anchors.
- Flatten typography hierarchy — counter with explicit type sizes from `03-design-tokens/tokens.json`.
- Render charts/canvases as decorative; you'll likely need to placeholder these and have Claude Code wire in real implementations later.

## Anti-prompts

These are anti-patterns to *explicitly forbid* in every prompt (Stitch responds to negative constraints):

```
DO NOT use:
  - rounded "iOS card" aesthetics; corners are 4–8px max
  - playful gradients, glassmorphism, or 3D effects
  - emoji-heavy imagery or generic AI-app illustrations
  - light theme; this is a dark-only platform
  - generic SaaS green-success/red-error patterns; use platform-specific bid-green and ask-red as defined
  - cards-on-cards-on-cards; embrace flat panels with thin borders
```
