# Praxis Frontend — DESIGN.md (for Claude Code)

> This file is intended to live at `frontend/DESIGN.md` in the Praxis repo on the redesign branch. It is the **single file** Claude Code should read to understand the design intent of the redesign. Everything else in this folder is a deeper drill-down; this file synthesizes the operating contract.

---

## TL;DR for the harness

You are redesigning the frontend of Praxis — an agentic crypto trading platform — onto a parallel branch. The redesign has six surfaces, three "modes" (HOT/COOL/CALM), a custom token system, and a strict color-as-meaning contract.

**The design portfolio at `docs/design/` is the source of truth.** When in doubt, read it. When this DESIGN.md and the portfolio disagree, the portfolio wins; flag the discrepancy and propose an update.

**Non-negotiables for any generated component:**
1. Use design tokens from `docs/design/03-design-tokens/tokens.css` (or the JSON if generating Tailwind config). Never hard-code hex colors.
2. Respect mode boundaries: HOT mode is dense; CALM mode is roomy; COOL is in between. Look up the surface in `docs/design/05-surface-specs/` to know which mode applies.
3. Numbers always use `font-feature-settings: 'tnum' 1` on IBM Plex Mono (tabular numerals — see ADR-011). Apply via the `.num-tabular` utility (see `docs/design/03-design-tokens/tailwind.preview.js`).
4. Color carries meaning, not decoration. There are six chromatic semantic roles (bid, ask, neutral, accent, warn, danger). Agent identities alias to accent and differentiate by glyph + label + position — see ADR-012.
5. Financial values are `Decimal` per the existing `libs/core/types.py` contract — display formatting respects this; never round silently.
6. Every actionable element has a keyboard shortcut documented in the surface spec.

---

## Where things live

```
docs/design/                      ← root of the design portfolio
├── 00-INDEX.md                   ← navigation
├── 01-design-philosophy.md       ← why this design exists
├── 02-information-architecture.md ← what surfaces exist
├── 03-design-tokens/             ← the token system
│   ├── tokens.json               ← DTCG format
│   ├── tokens.css                ← CSS custom properties
│   └── tailwind.preview.js       ← Tailwind config preview
├── 04-component-specs/           ← every reusable component
│   ├── primitives.md
│   ├── data-display.md
│   ├── trading-specific.md
│   ├── agentic.md
│   └── canvas.md
├── 05-surface-specs/             ← every screen
│   ├── 01-hot-trading.md
│   ├── 02-agent-observatory.md
│   ├── 03-pipeline-canvas.md
│   ├── 04-backtesting-analytics.md
│   ├── 05-risk-control.md
│   └── 06-profiles-settings.md
├── 06-stitch-prompts/            ← Google Stitch prompts (peer tool)
├── 08-reference-library/         ← annotated inspiration sources
│   ├── README.md
│   ├── inspiration-catalog.md
│   └── images/                   ← user populates with screenshots
└── 09-decisions-log.md           ← ADRs explaining design choices
```

---

## How to use this for code generation

### When asked to "create a new component"
1. Check whether it belongs in `primitives.md`, `data-display.md`, `trading-specific.md`, `agentic.md`, or `canvas.md`. If it doesn't fit any of these, the request is suspicious — flag it and ask whether the portfolio needs updating.
2. Read the spec for that component. The **Tokens** line is the contract for what it consumes.
3. Generate the component following the spec exactly. States, variants, accessibility — all required.
4. Use Tailwind v4 with the config from `03-design-tokens/tailwind.preview.js`.
5. Files go under `frontend/components/{primitives,data-display,trading,agentic,canvas}/`. (The existing project has no `src/` layer — components live directly under `frontend/components/`.)

### When asked to "build a screen"
1. Read the corresponding surface spec in `05-surface-specs/`.
2. Compose the screen from existing components — DON'T reinvent. If a component doesn't exist, generate it first per its component spec.
3. Wire up data via the existing API client at `frontend/lib/api/client.ts` (the actual entry point — `lib/api.ts` does not exist; the client is one level deeper). Map data per the surface spec's "Backed by" line.
4. Apply mode-specific data attribute on the surface root: `<div data-mode="hot">` etc. This activates the right semantic CSS vars.
5. Implement the keyboard map in the spec.

### When asked to "extend the design"
1. **Read `01-design-philosophy.md` first**. The 8 principles (P1–P8) constrain what's permissible.
2. If a request would violate a principle, *flag the violation and propose alternatives* before implementing. Don't silently bend the system.
3. If the addition is legitimate, update both the relevant component/surface spec AND this DESIGN.md. Treat the design portfolio as part of the codebase.

### When the request is for a "new surface"
1. New surfaces require a new spec in `05-surface-specs/` and an entry in `02-information-architecture.md`. Generate the spec FIRST, get user signoff, then implement.
2. New surfaces need a mode assignment (HOT/COOL/CALM) and a place in the IA graph. The graph in `02-information-architecture.md` §9 must be updated.

---

## Mode rules (canonical)

```
HOT mode  → density max, motion ≤180ms, color semantic-loaded, tabular numerals everywhere
COOL mode → density medium, motion ≤220ms, expressive but mode-budgeted motion (agents differentiate by glyph, not hue — ADR-012)
CALM mode → density low, motion ≤320ms, monochrome + single accent only
```

Mode is set via `data-mode="..."` on a surface root. Do not mix modes within a single surface. Do not assume any default — be explicit.

---

## Component composition

The hierarchy is **primitives → data-display → domain (trading or agentic or canvas)**. Domain components compose data-display + primitives but *never* the other way around.

A `PnLBadge` is a domain component → it composes a primitive (Tag) and a data-display (KeyValue) but is itself only used in domain layouts. A `Button` (primitive) never imports from domain.

---

## Critical-path components

These components have higher reliability requirements than others (per surface specs):

- **OrderEntryPanel** (Hot Trading) — its `kill-switch-armed` state must always render correctly when the kill switch is hard-armed
- **KillSwitchControl** (Risk Control) — must work when other services are unreachable
- **PnLBadge** (chrome) — must update at every PnL tick without dropping frames
- **OrderBook** (Hot Trading) — must virtualize and never block the main thread on update bursts

If you're generating these, ALSO generate unit tests for the critical-path behaviors.

---

## What "looks right"

If a generated screen passes these checks, it probably looks right:

- [ ] Background is `#0b0b0d` (or #0f0f12 in Calm mode) — never pure black, never near-white
- [ ] All numbers use tabular figures and right-align in tables
- [ ] No element uses a color outside the six chromatic semantic roles
- [ ] No element uses chromatic differentiation between agents — glyph + label + position only (ADR-012)
- [ ] No emojis used in production UI (occasional in tooltips/help is acceptable; review case-by-case)
- [ ] Every interactive element has a focus ring at `accent.500` 2px
- [ ] No card has shadow more dramatic than `shadow-md`
- [ ] No animation longer than the mode's motion budget
- [ ] Every text element traces back to a `typography.scale.*` token

If a generated screen fails any of these, that's a regression — fix before merging.

---

## Service mapping (for data wiring)

| Surface | Reads from | Writes to |
|---|---|---|
| Hot Trading | api_gateway, ingestion (WS), pnl (pubsub), validation, hot_path | execution (orders) |
| Agent Observatory | analyst, debate, ta_agent, regime_hmm, sentiment, slm_inference (each via WS or pub/sub) | analyst (overrides) |
| Pipeline Canvas | api_gateway/agent-config (canvas read), strategy | api_gateway/agent-config (canvas save), pipeline_compiler |
| Backtesting | backtesting (run dispatch, status WS), archiver (results) | backtesting (start run) |
| Risk Control | risk, pnl, rate_limiter (state), kill switch (Redis) | kill switch (Redis), risk (limit edits) |
| Profiles & Settings | api_gateway (profiles, exchange, tax), audit | same |

The frontend layer should treat these as a thin client — most logic stays server-side. Service boundaries match the architecture in `CLAUDE.md`.

---

## Backend coordination notes (per CLAUDE.md)

- Financial values are `Decimal`. Frontend deserializes from string-encoded JSON; never use `parseFloat`. There's a `Decimal.js` or similar in the existing frontend; use it.
- Redis channel names are authoritative in `libs/messaging/channels.py`. Never invent.
- Profile saves go through `PUT /agent-config/{profile_id}/pipeline` (canonical canvas save) — see `libs/core/pipeline_compiler.py`. The legacy `PUT /profiles/{id}` endpoint is deprecated for canvas; user-facing creation flow uses it but should migrate.
- Phase 1 vs Phase 2: this redesign covers Phase 1 surfaces (Hot Trading, Risk Control, Profiles) AND Phase 2 surfaces (Agent Observatory, Canvas, Backtesting). Don't assume Phase 1 frontend can ship without the Phase 2 dependencies — the Canvas surface needs `pipeline_compiler` and Phase 2 ML services to be operational.

---

## When you don't know

If a question isn't answered in the portfolio, do NOT make it up. Ask the user. The portfolio is meant to be exhaustive enough that ambiguity is a bug — flag the gap and we'll fix the docs together.

---

*Last updated: 2026-05-07. See `09-decisions-log.md` for the rationale behind any of these choices.*
