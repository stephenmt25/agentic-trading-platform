# Agentic Components

This is the inventory that doesn't exist in conventional trading platforms. These components make the AI reasoning of Praxis legible — borrowing patterns from Cursor, Claude, Perplexity, and adapting them to a trading context where the user is *not* in a chat conversation but supervising an autonomous system.

> **Core stance:** the user is *watching the agents work*, not *talking to them*. The default reading order is: signal → reasoning → decision → outcome. Chat is a peripheral input mode, not the primary surface.

---

### AgentTrace
**Used on:** Agent Observatory (primary), Hot Trading (collapsed inline), Pipeline Canvas (per-node detail)

**Anatomy:**
```
┌── [agent-avatar] regime_hmm  ▸  emitted at 14:32:01.234 ──┐
│                                                              │
│  ┌── input ──────────────────────────────────────────────┐  │
│  │ candles: BTC-PERP 1m × 240   features: returns, rv    │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌── reasoning (collapsed) ──────────────────────────────┐  │
│  │ ▸ probability shift detected: trending → choppy        │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌── output ──────────────────────────────────────────────┐  │
│  │ regime: choppy    p(trending)=0.18   p(choppy)=0.71    │  │
│  │ p(reversal)=0.11                                       │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌── downstream ─────────────────────────────────────────┐  │
│  │ → strategy_eval (canvas node #4)                       │  │
│  │ → debate (next round)                                  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

A trace is one *atomic event*: an agent received an input, produced an output, and that output went somewhere. Each section is collapsible; default for HOT mode is everything collapsed except output. Default for Observatory is everything expanded.

**States:**
- `streaming` — output box has a typing-on cursor; reasoning box shows live tokens
- `complete` — full content, timestamp final
- `errored` — left bar `ask.500`, error in output box
- `superseded` — dim 60% if a newer trace from the same agent exists

**Tokens:** uses agent identity color in the avatar ring + the section header underline. Otherwise neutral. Type `scale.body-dense` for content, `scale.code` for raw JSON output.

**Variants:**
- `density`: `compact` (just header + output), `standard` (default), `expanded` (all sections shown)
- `liveCursor`: bool — streaming indicator on/off
- `linkable`: makes section headers click-through to canvas/observatory

**Accessibility:** trace is `role="article"` with heading hierarchy. Each section is `<details>`/`<summary>` so keyboard users can collapse/expand with Space.

**Don't:**
- Render the reasoning content as a chat bubble. It is *not* a message; it is a derivation.
- Use the agent identity color anywhere except the avatar ring + section header underline. The trace body must remain neutral so multiple traces can coexist on screen.
- Auto-scroll to the newest trace when the user has scrolled up — show a "▼ N new" badge instead.

**Reference:** Claude tool-use expansion blocks; Cursor's agent log; Perplexity's "show steps" pattern.

---

### ReasoningStream
**Used on:** Agent Observatory, Pipeline Canvas (when viewing an LLM-backed node), Hot Trading (Cmd+K agent-query results)

**Anatomy:** pane that shows tokens streaming from an LLM as they arrive. Subtle `▍` cursor. Markdown rendered progressively; code blocks lock width as they finish.

**States:**
- `streaming` — cursor active, type-on at backend rate (no artificial delay)
- `paused` — cursor visible but flashing slow; "paused — click to resume"
- `done` — cursor removed, full content; meta line shows "1.2s · 287 tokens · sonnet-4-6"
- `errored` — partial content + error footer

**Tokens:** type `scale.body-dense`, `--font-sans` for prose, `--font-mono` for code, code block bg `--bg-raised`, cursor color `--color-accent-500`.

**Variants:**
- `mode`: `prose` (default) / `json` (syntax highlighted) / `xml-tags` (for tool-use markup)
- `inline` (constrained to 1 line + ellipsis, useful in Hot mode)
- `with-thinking` — when the model emits `<thinking>` blocks, render them in a slightly dimmed inset, collapsible

**Don't:**
- Add typing-on animation if the content arrives all at once (e.g., from cache) — that's deceptive.
- Let the stream pane reflow content above as more arrives. Reserve space; lock the cursor at bottom.

**Reference:** Claude streaming responses; Anthropic Console; the `<thinking>` rendering convention from Claude's extended thinking.

---

### ToolCall
**Used on:** Agent Observatory, Reasoning streams that include tool use

**Anatomy:**
```
┌─[ ⚙ tool · query_market_data ] ──── 23ms ──┐
│  ▸ args: { symbol: "BTC-PERP", lookback: "1h" }
│  ▸ result: { rows: 3600, latest: 42318.27 }   ✓
└──────────────────────────────────────────────┘
```

A condensed inline block within a ReasoningStream that represents one tool invocation. Header: gear icon + tool name + duration. Body collapsed by default; click to expand args and result.

**States:**
- `pending` — gear spinning, dimmed body
- `complete` — checkmark in `bid.500`, normal body
- `errored` — `✗` in `ask.500`, error in body

**Tokens:** card bg `--bg-raised`, header type `scale.caption` mono, body `scale.code`, success `--color-bid-500`, error `--color-ask-500`.

**Don't:** show tool args in plaintext as one line if they exceed ~40 chars — break to multi-line JSON. The reader's eye should never have to track sideways through long inline JSON.

**Reference:** Claude Code's tool-use blocks; Cursor's tool-call rendering.

---

### DebatePanel
**Used on:** Agent Observatory (the `debate` service surface)

**Anatomy:** a multi-agent argument visualization, custom to Praxis.

```
┌── topic: should we open BTC-PERP long now? ──── round 3/5 ──┐
│                                                                │
│  [agent-ta avatar] ta_agent          for                       │
│  ► trend confirmed on 1h, momentum positive                    │
│                                                                │
│  [agent-regime avatar] regime_hmm    against                   │
│  ► regime is choppy; trend signals are unreliable here          │
│                                                                │
│  [agent-sentiment avatar] sentiment  for (weak)                │
│  ► social sentiment +0.32, but volume thin                     │
│                                                                │
│  [agent-debate avatar] orchestrator  synthesis                 │
│  ► 0.62 confidence in long; suggest reduced size (0.4x)        │
│                                                                │
│  [▶ open round 4]   [⏸ pause debate]   [⛔ override decision]    │
└────────────────────────────────────────────────────────────────┘
```

Each agent contribution: avatar, agent name, stance label (`for` / `against` / `neutral` / `synthesis`), reasoning summary (one line, click to expand to full ReasoningStream).

**States:**
- `live` — current round streaming, active agent's row pulses faintly
- `paused` — orchestration halted, override button prominent
- `superseded` — entire panel dims 50%, header shows "superseded by round X" link

**Tokens:** each agent's row uses its identity color *only* for the avatar ring and stance label underline. Body text remains neutral. Stance labels use semantic colors: `for` → `bid.400`, `against` → `ask.400`, `neutral` → `neutral.400`, `synthesis` → `accent.300`.

**Variants:**
- `view`: `chronological` (default — by agent emission order) / `byStance` (groups for/against/neutral) / `graph` (force-directed, nodes = agents, edges = agreements/disagreements)
- `interventionEnabled`: shows override controls
- `embedded`: compact form for inclusion as a card on Hot Trading or Canvas

**Accessibility:** the orchestrator's synthesis must be reachable with a single Tab from focus on the panel — the user might be trying to override quickly. Keyboard shortcut `O` opens override modal when panel is focused.

**Don't:**
- Render the debate as a chat thread. Debates aren't conversations — they're parallel positions consolidated by an orchestrator.
- Make agent stances ambiguous. `for`/`against`/`neutral`/`synthesis` is the contract. If an agent is undecided, that's `neutral`.
- Auto-execute on synthesis without surfacing the override window. The user must have time to interrupt — a configurable "decision delay" (default 3s) gives them a chance.

**Reference:** OrchVis (academic — multi-agent oversight UI); Anthropic's policy debate visualizations; "AI Debate Arena" patterns; jury-room metaphor.

---

### ConfidenceBar
**Used on:** wherever a probabilistic output appears

**Anatomy:** horizontal stacked bar showing probability mass across discrete outcomes. Examples:
- regime_hmm: `[trending 18% │ choppy 71% │ reversal 11%]`
- direction prediction: `[long 0.62 │ neutral 0.18 │ short 0.20]`

Each segment labeled with its probability. Width proportional. Tallest segment label `fg.primary`; others `fg.muted`.

**Tokens:** segment colors are agent-specific (regime_hmm uses 3 violet shades; direction uses bid/neutral/ask).

**Variants:**
- `withDistribution` — adds a small KDE/histogram below for continuous outputs
- `historic` — light backdrop layer showing where the distribution was 1h/24h ago, for comparison

**Don't:** display a single confidence percentage when the underlying is multi-modal. P5 ("confidence intervals, not point estimates"). A single number throws away information.

---

### AgentSummaryPanel
**Used on:** Hot Trading (right column, bottom)

A composite, surface-level affordance specifically for Hot Trading — *not* a generic primitive. It exists because Hot Trading needs an at-a-glance reasoning summary without sending the user to Observatory.

**Anatomy:**
```
┌── AGENTS — recent ──────────── see all ▸ ─┐
│  [AgentTrace density="compact"] × 3        │
│  [DebatePanel embedded] × 0–1              │
└────────────────────────────────────────────┘
```

A header row with caption "AGENTS — recent" left-aligned and a "see all in Observatory ▸" link right-aligned. Body is up to 4 child cards rendered in compact density:
- Up to 3 most-recent `AgentTrace` cards from agents the active profile uses.
- Up to 1 active `DebatePanel` (in `embedded` variant) if a live debate exists for the current symbol.

Sort: newest first. Older traces age out as new ones arrive (FIFO).

**States:**
- `default` — populated with current traces
- `empty` — "No agent emissions for this symbol in the last 5 minutes." (one-line, muted)
- `agents-paused` — "Agents are paused for this profile. Resume in Pipeline Canvas." (link to canvas)
- `service-degraded` — "Agent feed degraded — showing last cached output (3m ago)."

**Tokens:** uses child component tokens; container has `--space-3` internal padding, `--border-subtle` between traces, `--bg-panel` background.

**Variants:**
- `maxItems`: 3 (default) / 4 (when no active debate) / custom
- `symbolFilter`: bound to current Hot Trading symbol; pass `null` for global feed

**Don't:**
- Render in `expanded` density — Hot Trading must keep this panel ≤300px tall.
- Auto-scroll on new emissions — too jittery in HOT mode. Snap-replace oldest.
- Add intervention controls here — those live on Observatory. The Hot Trading panel is read-only by design.

**Reference:** Linear's "activity" sidebar feed; Stripe's recent-events compact rendering.

---

### AgentAvatar
**Used on:** all agentic surfaces

**Anatomy:** circle 24/32/40, glyph centered. Ring 1.5px in agent identity color. Glyphs are abstract (no faces, no AI clichés like brains/sparkles):
- `ta_agent` — segmented bar (sparkline-like)
- `regime_hmm` — three connected nodes (states)
- `sentiment` — wave shape
- `slm_inference` — speech-bracket
- `debate` — three radiating lines (synthesis)
- `analyst` — pen-on-page

**Tokens:** ring `--color-agent-{name}`, glyph `--fg-primary`, bg `--bg-panel`.

**Variants:**
- `status`: small dot bottom-right — `live`, `idle`, `errored`, `silenced`
- `withName`: shows name to the right (`compact` cards) or below (`expanded` profiles)

**Don't:** use anthropomorphic icons (faces, robot heads). The agents are *not* characters. They are tools. Iconography reflects function, not personality.
