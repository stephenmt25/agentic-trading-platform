# Praxis — Design Philosophy

> "Theory into practice, grounded wisdom, decisive action."

This document defines the **emotional and operational intent** behind every screen, component, and interaction in the Praxis trading platform. It is the first thing the coding harness should read. Every later document refers back to these principles when justifying a decision.

---

## 1. The Praxis Tension

Praxis sits at the intersection of three vocabularies that rarely cohabit:

| Vocabulary | What it brings | What it threatens |
|---|---|---|
| **Pro-retail crypto trading** (Hyperliquid, dYdX, Kraken Pro) | Real-time density, dark theme discipline, sub-second readouts | Visual noise, trader-bro aesthetic, cognitive overload |
| **Agentic AI software** (Cursor, Claude, Perplexity) | Reasoning streams, tool-call visualization, intervention UX | Chat-shaped UIs that conflict with high-frequency surfaces |
| **Modern fintech** (Stripe, Linear, Mercury) | Typographic restraint, generous whitespace, calm | Density too low for live tape, "blog post" aesthetic |

**The synthesis we are building:** a platform that *feels* as restrained and typographically considered as Linear, *behaves* as fast and dense as Hyperliquid, and *reasons visibly* like Claude — without the chat-shaped tax.

This is the design problem. Every component spec re-states some aspect of it.

---

## 2. The Three Modes of Praxis (and their visual contracts)

Praxis is not one product — it's three modes the same user moves between throughout the day. Each mode has a different density budget, motion budget, and color contract. Conflating them is the most common failure mode in trading-platform redesigns.

### 2.1 HOT mode — "the cockpit"
**Surfaces:** Hot Trading, Risk Control (live)
**Intent:** every pixel earns its place; the user is making decisions in seconds; numbers update continuously.
**Density:** maximum. Inter at 12–13px, tabular numerals, 4px spacing grid.
**Motion:** functional only — flash on price tick (180ms), pulse on order fill, no decorative animation, ever.
**Color:** semantic-loaded. Green/red carry cash-flow meaning, not status meaning. Neutral grays do all the structural work.
**Inspiration weight:** 70% Hyperliquid/dYdX, 20% Bloomberg discipline, 10% Linear restraint.

### 2.2 COOL mode — "the laboratory"
**Surfaces:** Pipeline Canvas, Backtesting & Analytics, Agent Observatory (when reviewing, not live)
**Intent:** the user is composing, comparing, reasoning. Time pressure is low. Cognitive depth is high.
**Density:** medium. Inter at 13–14px, more whitespace, room for diagrams and code.
**Motion:** expressive but short — node connections animate (220ms ease-out), reasoning streams type-on at 60–90 chars/sec, charts cross-fade.
**Color:** chromatic. Agent identities use distinct hues (HSL-spaced); regime states use a calm 5-step scale; chart series follow a perceptually-uniform sequence.
**Inspiration weight:** 40% TradingView/QuantConnect, 30% n8n/Langflow canvas, 20% Linear, 10% Cursor IDE.

### 2.3 CALM mode — "the office"
**Surfaces:** Profiles & Settings, Tax, Archives, Auth
**Intent:** infrequent, deliberate, configural. The user is editing intent, not reacting to markets.
**Density:** low. Inter at 14–15px, generous spacing, large form controls, prose-friendly line lengths.
**Motion:** minimal. Page transitions only, no on-data animations.
**Color:** monochrome with single accent. The accent is the *only* hue; everything else is neutral.
**Inspiration weight:** 60% Stripe/Linear, 30% Mercury, 10% Notion.

> **Why three modes and not one design system?** Because a single density does not serve all three. A typography system that's right for Hot mode is wrong for Calm; a motion system that's right for Cool is wrong for Hot. The token system (see `03-design-tokens/`) explicitly carries mode-scoped variants.

---

## 3. Core Principles

### P1. Numbers are the protagonist
In Hot and Cool modes, numeric values lead every visual hierarchy. Labels are subordinate. This means: tabular numerals always; right-align all numbers; reserve the largest type ramp steps for prices, PnL, position sizes; use *typography* to differentiate magnitude (display weight 600 for primary, 500 for secondary), not color.

> **Do** — `$42,318.27` in Display/Bold tabular, with the label "Equity" in Caption/Regular above it
> **Don't** — equal-weight label and value, or color-coded magnitudes

### P2. Color carries meaning, never decoration
The full palette has six chromatic semantic roles:
- `bid` (green family) — own buys, positive PnL, ask-side liquidity flowing in
- `ask` (red family) — own sells, negative PnL, bid-side liquidity flowing out
- `neutral` (grays) — structure, chrome, non-directional data
- `accent` (indigo, single hue) — interactive affordances, focus, the platform's "voice"
- `warn` (amber) — limits approached, soft thresholds, advisory
- `danger` (red, distinct from ask) — kill-switch territory, hard violations

Agent identities (ta, regime, sentiment, slm, debate, analyst) are **not a chromatic role** — per ADR-012 they alias to `accent` and differentiate by glyph, label, and column position. The 3-color discipline holds platform-wide; multi-agent surfaces lean on typography and structure, not hue.

Anything that isn't in this taxonomy doesn't get color. Brand expression happens through type and layout.

### P3. The platform reasons visibly
The "agentic" parts of Praxis (debate, regime_hmm, sentiment, ta_agent, slm_inference) are not background services — they are protagonists with visible identities. Every trading decision must be traceable to *which agent argued what and why*, with the same fidelity Claude/Cursor give to tool calls. This is not Bloomberg with a chatbot bolted on; the reasoning surface is a first-class peer to the order entry surface.

### P4. The canvas is the source of truth
`trading_profiles.pipeline_config` is authoritative (per CLAUDE.md). The visual canvas is therefore not "a fancy editor" — it is the *primary* mental model for what a profile does. Every backtest, every live order, every agent decision should be linkable back to a node on the canvas. The canvas surface gets investment proportional to that authority.

### P5. Confidence intervals, not point estimates
Every model output (price prediction, regime probability, sentiment score) is a distribution, not a number. Display confidence intervals or probability distributions wherever the underlying value carries uncertainty. Hide the uncertainty only when the user has explicitly opted into a denser view.

### P6. Reversibility is a visual property
Destructive or irreversible actions (placing orders, killing the switch, deleting profiles) get visual *weight* proportional to their consequence: larger hit areas, distinct color treatment, secondary confirmation for the truly catastrophic. Frequent reversible actions (scrolling, filtering, hovering) are friction-free. The Bloomberg/Hyperliquid "two-tap to fire an order" pattern is a deliberate choice, not laziness — it earns it through hit-area discipline.

### P7. Keyboard is a first-class input
The entire Hot mode must be operable from the keyboard. This is not accessibility theater — it's how power users work. Every actionable element has a documented keyboard shortcut; a `?` key surface lists them; focus rings are visible without being decorative. Inspiration: Bloomberg function codes, Linear's command-K palette, Vim modal editing.

### P8. Decimal precision is sacred
Per CLAUDE.md §2A: financial values are `Decimal`, never `float`. The UI inherits this discipline. Never round in display unless the user has zoomed out (e.g., portfolio-level totals). When rounding, show the rounded indicator (`~` or trailing `…`). Never lose a basis point silently.

---

## 4. The Vibe (for Google Stitch)

When prompting Stitch with the "Vibe Design" feature, this is the source-of-truth emotional brief:

> A Praxis screen should feel like *the bridge of a research vessel*: instruments everywhere, but every instrument is calm, labeled, and trustworthy. The lights are dim because the work is precise — not because we're hiding anything. When something needs attention, exactly one thing glows. When the AI agents reason, you can listen in on the conversation without it intruding on the controls. The whole thing should feel built by people who have shipped production trading systems and also read Edward Tufte.

**Reference moods (in order of weight):**
1. Hyperliquid at 3am during a volatile session
2. The Linear sidebar redesign
3. Claude's tool-use reasoning expanding inline
4. A Bloomberg terminal viewed across the trading floor — illegible from far away, perfectly clear up close
5. The Stripe API docs — calm, generous, trusted
6. n8n's canvas with a complex workflow rendered

**Anti-moods (explicitly avoid):**
- Anything Coinbase consumer
- Robinhood / casino-trading aesthetics (large hero numbers, confetti, cards-on-cards)
- "Web3 vibes" — chromatic gradients, glassmorphism, neon-on-purple
- Generic SaaS dashboard (Material 3, Bootstrap admin templates)
- Any AI-app-builder default look (v0/Bolt/Lovable shadcn-on-Tailwind generic)

---

## 5. Where to read next

| If you're building... | Read next |
|---|---|
| Information architecture | `02-information-architecture.md` |
| The token system | `03-design-tokens/tokens.json` and `tokens.css` |
| A specific component | `04-component-specs/{primitives,data-display,trading-specific,agentic,canvas}.md` |
| A specific screen | `05-surface-specs/0{1-6}-*.md` |
| A Stitch prompt to generate a screen | `06-stitch-prompts/0{1-6}-*.prompt.md` |
| The single doc to feed Claude Code | `07-claude-code-context.md` |
| Why we made these choices (ADRs) | `09-decisions-log.md` |
