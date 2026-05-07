# Praxis Design Portfolio — INDEX

> *Theory into practice, grounded wisdom, decisive action.*

This is the navigation map for the design portfolio that drives the Praxis frontend redesign. The portfolio is consumed by **two tools**: Claude Code (as design context) and Google Stitch (as text+image prompts). Every artifact below has been authored to serve both.

---

## Read this first

| | |
|---|---|
| **New here?** | Start with [`01-design-philosophy.md`](01-design-philosophy.md) → [`02-information-architecture.md`](02-information-architecture.md). They're the "why" of everything else. |
| **Building a screen?** | Read the matching surface spec in [`05-surface-specs/`](05-surface-specs/), then compose components from [`04-component-specs/`](04-component-specs/). |
| **Generating with Stitch?** | Use the prompts in [`06-stitch-prompts/`](06-stitch-prompts/). Populate [`08-reference-library/images/`](08-reference-library/) with screenshots first. |
| **Wiring data?** | [`07-claude-code-context.md`](07-claude-code-context.md) §"Service mapping" |
| **"Why did we choose X?"** | [`09-decisions-log.md`](09-decisions-log.md) — ADRs |
| **"What's not yet covered?"** | [`10-known-gaps-v1.1.md`](10-known-gaps-v1.1.md) — 17 known issues with v1.1 plans |
| **"How do I execute this redesign?"** | [`11-redesign-execution-plan.md`](11-redesign-execution-plan.md) — step-by-step branch setup → cutover |

---

## Full file map

```
docs/design/
│
├── 00-INDEX.md                          ← this file
├── 01-design-philosophy.md              ← principles, modes, vibe
├── 02-information-architecture.md       ← six surfaces, IA graph, nav model
│
├── 03-design-tokens/                    ← the token system (foundation)
│   ├── tokens.json                          DTCG format — the canonical source
│   ├── tokens.css                           CSS custom properties (drop-in)
│   └── tailwind.preview.js                  Tailwind v3/v4 config preview
│
├── 04-component-specs/                  ← every reusable building block
│   ├── README.md                            spec-format reading guide
│   ├── primitives.md                        Button, Input, Select, Toggle, Tag, Kbd, Tooltip, Avatar
│   ├── data-display.md                      Table, List, KeyValue, Sparkline, Pill, StatusDot
│   ├── trading-specific.md                  OrderBook, DepthChart, TapeRow, PnLBadge, RiskMeter, OrderEntryPanel, PositionRow
│   ├── agentic.md                           AgentTrace, ReasoningStream, ToolCall, DebatePanel, ConfidenceBar, AgentAvatar
│   └── canvas.md                            Node, Edge, NodePalette, MiniMap, NodeInspector, RunControlBar
│
├── 05-surface-specs/                    ← every screen
│   ├── 01-hot-trading.md                    HOT — the cockpit (chart + book + entry + agents summary)
│   ├── 02-agent-observatory.md              COOL — agent reasoning, traces, debates, intervention
│   ├── 03-pipeline-canvas.md                COOL — node-based profile editor (source of truth)
│   ├── 04-backtesting-analytics.md          COOL — historical evaluation
│   ├── 05-risk-control.md                   HOT — kill switch, exposure, limits, violations
│   └── 06-profiles-settings.md              CALM — settings, exchange keys, tax, audit
│
├── 06-stitch-prompts/                   ← Google Stitch prompts (one per surface)
│   ├── README.md                            how to use Stitch effectively with this portfolio
│   ├── 01-hot-trading.prompt.md
│   ├── 02-agent-observatory.prompt.md
│   ├── 03-pipeline-canvas.prompt.md
│   ├── 04-backtesting.prompt.md
│   ├── 05-risk-control.prompt.md
│   └── 06-profiles.prompt.md
│
├── 07-claude-code-context.md            ← single-file DESIGN.md for Claude Code
│
├── 08-reference-library/                ← visual inspiration (you populate the images)
│   ├── README.md                            capture guide + filename convention
│   ├── inspiration-catalog.md               annotated source list with what-to-take/leave
│   └── images/                              (empty — drop your screenshots here)
│
├── 09-decisions-log.md                  ← ADRs (architecture decision records)
├── 10-known-gaps-v1.1.md                ← issues identified, scoped for next iteration
└── 11-redesign-execution-plan.md        ← branch setup, build order, Stitch+Claude Code workflow, cutover
```

---

## The portfolio as a contract

This portfolio is meant to be **exhaustive enough that ambiguity is a bug**. Specifically:

- If the harness wants to make a design choice not covered here, the right answer is to **flag the gap and ask** — not to invent.
- If the harness generates output that contradicts the portfolio, the portfolio wins. The output is wrong, and the way to fix it is to either re-anchor the harness or update the portfolio (with an ADR).
- If you, the user, change your mind on a principle, **update the philosophy doc and the relevant ADR** before re-running the harness. The harness's output is downstream of the portfolio, not parallel to it.

---

## How the dual-consumer (Claude Code + Stitch) workflow runs

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   1. You take screenshots → 08-reference-library/images/                │
│                                                                          │
│   2. You open Google Stitch → paste 06-stitch-prompts/{surface}.md +    │
│      upload reference images → iterate to a Figma export                │
│                                                                          │
│   3. You hand off to Claude Code on the redesign branch:                │
│      - Pin DESIGN.md = 07-claude-code-context.md                        │
│      - Reference 03-design-tokens/tokens.css for tokens                 │
│      - Reference 04-component-specs/ + 05-surface-specs/                │
│      - Optional: feed Stitch-generated Figma file as visual grounding   │
│                                                                          │
│   4. The harness generates components → you review against              │
│      "What looks right" checklist in 07-claude-code-context.md          │
│                                                                          │
│   5. Surfaces compose → integrate into the redesign branch              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Status of this portfolio

**Version:** 1.0.0-draft
**Last updated:** 2026-05-07
**Owner:** Wrench (renchythomas@gmail.com)
**For:** Praxis frontend redesign — parallel branch off `main`

This is a v1 draft. Expected gaps to fill in v1.1:
- A handful of agentic-component edge cases (e.g., what happens when a debate has 6+ participants instead of 4 — we've sized for 4)
- Mobile responsive specs are intentionally thin; we want to validate desktop first
- Empty-state copywriting needs a content review
- A11y deep-dive (we've covered keyboard + ARIA hints; needs a screen-reader pass)

If you discover gaps while running the harness, flag them in `09-decisions-log.md` as candidate ADRs.
