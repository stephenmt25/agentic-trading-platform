# Inspiration Catalog

The four design vocabularies Praxis draws from, with specific extracts (what to take, what to leave) per source. The goal is to be **explicit about what we're borrowing** so the harness can be specific about what to imitate vs. avoid.

---

## 1. Pro-retail crypto/derivatives

The closest match to Praxis's domain. Take generously; leave nothing reckless.

### Hyperliquid
**Take:**
- Three-column trading canvas: left = market overview, center = order entry/chart, right = positions/portfolio (or our mirrored layout: left rail / center main / right entry+agents)
- Information density discipline — rows tight, type small, numbers tabular
- Subtle motion for confirmations and order fills (120–220ms, never longer)
- Collapsible advanced controls so power users can access fine-grained parameters quickly
- Dark theme as default
- Mobile stacked layout: chart top, order controls mid, portfolio bottom (we extend this to monitor-only on mobile)

**Leave:**
- Anything overtly "Web3" — wallet-connect prominence, gas-fee callouts, chain-branding
- Coloration that reads as crypto-bro

**Source:** app.hyperliquid.xyz; design write-up at hyperliq-trade-us.pages.dev

### dYdX (v4)
**Take:**
- Three principles articulated explicitly: (1) trust through information architecture, (2) critical data + inputs upfront with revert/cancel, (3) frequent actions ≤ 3 steps from anywhere
- Bespoke leverage selector with both slider and input field — we adopt this verbatim
- Improved order-type selector

**Leave:**
- Anything specific to their tokenomics / governance UI

**Source:** dydx.trade; engineering blog "The Evolution of the Trading Interface"

### Kraken Pro
**Take:**
- Unapologetic data density (this is a touchstone for "we're not afraid of dense screens")
- Customizable workspace
- Live order book + streaming trades coexisting

**Leave:**
- Their specific iconography (legacy)

### Bookmap / TensorCharts (specialty viz)
**Take:**
- Order book heatmap: y = price, x = time, color intensity = liquidity at that level. Reference for visualizing depth over time.
- Cumulative-fill rendering on book rows (we adapt this in `OrderBook` component)

**Leave:**
- Their UI chrome — these are specialty tools whose chrome is dated

---

## 2. Quant/algo IDE-style

For Pipeline Canvas, Backtesting, and parts of Agent Observatory.

### TradingView
**Take:**
- Chart-first hierarchy (chart is the protagonist of the trading view)
- Left sidebar of drawing tools (we don't expose these on Hot Trading but the embedded chart inherits TradingView Lightweight Charts)
- Multi-chart layouts (12 patterns); we don't ship multi-chart at v1 but the IA accommodates it
- Strategy tester results page: equity curve + headline metrics + trades table — direct inspiration for our backtesting detail screen

**Leave:**
- Marketing / community / chat features
- Light theme

**Source:** tradingview.com docs

### QuantConnect
**Take:**
- Backtest result page composition (metrics card → equity → trade-by-trade)
- Strategy debugging perspective — focus on attribution

**Leave:**
- IDE itself (Praxis canvas is not a code IDE)

### Lean (CLI/research framework)
**Take:**
- Conceptual rigor about reproducibility (we reflect this in "view canvas as run" feature)

**Leave:**
- The CLI aesthetic — the canvas is graphical

---

## 3. Modern fintech / institutional-modern

For Calm mode and analytics surfaces.

### Stripe (Dashboard, API Docs)
**Take:**
- Card layout discipline: scales from few to many features without restructuring
- Trend indicator + sparkline on each metric card (we adapt this in Sparkline + KeyValue)
- Calm typography and generous whitespace
- Dashboard density control (user-adjustable density)
- API Docs reference book aesthetic — for docs/help surfaces

**Leave:**
- Light-mode default (we only do dark)
- Marketing-leaning home page styling

**Source:** dashboard.stripe.com, docs.stripe.com

### Linear
**Take:**
- 4px base spacing grid (we adopt verbatim)
- Inter typography on dark gray background — direct inspiration for our stack
- Modular components composing into varied views without traditional grid lock
- Settings IA pattern — sidebar nav + content with bounded width
- Command palette discipline (Cmd+K everywhere)
- Sidebar-redesign principles (typographic restraint, tight system)

**Leave:**
- Their accent color (we use indigo, not their purple gradient)
- Issue/project specific patterns that don't map to trading

**Source:** linear.app; their blog "How we redesigned the Linear UI"

### Mercury, Brex, Ramp
**Take:**
- Restrained palette + generous whitespace for finance screens
- Calm transactional surfaces

**Leave:**
- Gold/luxury banking aesthetic (we're not a private bank)

---

## 4. Agentic software

For Agent Observatory and the AI-reasoning surfaces. This is the most novel design problem — there are no fully-formed conventions to copy yet.

### Claude (Desktop, Console, claude.ai)
**Take:**
- Tool-use expansion blocks as "embedded sub-actions" — direct inspiration for our `ToolCall` component
- Streaming response rendering (the typing-on cursor)
- Generative UI / inline interactive widgets — reserve for future, but the pattern of "inline rich content within agent output" is the model
- Programmatic Tool Calling concept — agents orchestrate tools through code; reflected in how our `AgentTrace` shows downstream

**Leave:**
- Chat-bubble styling for agent output (our agents are NOT chatting)
- "Hi! How can I help?" copy

**Source:** Anthropic Engineering blog "Advanced Tool Use"; claude.ai

### Cursor (IDE)
**Take:**
- Agents as managed processes — visible in sidebar, manageable as objects, can run "plans" multi-step strategies. We adapt this to "agents are visible in the Roster column of Observatory"
- Multi-agent decomposition pattern (main agent + specialized subagents) — relevant for our debate orchestration UX
- Aggregated multi-file diffs for review — relevant if we ever ship a "multi-profile change review" feature

**Leave:**
- Editor-specific UI (we are not an IDE for our users)

### Perplexity (Pro Search)
**Take:**
- Plan-then-execute pattern with intermediate progress display — reference for how we show debate rounds and multi-step agent plans
- "Show steps" expandable sections (we adapt to AgentTrace's collapsible sections)
- The UX insight that *users tolerate latency much better when they can see intermediate progress*

**Leave:**
- Search-result chrome
- Citations (different problem domain)

### Replit Agent / Devin / Lovable / Bolt / v0
**Take (selectively):**
- The general pattern of "agent does work autonomously, user can intervene or watch"
- Visual editor + chat unified workspace concept (Replit Agent 4) — but we deliberately *don't* unify; agents are observers, not interlocutors

**Leave:**
- The "AI app builder" aesthetic — Praxis is NOT an app builder
- Generic shadcn/ui-on-Tailwind look (this is the "AI default" we explicitly avoid)

### Multi-agent debate / OrchVis (academic)
**Take:**
- Hierarchical goal alignment, layered visualization, conflict resolution
- The Planning Panel concept — when agents conflict, surface the conflict explicitly (we adopt for `DebatePanel`)
- Summary pane with high-level rationales + proposed resolutions + predicted future states
- Jury-room metaphor (multiple positions consolidated by an orchestrator)

**Leave:**
- Academic chrome / dashboard-specific patterns

**Source:** OrchVis paper (arxiv.org/html/2510.24937), AI Debate Arena examples

---

## 5. Cross-cutting (mood/aesthetic, not structural)

These are *mood* references — they shape the feel without dictating composition.

| Source | What it lends |
|---|---|
| Bloomberg terminal (across the trading floor) | "Illegible from far away, perfectly clear up close" — the discipline of dense legibility |
| Aviation glass cockpits | Emergency control aesthetic for Risk Control |
| Tufte's *The Visual Display of Quantitative Information* | Data-ink ratio thinking; chart simplicity |
| Edward Tufte sparklines | The minimal-line-no-axis treatment in data-display.md |
| Notion (calm aspects only) | Document-feel for Calm mode pages |
| Arc browser (Browse for Me) | One way of presenting AI-mediated outputs without chat-shape |

---

## 6. Anti-references — what NOT to look like

Useful to keep visible. If a generated screen *looks like* any of these, that's a problem.

- Coinbase consumer
- Robinhood (any era)
- Binance home/marketing
- Generic shadcn/ui defaults
- Material 3 admin templates
- Bootstrap admin themes
- Any "AI app builder" default
- Glassmorphism trend (the entire 2022–2024 cycle)
- "Web3" glow / neon
- Tailwind UI marketing components

If the harness defaults toward any of these, that's the symptom of insufficient anchoring — re-read `01-design-philosophy.md` and one of the Stitch prompts to re-anchor.
