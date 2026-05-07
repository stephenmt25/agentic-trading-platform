# Surface Spec — Agent Observatory

**Mode:** COOL (HOT when watching live)
**URL:** `/agents/observatory?focus={agent_id}&since={iso}`
**Backed by:** `analyst`, `debate`, `ta_agent`, `regime_hmm`, `sentiment`, `slm_inference`
**Frequency:** the user spends 15–25% of their session here, esp. during anomalies
**Density:** medium

---

## 1. Layout

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ◀▶ 🤖 Agent Observatory                                                  [search]│
│ ◉ live  filter: ⊕ all agents  ⏱ since: last 1h  symbol: BTC-PERP                │
├──────────────┬─────────────────────────────────────┬─────────────────────────────┤
│              │                                       │                              │
│   AGENT      │              EVENT STREAM             │       FOCUS PANEL           │
│   ROSTER     │       (chronological, virtualized)    │                              │
│              │                                       │  (selected agent's          │
│ ⊡ ta         │   ┌─ AgentTrace ─────────────┐       │   detail — full trace,      │
│ ⊡ regime     │   │ regime_hmm  14:32:01      │       │   reasoning stream,        │
│ ⊡ sentiment  │   │ regime: choppy 0.71       │       │   tool calls, downstream   │
│ ⊡ slm        │   └────────────────────────────┘       │   wiring)                   │
│ ⊡ debate     │   ┌─ AgentTrace ─────────────┐       │                              │
│ ⊡ analyst    │   │ ta_agent  14:31:58       │       │                              │
│              │   │ signal: long(weak)        │       │                              │
│              │   └────────────────────────────┘       │                              │
│              │                                        │                              │
│              │   ┌─ DebatePanel ────────────┐         │                              │
│              │   │ topic: open BTC long?     │         │                              │
│              │   │ round 3/5  ► live         │         │                              │
│              │   └────────────────────────────┘         │                              │
│              │                                        │                              │
└──────────────┴─────────────────────────────────────┴─────────────────────────────┘
```

Three-column: 220px left (agent roster + filter facets), flexible center (event stream), 460px right (focus panel for whichever event/agent is selected).

When no event is selected, the focus panel shows a *summary dashboard*: per-agent status cards, current debate state, regime probabilities ConfidenceBar, sentiment last 24h.

---

## 2. The agent roster

Each entry is `[AgentAvatar | name | StatusDot | last-emit time]`. Click toggles "include this agent" filter. Right-click opens "go to agent dashboard" / "silence this agent's emits" / "open in canvas."

Status dots:
- `live` — emitted within configured liveness window (e.g., 5 min)
- `idle` — emitted before that window
- `errored` — last emission was an error
- `silenced` — user has muted this agent's stream

---

## 3. The event stream (center column)

A virtualized vertical feed of AgentTrace and DebatePanel cards, sorted by `emitted_at` descending. Filters at top: agent multiselect (mirrors roster checkboxes), time range, symbol selector, free-text search across reasoning bodies.

**Behavior:**
- New traces stream in at top with a 240ms slide-in (COOL mode allows this expression).
- Auto-scroll lock: pinned at top by default; user scrolls down → lock disengages, "▼ N new" pill appears.
- Each card has `[focus]` (opens in right panel), `[trace ▸ canvas]` (jumps to canvas), `[copy raw json]` (debugging).

---

## 4. The focus panel (right column)

When a trace is selected, this shows:
1. **Header** — AgentAvatar + name + emit time + symbol
2. **Inputs** — full input payload, syntax highlighted
3. **Reasoning** — ReasoningStream of the model's output, including ToolCall blocks if present
4. **Output** — final structured output (typed)
5. **Confidence** — ConfidenceBar(s) for any probabilistic outputs
6. **Downstream** — list of nodes/agents that consumed this output, with timestamps
7. **Actions** — `silence next N`, `flag for review`, `add to test fixtures`, `re-run with edits`

When the user selects a DebatePanel card, focus panel shows the round-by-round breakdown with each agent's contribution as a sub-card, plus an `intervene` action (user types/picks an override decision).

---

## 5. The summary dashboard (default focus panel)

When nothing is selected:

```
┌── current state ────────────────────────────────────┐
│  REGIME (regime_hmm)                                │
│    [trending 18% │ choppy 71% │ reversal 11%]       │
│                                                      │
│  SENTIMENT (sentiment)                               │
│    score: +0.32  (24h moving avg ↑ +0.08)           │
│    ▁▂▃▄▅▆▆▅▆▇▆▅▄▃▃▂▂▃▄ (sparkline 24h)             │
│                                                      │
│  TA SIGNAL (ta_agent)                                │
│    long(weak) since 14:21 | confluences: 3/7         │
│                                                      │
│  ACTIVE DEBATE                                       │
│    "open BTC-PERP long now?" round 3/5 — live       │
│    [ tap to focus ]                                 │
│                                                      │
│  AGENT HEALTH                                        │
│    5 live · 0 idle · 0 errored                      │
└──────────────────────────────────────────────────────┘
```

Each section is a card; click any to enter focus mode for that agent.

---

## 6. Live behaviour

- Traces stream in via WebSocket from each agent's pub channel (`pubsub:agent_signals` or per-agent).
- Filtering is client-side (we keep the most recent ~5,000 events in memory; older fall off but remain queryable via Postgres/archiver for the time range filter).
- DebatePanel rounds animate in as the orchestrator emits them; user can pause the whole panel without pausing the underlying debate service.

---

## 7. Keyboard map

| Key | Action |
|---|---|
| `J` / `K` | Down / Up through event stream (vim-style) |
| `Enter` | Focus selected event in right panel |
| `F` | Focus filter facets |
| `Cmd+1…6` | Toggle each agent in the roster |
| `O` | Override active debate (when a DebatePanel is focused) |
| `Cmd+K` | Command palette |

---

## 8. The intervention path

This is the most ethically loaded UX in Praxis. The user can override an agent's output before downstream consumers act on it. Specifically:

- **Pre-execution debate override** — user presses `O` on a live DebatePanel; modal opens with "force decision: long / short / hold" with an optional rationale text. Submitting writes a `user_override` event that downstream consumers (strategy_eval, execution) honor. The override is *audited* — it appears in the analyst archive permanently, attributed to the user.

- **Silence next N emissions** — for noisy agents during atypical conditions, user can silence the next N emissions. Default N=5. While silenced, downstream consumers receive the *last cached output* with a `cached_until` flag.

- **Replay with edits** — for retro analysis: take a past trace, edit the input, re-run the agent against it. Result is shown alongside original; never affects production.

These actions are *not* presented as casual buttons. They are deliberate choices with audit trails. The override modal includes the rationale text field as required (not optional).

---

## 9. Edge / failure cases

| Case | Treatment |
|---|---|
| Agent service crash | StatusDot `errored`; last-good output stays usable downstream with a warning banner; "restart agent" action visible to admin users |
| Debate orchestrator timeout | DebatePanel shows `errored` state + "synthesis unavailable; last round shown is final"; downstream does not act on a partial debate |
| ReasoningStream stalls mid-token | Show a "stalled — N seconds" indicator after 8s; offer "abort and retry" |

---

## 10. Empty states

| Region | Empty state copy |
|---|---|
| No agent activity yet | "No agent emissions in the last hour. Profile may be paused or agents idle." (link to canvas) |
| Filter excludes everything | "No events match these filters." + "Clear filters" button |
| No active debate | "No debate currently active. Debates trigger when ≥2 agents disagree about a decision." |
