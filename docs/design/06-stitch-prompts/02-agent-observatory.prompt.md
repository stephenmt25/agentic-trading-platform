# Stitch Prompt — Agent Observatory Surface

## VIBE

Design a screen that feels like watching a panel of expert analysts reason out loud, captured calmly and precisely. The same dim instrumentation aesthetic as a Bloomberg terminal, but with the expressive presence of Claude's tool-use blocks made spatial. The viewer is *listening in* on the AI's reasoning, not chatting with it. Every event is timestamped, attributed, and traceable. The screen should feel like a research notebook crossed with a flight recorder — present, calm, and rigorous.

## DETAILED PROMPT

Generate a desktop AI agent monitoring UI named "Agent Observatory" for a derivatives trading platform called Praxis. Viewport 1440×900px.

**Background, typography, color rules:** identical to the Hot Trading prompt. Same #0b0b0d background, same Inter font, same neutral/bid/ask/accent palette. The only addition: agent identity colors used SPARINGLY — only on agent avatar rings and header underlines:
- ta_agent: blue #3b82f6
- regime_hmm: violet #a855f7
- sentiment: pink #ec4899
- slm_inference: teal #14b8a6
- debate: orange #f97316
- analyst: lime #84cc16

**Layout — three columns on a 1440×900 viewport:**

1. **Far-left rail** (56px, same six-icon stack as Hot Trading; 🤖 robot icon highlighted with violet 2px left bar)

2. **Agent roster column** — 220px wide. Heading "AGENTS" in 11px caption. Below, six rows, each: small 24px circular avatar with identity-color ring + abstract glyph in the center (NOT a cartoon face — abstract shapes representing function), agent name in 13px medium, status dot (green=live, gray=idle, red=errored), small relative timestamp "14:32:01". Below the roster, a "FILTERS" heading and three filter facet rows: "Time range: last 1h ▾", "Symbol: BTC-PERP ▾", "Search ⌕".

3. **Event stream — center column** — flexible width. Top bar with the six chrome status pills (live, regime, latency, kill-switch, agent count, PnL). Below: a vertical scrollable list of "AgentTrace" cards, each card structured as:
   - Card header: agent avatar with identity-color ring, agent name, "▸" expand chevron, emit timestamp "14:32:01.234"
   - Card has a thin vertical bar on the LEFT in the agent's identity color (so the eye can scan agent attribution)
   - Card body: three labeled subsections (collapsible): "input" (showing "candles BTC-PERP 1m × 240"), "reasoning" (one-line: "▸ probability shift detected: trending → choppy"), "output" (the structured result, e.g., "regime: choppy   p(trending)=0.18   p(choppy)=0.71   p(reversal)=0.11" rendered with the probabilities AS A HORIZONTAL STACKED BAR — three segments showing the relative probabilities, with each segment labeled).
   - Card footer: "downstream → strategy_eval (canvas node #4) → debate (next round)" with the arrows in muted text.

   Show 4 cards stacked, alternating agents:
     a. regime_hmm card showing the probability bar
     b. ta_agent card showing "signal: long(weak)" with three small confluence indicators (3/7 green, 4 muted)
     c. **A larger DebatePanel card** — different visual treatment: a banded card with an orange (debate) accent, header "topic: should we open BTC-PERP long now?  ── round 3/5  ►live", body with FOUR rows representing each agent's contribution — each row shows: agent avatar, agent name, stance label ("for" in emerald, "against" in red, "for (weak)" in muted, "synthesis" in indigo), and a one-line argument (e.g., "trend confirmed on 1h, momentum positive"). Below the rows, a footer with three buttons: "[▶ open round 4]   [⏸ pause debate]   [⛔ override decision]".
     d. sentiment card showing a small sparkline of last 24h sentiment scores.

4. **Focus panel — right column** — 460px wide. Header showing the currently-focused trace: agent avatar, agent name, emit time, symbol. Below, vertical sections:
   - "INPUTS" — small JSON block in mono font on a #18181b panel
   - "REASONING" — a "ReasoningStream" pane: prose text with a typing-on cursor at the end (a thin vertical bar `▍` in indigo). Show 2-3 lines of model output text, ending mid-sentence with the cursor.
   - **A "TOOL CALL" inline block** within the reasoning: a card with header "[⚙ tool · query_market_data] ── 23ms", showing args as JSON and a green checkmark for success.
   - "OUTPUT" — the structured output, with a CONFIDENCE BAR underneath (horizontal stacked bar with three labeled probabilities)
   - "DOWNSTREAM" — list of consumers
   - "ACTIONS" row — small buttons: silence next 5, flag for review, add to test fixtures, re-run with edits

**Visual character:**
- All cards have flat #0f0f12 backgrounds with 1px #18181b borders, 6px corners
- The chevrons (▸) for collapsing sections are 12px and muted
- The DebatePanel is the visually richest element — it should be obviously the densest information node
- No emoji, no decorative imagery, no illustrations
- ReasoningStream cursor blinks (drawn at one moment in the static image — show the bar present)

## REFERENCE NOTES

Priority reference uploads:
1. `08-reference-library/images/05-claude-tool-use.png` — Claude tool-call expansion blocks
2. `08-reference-library/images/06-cursor-agent-log.png` — Cursor's agent execution log
3. `08-reference-library/images/07-perplexity-steps.png` — Perplexity Pro Search step display
4. `08-reference-library/images/03-linear-app.png` — for typography rhythm

## ANTI-PROMPT

```
DO NOT generate:
  - chat bubbles for agent output (this is NOT a chat UI)
  - faces or anthropomorphic icons for agents (abstract glyphs only)
  - rainbow gradients across agents
  - generic "AI assistant" purple-and-stars aesthetic
  - oversized "thinking..." illustrations
  - left-aligned chat avatars (the agents are NOT speaking; they are emitting)
```
