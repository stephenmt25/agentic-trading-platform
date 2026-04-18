# Analysis Page — Chart Enhancement Plan

> Follow-up to the synced-axis work landed in the analysis page. This plan breaks the next batch of pattern-matching aids into independent increments, each of which can ship on its own.
>
> **Guiding principle**: every visual addition must come with a user-facing explanation (InfoTooltip or inline copy) that tells the trader how to *read* the signal. A feature that looks cool but doesn't teach the eye what to look for is dead weight.

## Current baseline (already shipped)

- Synchronized x-axis: zoom/pan on the candle chart drives the score chart's x-domain.
- Bidirectional crosshair: hover either chart, both highlight the same moment.
- InfoTooltips on the page header, Agent Scores header, each agent badge, and the weights panel.

Sync state lives in `useAnalysisStore` (`hoveredTime`, `hoverSource`, `visibleRange`). New features should reuse that store rather than introducing parallel state.

---

## Increment 1 — Signal markers on candles

**What:** Render small arrows/dots directly on candles where an agent's score crosses a configurable threshold (default ±0.5). Up-arrow below the candle for bullish crossing, down-arrow above for bearish.

**Why:** Collapses the "look up at the score line, then back down at the candle, then compare x-positions" loop into a single glance. Instantly answers "did this signal precede this candle's move?"

**How:**
- Compute markers in a `useMemo` from `scores` + configurable threshold per agent.
- Pass to `PriceChart` via a new prop `markers: SeriesMarker[]`.
- Use lightweight-charts' `createSeriesMarkers(candleSeries, markers)` helper (v5.1 API — replaces the old `series.setMarkers()` which was deprecated in v5).
- Color per agent, matching the score line colors.
- Threshold configurable from OverlayToggles (slider or fixed preset: ±0.3, ±0.5, ±0.7).

**User explanation:** InfoTooltip near the marker-threshold control:
> "Arrows mark where an agent's score crossed the threshold into bullish (▲) or bearish (▼) territory. Look for arrows that cluster just before a sharp move — that's the agent leading price. Arrows that cluster just after a move mean the agent is reacting, not predicting."

**Effort:** ~2 hours. **Risk:** Low — additive, no API changes.

---

## Increment 2 — Score-intensity heatstrip

**What:** A 12-16px-tall horizontal band rendered between the candle chart and the score line chart. Each column represents the same time bucket as the chart above it, colored by aggregate score intensity: saturated green = strong long consensus, saturated red = strong short consensus, grey/faded = weak or conflicting.

**Why:** Lets the eye scan 500 candles of agent state without reading four overlapping lines. Answers "what was the overall bias here?" faster than the line chart.

**How:**
- New component `ScoreHeatstrip.tsx` using a flat SVG or canvas row.
- Aggregate = weighted mean of visible agent scores at each timestamp, using current weights from the store.
- Color interpolation: `-1 → #ef4444`, `0 → transparent`, `+1 → #22c55e`. Alpha = `abs(score)`.
- Shares x-domain with the other charts via `useAnalysisStore.visibleRange` — same sync contract.
- Hover shows a tooltip with the component scores.

**User explanation:** InfoTooltip on the strip header:
> "Color intensity = how strongly agents agreed on direction. Deep green = strong long consensus; deep red = strong short. Faded grey = agents are divided or neutral. Scan the strip like a heartbeat: long uninterrupted bands of one color often correspond to trending regimes; rapid flips signal chop."

**Effort:** ~4 hours. **Risk:** Low — new component, no changes to existing charts.

---

## Increment 3 — Agent-disagreement shading

**What:** Translucent vertical bands on the candle chart covering time windows where cross-agent variance exceeds a threshold (e.g., `std(scores) > 0.4`). Think of it as "agents are fighting here."

**Why:** High disagreement often precedes regime changes or reversals. Highlighting those windows teaches the eye to watch for them.

**How:**
- Compute disagreement per timestamp from the score array.
- Use lightweight-charts `addSeries(AreaSeries)` with a custom price format, or draw overlaid via absolute-positioned `<div>`s sized from the chart's `timeScale().timeToCoordinate()`.
- Band opacity scales with variance magnitude.

**User explanation:**
> "Shaded bands mark windows where agents strongly disagreed. Disagreement often precedes regime changes — when a consensus breaks down, it's sometimes the early signal that the old regime is ending. Watch what price does in the bar or two after a shaded band ends."

**Effort:** ~3 hours. **Risk:** Medium — getting the overlay to pan/zoom cleanly with the chart takes care.

---

## Increment 4 — Lead-lag correlation panel

**What:** A small strip (similar height to the score chart) showing rolling cross-correlation between each agent's score and forward N-bar returns, at shift values [-5, -3, -1, 0, +1, +3, +5] bars. Peak at shift < 0 = agent lags price; peak at shift > 0 = agent leads price.

**Why:** Moves past "do the shapes look similar?" into "is this agent actually predictive?" This is the honest check a quant would run before weighting an agent.

**How:**
- New endpoint or client-side compute: `correlation(score[t-k:t], return[t+1:t+1+N])` over rolling windows.
- New component `LeadLagPanel.tsx` — small heatmap (agents × shift values), color = correlation strength.
- Updates on symbol/timeframe change, shares visible range.

**User explanation:**
> "Each cell is how well an agent's score at time T predicts price change N bars later. Right-of-center peaks (positive shift) = the agent is a leading indicator. Left-of-center peaks = it's reacting to price that already moved. Columns near zero that are all dim = the agent isn't adding signal over the window you're looking at."

**Effort:** ~1 day. **Risk:** Medium — needs correlation compute (client-side is fine for 500 bars × 4 agents × 7 shifts).

---

## Increment 5 — Score → forward-return scatter

**What:** Small side panel (or modal): scatter plot with agent score on x-axis, forward N-bar return on y-axis, one dot per bar. Color fades with age (recent = bright, old = faded). One panel per agent, or a facet grid.

**Why:** Shows predictive power at a glance. A tight diagonal = predictive agent; a cloud = noise. This is the single most honest visualization of "does this signal work?"

**How:**
- Recharts `ScatterChart`. Facet by agent with 2×2 grid on the analysis page footer, or a dropdown to pick one.
- Forward return = `(close[t+N] - close[t]) / close[t]`, N configurable (default 3 bars).
- Hover a dot highlights the corresponding bar on the main candle chart (reuse `setHoveredTime` from the store).

**User explanation:**
> "Each dot is one bar: the agent's score at that bar (x) vs. what price did in the next N bars (y). A tight line sloping up-and-to-the-right means the agent is predictive — high scores really did precede gains. A shapeless cloud means the agent isn't adding signal at this timeframe. Change timeframe to see if the agent works better on longer or shorter horizons."

**Effort:** ~1 day. **Risk:** Low — isolated recharts component.

---

## Cross-cutting — Onboarding / first-time guide

The analysis page now has enough instrumentation that a first-time user will miss the synced-axis + crosshair behavior. Options, ordered by effort:

### Option A: One-time banner (lightweight)
Dismissible banner above the charts on first visit: "Tip: hover either chart to sync crosshairs. Zoom one, both follow." Store dismissal in `localStorage` under `praxis.analysis.tipDismissed`. **~30 min.**

### Option B: Welcome overlay (matches Monitor pattern)
Mimics the Monitor page's welcome card from commit 92abfb1 — a centered card with 3-4 labelled panels pointing at the actual chart regions: "Candle chart", "Agent scores (synced axis)", "Hover to sync crosshair", "Weights below". Dismissed on first interaction. **~2 hours.**

### Option C: Interactive tour
Multi-step overlay (shepherd.js or hand-rolled) that highlights each region with explanatory copy. Over-engineered for 4-5 concepts — skip unless the feature set grows. **~1 day.**

**Recommend Option B** — matches existing pattern, higher signal than a banner, low maintenance.

---

## Suggested order

1. **Increment 1 (markers)** — highest signal-to-effort; immediately makes the sync work feel useful.
2. **Option B onboarding** — ship alongside 1, so new users find the markers.
3. **Increment 2 (heatstrip)** — complements markers; gives a 10,000-foot view.
4. **Increment 5 (scatter)** — the honesty check. Gates further agent-weight tuning work.
5. **Increment 4 (lead-lag)** — deeper than scatter; add once users are asking the right questions.
6. **Increment 3 (disagreement bands)** — nice-to-have; lowest priority.

Each increment should land with its InfoTooltip copy reviewed — the text above is a starting point, not final copy.
