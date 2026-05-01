# 2nd Brain — Roadmap (PR2 → PR5)

> **Status:** Plan, awaiting approval. No code changes yet.
> **Predecessor:** PR1 — The Ledger (see `docs/SECOND-BRAIN-PR1-PLAN.md`). PR1 is pure observability — every trade is reconstructable end-to-end, but no decision logic changes.
> **This document defines the path from "we can replay the past" to "the system improves itself based on what the past tells us."**

The order matters: each PR depends on data the prior one produced. PR1 → PR2 → PR3 compound. PR4 and PR5 can run in parallel once PR3 lands.

---

## PR2 — Insight Engine (read the ledger)

### Goal
Compute and expose, per profile and per agent: *"would this signal have been profitable?"* and *"which gate is doing useful work versus just blocking volume?"* Today we have the data; we have no consumer.

### Behavior change
**None to live trading.** PR2 only reads. New endpoints, new dashboard panels, new periodic reports. Decision logic is unchanged.

### Concrete deliverables

#### 1. Gate efficacy report
For each gate (abstention, circuit breaker, regime, HITL): take the *blocked* set, look up what the market did over the next N candles, and ask "would this trade have been a winner had it passed?"
- If abstention's blocked-set has a similar realized win rate to its passed-set, abstention isn't filtering — it's throttling.
- If a gate's blocked-set has a *better* realized win rate than its passed-set, the gate is filtering out winners — it's miscalibrated and should be relaxed.

Implementation sketch:
- New worker `services/analyst/src/gate_efficacy.py` runs on a cadence (every 6h initially).
- Joins `trade_decisions` (entry candle + outcome) with `market_data_ohlcv` (next K candles).
- Computes "would-be P&L" assuming the gate had passed and we'd held until stop_loss / take_profit / time-out.
- Writes results to a new `gate_efficacy_reports` table.
- New endpoint `GET /agent-performance/gate-efficacy/{symbol}?profile_id=&window=` returns the latest report.
- New panel in the Performance Review drawer: "Gate Efficacy — last 7d / 30d."

#### 2. Agent attribution
At each EXECUTED decision, the score from each agent was X. Did decisions where TA agreed with sentiment perform better than disagreement? Better than TA-alone? Better than majority-vote among agents?
- Output a confusion-matrix-like view: rows = agent agreement patterns, columns = realized outcome.
- This is the data that justifies (or removes) any specific agent.

Implementation sketch:
- New worker `services/analyst/src/agent_attribution.py`.
- Joins `trade_decisions.agents` (each agent's score at decision time) with `closed_trades.realized_pnl_pct`.
- Bucketed by agent-agreement pattern (TA+SENT+DBT all bullish, TA bullish only, mixed, etc.).
- Endpoint `GET /agent-performance/attribution/{symbol}?profile_id=` already exists for trade attribution; extend to return the new agreement-pattern slice.
- Updates the existing `TradeAttributionPanel` to show agreement-pattern rows.

#### 3. Strategy-rule heatmap
Group closed trades by the *exact* condition set that matched them. Some rule combinations may carry the win rate; others may bleed money silently.
- Useful for users tuning their own strategies — "your `RSI<30 AND MACD>0` rule wins 62% on BTC but only 41% on ETH."

Implementation sketch:
- Worker reads `trade_decisions.strategy.matched_conditions` (already persisted in PR1's audit chain).
- Aggregates per-rule-fingerprint outcomes.
- Surfaces in `/strategies` page as a per-profile breakdown.

#### 4. Close-reason taxonomy
Today, all 25 closed trades have `close_reason = stop_loss`. That's a giant signal — either stops are too tight, or entry timing is uniformly bad. The ledger lets us slice by close reason × symbol × profile × regime.

Implementation sketch:
- New summary endpoint `GET /audit/close-reasons?profile_id=&window=`.
- Returns counts of `stop_loss / take_profit / max_holding / manual / kill_switch` over the window.
- New panel in Performance Review drawer.

### Acceptance test
After PR2 ships, this question can be answered from the dashboard alone:
> "Of the trades blocked by the abstention gate in the last 7 days, what fraction would have been profitable had they passed?"

If the answer comes back as a number (with a confidence interval), PR2 is done.

---

## PR3 — Adaptive weights (write back from the ledger)

### Goal
When PR2's metrics show agent X is consistently right and agent Y consistently wrong over the last N decisions, **update agent weights automatically.** This is where the system stops being a deterministic rules engine and starts being agentic.

### Behavior change
**This is the first PR that changes live trading.** The system will quietly retune its own gate thresholds and agent weights based on realized performance. Every change flows through a versioned `config_changes` log so it's reversible and visible.

### Concrete deliverables

#### 1. Weight tuner worker
- New worker `services/analyst/src/weight_tuner.py` runs every hour.
- Reads `closed_trades` joined with `agent_score_history` over a rolling window (default 30 days).
- Computes per-agent realized accuracy via EWMA — if TA's bullish score correlated with positive `realized_pnl_pct` 65% of the time but sentiment correlated only 50%, TA's weight goes up and sentiment's goes down.
- Writes new rows to `agent_weight_history`.
- The hot_path Analyst component (already reading from `agent_weight_history`) automatically picks up the new weights.

Bounds:
- Weight changes capped at ±5% per cycle to avoid oscillation.
- Minimum sample size before any weight change: 50 closed trades.
- Hard floors and ceilings on per-agent weights (e.g., never below 5%, never above 60% — no single agent can dominate).

#### 2. Gate calibrator
- Reads PR2's gate efficacy reports.
- If a gate's blocked-set has higher realized win rate than its passed-set for ≥3 consecutive cycles, propose relaxing the gate.
- Writes proposed changes to `config_changes` table with status `proposed`.
- Configurable: auto-apply, or require human approval via a new HITL-style flow.

Bounds:
- Threshold changes capped at ±10% per cycle.
- Hard guardrails (e.g., abstention floor of 30% to avoid letting everything through).

#### 3. Reversibility
- All weight + threshold changes flow through `config_changes` with timestamps and reasoning.
- New `/agent-config/history` endpoint shows the audit trail.
- One-click revert from the dashboard returns to a prior config snapshot.

### Acceptance test
After PR3 ships:
> "Without manual intervention, can the system improve win rate by ≥1% over a 14-day backtest replay where it weights agents based on their realized accuracy?"

This requires PR2's gate efficacy data + PR3's weight tuner running over historical data.

---

## PR4 — Profile auto-tuning (parallelizable with PR5)

### Goal
When a user's strategy has been losing for N days but a *neighbor* strategy (one indicator different) has been winning, surface the suggestion. Eventually, with consent, apply it.

### Behavior change
Surfaces suggestions to users; does not change live profiles without explicit consent.

### Concrete deliverables

#### 1. Profile suggestor
- Worker `services/analyst/src/profile_suggestor.py` runs daily.
- For each underperforming profile, generates a small set of micro-mutations (one indicator changed, one threshold shifted, etc.).
- Backtests each mutation against the last 30 days of market data using the existing `services/backtesting/`.
- Ranks by Sharpe / win rate / drawdown.
- Top-3 suggestions surface in the Strategies page with "Try this" buttons.

#### 2. Shadow profile mode
- A user can promote a suggestion to "shadow" — runs paper-only alongside the live profile.
- After K trades, the dashboard shows side-by-side performance.
- One-click "promote shadow → live" replaces the live profile (with rollback).

#### 3. Suggestion provenance
- Every suggestion logs: original profile, what mutation, what backtest produced what number, date generated.
- User can audit: "why did the system suggest changing my RSI threshold from 30 to 35?"

### Acceptance test
> "Given a profile that has lost money 3 weeks in a row, the suggestor produces at least one micro-mutation that beats it on a held-out backtest."

---

## PR5 — LLM-assisted post-mortems (parallelizable with PR4)

### Goal
Use the (now-hydrated) debate transcripts and decision context to generate human-readable explanations of why each trade won or lost. This is the "second brain" in the literal sense — not just a record, but a narrator.

### Behavior change
Read-only. Generates LLM-authored text from existing data; doesn't change trading.

**Hard prerequisite:** the debate engine must be producing real (not "Failed to generate argument") transcripts. As of 2026-05-01 it produces 100% failure placeholders. PR5 is gated on hydrating that pipeline first.

### Concrete deliverables

#### 1. Per-trade post-mortem
- For each closed trade, generate a 2-3 paragraph narrative:
  - Why was this signal generated? (Indicator readings + agent scores at entry)
  - What did the debate transcript actually say?
  - What happened in the market afterwards?
  - Was the close reason consistent with the entry thesis?
- Persist in new `trade_postmortems` table (one row per `closed_trade.position_id`).

#### 2. Period summaries
- Daily / weekly summaries: "this week your portfolio lost 1.2% — the dominant reason was X, the top winner was Y."
- Generated by an LLM that reads the closed trades + post-mortems for the period.

#### 3. Operator queries
- A natural-language query interface over the audit chain: "show me trades where TA disagreed with sentiment and we lost money."
- Translates to SQL via LLM, runs the query, returns formatted results.

### Acceptance test
> "Pick a closed trade at random. Read its post-mortem. Without looking at the raw audit data, can a human understand why the trade happened and why it ended the way it did?"

---

## Sequencing summary

```
PR1 (audit chain) ──→ PR2 (insight engine) ──→ PR3 (adaptive weights)
                                            │
                                            ├──→ PR4 (profile auto-tuning)
                                            │
                                            └──→ PR5 (LLM post-mortems)
                                                  ↑
                                                  └─ blocked on debate
                                                     hydration (Phase 2 ML)
```

PR3 unlocks PR4 and PR5 logically — once the system is writing back, autotune (PR4) and narration (PR5) can share the metrics infrastructure. PR5 also depends on the broader Phase 2 ML hydration (real debate transcripts, working LLM provider).

## Why this order

The discipline matters: building intelligence on top of an unverified audit chain is how you ship a system that confidently makes worse decisions. PR1 verified the chain; PR2 reads from it; PR3 writes back to it; PR4/5 build user-facing surfaces over the resulting feedback loop.

If you skip ahead — e.g., write an "adaptive weight tuner" before PR2's gate efficacy data exists — the tuner has no ground truth to tune against, and you introduce drift you can't measure. Build the metrics layer first, then build the actuator on top.
