# Second Brain — Remaining PRs (PR2 → PR5)

> **Status:** Plans, not yet started. PR1 (the audit chain) is shipped and verified.
> **Predecessors:** [`SECOND-BRAIN-PR1-PLAN.md`](./SECOND-BRAIN-PR1-PLAN.md), [`SECOND-BRAIN-ROADMAP.md`](./SECOND-BRAIN-ROADMAP.md)
> **Related session work:** [`EXECUTION-REPORT-2026-05-01.md`](./EXECUTION-REPORT-2026-05-01.md) — Track C work that PR3/PR4 depend on (shadow flag, regime gating, both-legs profiles)
>
> Each PR below is execution-ready: goal, behavior change, files, migration, steps, acceptance, scope risks, effort. Sequencing and decision points at the bottom.

---

## Context recap

PR1 made every trade reconstructable. PR2-PR5 close the loop from realized outcomes back to the engine's configuration.

```
PR1  audit chain   → PR2  insight engine → PR3  adaptive weights → PR4  profile auto-tune
                                                                  → PR5  LLM post-mortems
                                                                          (gated on A.1)
```

The order matters. Each PR depends on data the prior one produced; skipping ahead means writing actuators on top of unverified data.

Three shipped pieces from prior sessions feed into these PRs and should be treated as fixed inputs:

- `trade_decisions.shadow` column (migration 018, today) — PR3 reads this to compare regime-gated would-be trades against live trades.
- `entry_long` / `entry_short` schema in `StrategyRulesInput` — PR4's mutation generator can produce both-legs variants.
- `preferred_regimes` field — PR3's gate calibrator should treat regime gating as one of the gates whose efficacy is measured.

---

## PR2 — Insight Engine (read the ledger)

### Goal

Compute and expose, per profile and per agent: *"would this signal have been profitable?"* and *"which gate is doing useful work versus just blocking volume?"* The data exists; nothing reads it.

### Behavior change to live trading

**None.** PR2 only reads. New endpoints, new dashboard panels, new periodic reports. Decision logic is unchanged.

### Dependencies

- PR1 audit chain (shipped)
- `closed_trades`, `trade_decisions`, `market_data_ohlcv`, `agent_score_history` tables (all exist)

### Files to create / modify

**New:**
- `services/analyst/src/insight_engine.py` — orchestrator that runs every 6h
- `services/analyst/src/gate_efficacy.py` — computes blocked-set vs passed-set realized P&L per gate
- `services/analyst/src/agent_attribution.py` — computes agreement-pattern outcomes
- `services/analyst/src/strategy_heatmap.py` — per-rule-fingerprint outcomes
- `services/analyst/src/close_reason_taxonomy.py` — close_reason × symbol × profile × regime slicing
- `services/api_gateway/src/routes/insights.py` (or extend `agent_performance.py`)
- `frontend/components/PerformanceReview/GateEfficacyPanel.tsx`
- `frontend/components/PerformanceReview/CloseReasonPanel.tsx`
- `frontend/components/PerformanceReview/RuleHeatmapPanel.tsx`

**Modify:**
- `frontend/components/PerformanceReview/PerformanceReviewDrawer.tsx` (or wherever the drawer lives) — slot in the new panels
- `frontend/components/PerformanceReview/TradeAttributionPanel.tsx` — extend with agreement-pattern rows

### Migration

`019_insight_engine_tables.sql`:

```sql
CREATE TABLE IF NOT EXISTS gate_efficacy_reports (
    report_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id       UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    symbol           TEXT NOT NULL,
    gate_name        TEXT NOT NULL,                -- abstention | regime | regime_mismatch | circuit_breaker | hitl | risk
    window_start     TIMESTAMPTZ NOT NULL,
    window_end       TIMESTAMPTZ NOT NULL,
    blocked_count    INT NOT NULL,
    passed_count     INT NOT NULL,
    blocked_would_be_win_rate  NUMERIC(6,4),       -- NULL when blocked_count too small
    blocked_would_be_pnl_pct   NUMERIC(10,4),
    passed_realized_win_rate   NUMERIC(6,4),
    passed_realized_pnl_pct    NUMERIC(10,4),
    sample_size_blocked        INT NOT NULL,        -- after dropping rows where lookahead unavailable
    sample_size_passed         INT NOT NULL,
    confidence_band            NUMERIC(6,4),        -- bootstrap CI width on the difference
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_gate_efficacy_profile_gate ON gate_efficacy_reports (profile_id, gate_name, created_at DESC);

CREATE TABLE IF NOT EXISTS rule_fingerprint_outcomes (
    fingerprint      TEXT NOT NULL,                  -- e.g. "rsi:LT:30 | macd:GT:0"
    profile_id       UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    symbol           TEXT NOT NULL,
    window_start     TIMESTAMPTZ NOT NULL,
    window_end       TIMESTAMPTZ NOT NULL,
    trade_count      INT NOT NULL,
    win_rate         NUMERIC(6,4),
    avg_pnl_pct      NUMERIC(10,4),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fingerprint, profile_id, symbol, window_end)
);
```

### Implementation steps

1. **Build the gate efficacy worker first** — it's the highest-leverage metric and the one the partner dialogue specifically calls out. Stop here for the MVP if time runs short.

   For each blocked decision in the window:
   - Look up the next K candles in `market_data_ohlcv` (K configurable; default 60 minutes for 1m bars)
   - Simulate "would this trade have been a winner had it passed?" assuming the profile's stop_loss / take_profit / max_holding from `risk_limits`
   - Compute would-be P&L
   - Compare against actually-passed decisions over the same window

   Edge cases: trades where the lookahead window crosses end-of-data (drop). Trades where the next-K candles include a regime change (record but don't filter — that's signal). Decisions blocked by HITL where the human eventually approved (those become passed-set retroactively).

2. **Agent attribution.** Read `trade_decisions.agents` (the JSONB column populated in PR1). Bucket by agreement pattern: `TA_BULL+SENT_BULL+DBT_BULL`, `TA_BULL only`, `TA_BULL+SENT_BEAR (disagreement)`, etc. For each bucket, join with the closed trade's realized P&L. Output a confusion-matrix-style view.

3. **Rule heatmap.** Read `trade_decisions.strategy.matched_conditions` (already persisted by PR1). For each unique fingerprint (sorted condition tuple), aggregate trade count + win rate + avg P&L. Surface per-profile.

4. **Close reason taxonomy.** Single SQL query — `SELECT close_reason, COUNT(*) FROM closed_trades WHERE ... GROUP BY close_reason`. Slice by profile / symbol / regime via WHERE clauses on the JOIN.

5. **API.**
   - `GET /agent-performance/gate-efficacy/{symbol}?profile_id=&window=7d`
   - `GET /agent-performance/attribution/{symbol}?profile_id=` (extend existing endpoint with agreement-pattern slice)
   - `GET /agent-performance/rule-heatmap/{symbol}?profile_id=`
   - `GET /audit/close-reasons?profile_id=&window=`

6. **Frontend.** Each panel is a thin renderer — fetch, paginate, render a table with sparklines. Reuse the existing Performance Review drawer chrome.

### Acceptance criteria

After PR2 ships, this question gets a number on the dashboard:

> *"Of the trades blocked by the abstention gate in the last 7 days, what fraction would have been profitable had they passed?"*

Specifically:
- `gate_efficacy_reports` table populated with ≥1 row per (profile, gate) for the demo profile
- `GET /agent-performance/gate-efficacy/...` returns the report
- Drawer panel renders it with a confidence interval
- Worker runs on schedule (verify by checking `created_at` advances every 6h)

### Out of scope

- Real-time efficacy. 6h cadence is enough; partner-facing impact is the same.
- Statistical significance with proper p-values. Sample sizes are too small for robust frequentist tests; descriptive stats + bootstrap confidence intervals are the right choice.
- Acting on the metrics. PR3 is the actuator.

### Effort

- Gate efficacy alone (MVP): 3-4 days
- All four metric classes + UI: 6-8 days

### Risks

- **Lookahead bias.** When computing "would have won", be careful not to use information that wasn't available at the decision moment. Use the same risk_limits and exit policies that were in effect for the profile at decision time, not current values.
- **Sample size.** With ~7 APPROVED decisions in the last 24h on the demo profile, the passed-set is too small for reliable comparison. PR2 should report sample sizes prominently and abstain (return null) when below a threshold (e.g. < 30 trades).

---

## PR3 — Adaptive Weights (write back to the ledger)

### Goal

When PR2's metrics show agent X is consistently right and agent Y consistently wrong over the last N decisions, **update agent weights automatically**. Same for gate thresholds when efficacy data warrants. This is the first PR that makes the platform agentic in the literal sense.

### Behavior change to live trading

**Significant.** The system retunes its own gate thresholds and agent weights based on realized performance. Every change flows through a versioned `config_changes` log so it's reversible and visible.

### Dependencies

- **PR2 metrics** — gate efficacy reports, agent attribution
- **C.5 shadow trades** (shipped in autonomous-execution-2026-05-01) — needed to compare regime-gated would-be trades against live trades for regime-gating calibration
- `agent_weight_history` table (migration 012, exists)
- `config_changes` table (verify exists; if not, add to migration)
- Hot path's Analyst component already reads from `agent_weight_history` per the C.5 commit context — confirm before starting

### Files to create / modify

**New:**
- `services/analyst/src/weight_tuner.py` — hourly worker, EWMA per-agent accuracy → weight updates
- `services/analyst/src/gate_calibrator.py` — proposes gate threshold relaxations / tightens
- `services/analyst/src/config_writer.py` — common interface for writing to `config_changes` with full provenance
- `services/api_gateway/src/routes/agent_config.py` — extend with `GET /agent-config/history` and `POST /agent-config/revert/{change_id}`
- `frontend/components/AgentConfig/ConfigHistoryPanel.tsx` — version-control-style log of changes with revert buttons

**Modify:**
- `services/hot_path/src/agent_modifier.py` — confirm it reads weights from `agent_weight_history` on a refresh interval (it should already)
- `services/hot_path/src/abstention.py` — read threshold from `gate_config:abstention` Redis key (or wherever the gate calibrator writes)
- `services/hot_path/src/regime_dampener.py` — multipliers should be loadable from config so the calibrator can update them

### Migration

`020_config_provenance.sql` (assuming `config_changes` exists; adjust if not):

```sql
ALTER TABLE config_changes
    ADD COLUMN IF NOT EXISTS reasoning JSONB,           -- {agent: "ta", prior_weight: 0.4, new_weight: 0.45, evidence: {win_rate_lift: 0.03, n_trades: 87}}
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual',  -- 'manual' | 'weight_tuner' | 'gate_calibrator'
    ADD COLUMN IF NOT EXISTS auto_applied BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS reverted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_config_changes_source ON config_changes (source, applied_at DESC);
```

### Implementation steps

1. **Weight tuner first.** Smaller scope, lower blast radius than gate calibrator.

   Algorithm:
   - Read closed trades over rolling 30 days
   - For each (agent, direction) pair, compute Pearson correlation between agent's score at decision time and realized P&L
   - Convert correlation → target weight via softmax with temperature τ (configurable; start with τ=0.5)
   - Apply ±5% per-cycle cap on weight changes
   - Apply hard floors (5%) and ceilings (60%)
   - Require ≥50 closed trades before any change
   - Write the new weight row to `agent_weight_history` with a `config_changes` provenance row

   Hot path picks up the new weight on next tick (existing read-from-table behavior).

2. **Gate calibrator second.** Reads PR2 gate efficacy reports.

   Algorithm:
   - For each gate, look at the last 3 efficacy reports (18h of data)
   - If `blocked_would_be_win_rate - passed_realized_win_rate > confidence_band` for ≥3 consecutive cycles, propose relaxing the gate threshold by 5%
   - Write proposal to `config_changes` with status `proposed` (auto-apply or HITL-style approval, controlled by env)
   - Hard guardrails: abstention threshold floor 30% (never let everything through), HITL confidence floor 0.2 (never auto-approve below this)

   The regime_mismatch gate (added in C.4) is special: calibrating it means changing the profile's `preferred_regimes` list, not a numeric threshold. Defer the regime-gating calibration to a sub-feature ("would removing RANGE_BOUND from this profile's preferred_regimes improve realized P&L?") — write the proposal but don't auto-apply.

3. **Reversibility.**
   - `GET /agent-config/history?source=&since=` returns recent changes
   - `POST /agent-config/revert/{change_id}` writes a new change row that restores the prior value (don't delete the original)
   - Frontend renders a git-log-style view with one-click revert

4. **Observability.** Every weight change emits a structured log line + a telemetry event so the dashboard can show "the system retuned itself X minutes ago because Y".

### Acceptance criteria

> *"Without manual intervention, can the system improve win rate by ≥1% over a 14-day backtest replay where it weights agents based on their realized accuracy?"*

Specifically:
- Weight tuner runs once and writes ≥1 row to `agent_weight_history` based on EWMA accuracy
- Hot path's Analyst picks up the new weight on the next tick (verify via probe script)
- `config_changes` row exists documenting the tune (with reasoning JSONB)
- Dashboard config-history panel shows the change
- One-click revert restores prior config

### Out of scope

- Reinforcement learning (q-learning, policy gradient). EWMA + bounded updates is enough for the first pass.
- Cross-symbol weight transfer (BTC weights informing ETH weights). Per-symbol only.
- Real-time updates (sub-hour). Hourly cadence is enough.
- User-visible weight tuning (let the user override learned weights). That's a UX layer for later.

### Effort

- Weight tuner alone: 3-4 days
- + Gate calibrator: +3-4 days
- + Reversibility UI: +2 days
- Total realistic: 8-10 days

### Risks

- **Oscillation.** If the tuner overshoots, weights swing wildly. ±5% cap is the primary defense; verify in a backtest replay before letting it run on live data.
- **Concept drift on changeover.** When PR3 first goes live, the historical training window contains data from the static-weight regime. Bootstrap problem: it'll tune toward the static optimum. Acceptable for v1; document.
- **Reversal cascades.** If a revert triggers a tune in the opposite direction, you can get reverberation. Add a cooldown: no auto-tune within 24h of a revert.

---

## PR4 — Profile auto-tuning (parallelizable with PR5)

### Goal

When a user's strategy has been losing for N days but a *neighbor* strategy (one indicator different, one threshold shifted) has been winning, surface the suggestion. With consent, apply it.

### Behavior change to live trading

Surfaces suggestions to users; does not change live profiles without explicit consent. Shadow mode runs paper-only alongside the live profile.

### Dependencies

- **PR2 metrics** (rule heatmap especially)
- **`services/backtesting/`** — existing backtest service, used as the suggestion-validation engine
- **C.1 both-legs schema** (shipped autonomous-execution-2026-05-01) — mutation generator can propose adding an entry_short to a long-only profile when shorts are profitable on the same symbol
- **C.2 indicators** (shipped autonomous-execution-2026-05-01) — mutation space is wider with VWAP, Keltner, RVOL, Z-Score, Hurst available

### Files to create / modify

**New:**
- `services/analyst/src/profile_suggestor.py` — daily worker that generates and ranks mutations
- `services/analyst/src/mutation_generator.py` — pure functions producing N micromutations of a given profile
- `services/api_gateway/src/routes/suggestions.py` — new endpoint surface
- `frontend/components/Strategies/SuggestionPanel.tsx` — "Try this" cards on the strategies page
- `frontend/components/Strategies/ShadowComparePanel.tsx` — side-by-side live vs shadow performance

**Modify:**
- `services/api_gateway/src/routes/profiles.py` — add `POST /profiles/{id}/promote-shadow` endpoint
- `services/hot_path/src/state.py` — `ProfileState` gains a `shadow_of` field linking shadow profiles to their live parent

### Migration

`021_profile_suggestions.sql`:

```sql
CREATE TABLE IF NOT EXISTS profile_suggestions (
    suggestion_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_profile_id UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(user_id),
    mutation_kind    TEXT NOT NULL,                  -- 'threshold_shift' | 'add_indicator' | 'add_short_leg' | etc.
    mutation_diff    JSONB NOT NULL,                 -- structured diff vs parent rules
    backtest_window  JSONB NOT NULL,                 -- {start_date, end_date, symbol, slippage_pct}
    backtest_metrics JSONB NOT NULL,                 -- {sharpe, win_rate, max_dd, total_trades}
    parent_metrics   JSONB NOT NULL,                 -- baseline for comparison
    rank             INT NOT NULL,                   -- 1..N within the suggestion batch
    status           TEXT NOT NULL DEFAULT 'proposed', -- 'proposed' | 'shadowed' | 'promoted' | 'dismissed'
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_profile_suggestions_user ON profile_suggestions (user_id, status, created_at DESC);

ALTER TABLE trading_profiles
    ADD COLUMN IF NOT EXISTS shadow_of UUID REFERENCES trading_profiles(profile_id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_trading_profiles_shadow_of ON trading_profiles (shadow_of) WHERE shadow_of IS NOT NULL;
```

### Implementation steps

1. **Mutation generator.** Pure function: `(profile_rules, indicator_universe) → List[mutation]`. Mutation classes:
   - **Threshold shift:** for each existing condition, generate ±10%, ±20% threshold variants
   - **Add indicator:** add one of the C.2 indicators (vwap, keltner.upper, rvol, z_score, hurst) with a sensible default threshold
   - **Match mode swap:** AND ↔ OR
   - **Add short leg:** if profile is long-only and shorts on the same symbol have been profitable (per PR2 attribution), propose a both-legs mutation
   - **Direction flip:** rare, but worth one slot — sometimes a contrarian profile beats the original

   Generate ~10 mutations per parent. Deduplicate by canonical fingerprint.

2. **Backtest each mutation.** Reuse `services/backtesting/` against the last 30 days of OHLCV. Use the `BacktestRequest` schema from `libs/core/schemas.py`. Fan out via the existing job runner; cap concurrency at 3.

3. **Rank.** Score = `0.5 * sharpe_z + 0.3 * win_rate_z + 0.2 * (-max_dd_z)` where `_z` is the standardized score across the batch. Top 3 surface.

4. **Surface in `/strategies`.** New panel below the profile list. Each card shows the mutation diff (`+ rsi LT 25 | - rsi LT 30`), the backtest delta (`+1.4 Sharpe over 30d`), and three buttons: "Shadow", "Promote", "Dismiss".

5. **Shadow mode.** "Shadow" creates a new `trading_profiles` row with `shadow_of` set to the parent. Hot path treats shadow profiles like live profiles but every emitted decision is forced to `shadow=true` (the column shipped in C.5). After K trades (configurable; default 50), the dashboard shows side-by-side performance.

6. **Promotion.** "Promote" copies the shadow profile's rules over the parent, marks the parent's prior rules as a snapshot in `config_changes`, and removes the shadow row. One-click revert restores the prior rules.

### Acceptance criteria

> *"Given a profile that has lost money 3 weeks in a row, the suggestor produces at least one micro-mutation that beats it on a held-out backtest."*

Specifically:
- `profile_suggestions` table populated with ≥3 ranked rows for at least one user-owned profile
- "Try this" cards render on `/strategies` with the diff and the backtest delta
- Click "Shadow" creates a `shadow_of`-linked profile that produces shadow=true decisions
- After K shadow trades, the compare panel renders live vs shadow

### Out of scope

- Cross-profile mutations (taking ideas from one user's profile and suggesting them to another). Privacy + IP concerns.
- LLM-generated mutations ("describe a strategy" → profile). That's PR5+ territory and a separate feature.
- Genetic-algorithm mutation chains (mutate the mutation). Single-step only.

### Effort

- Mutation generator + backtest fan-out: 3-4 days
- Suggestion UI + shadow mode UX: 3-4 days
- Promotion + revert flow: 2 days
- Total: 8-10 days

### Risks

- **Backtest spend.** Each suggestion batch fires N backtests against 30 days of data. With 10 mutations × 50 active profiles × daily cadence = 500 backtests/day. Backtest service should be queued, not concurrent.
- **Survivorship bias.** Mutations are ranked on a single window. A mutation that wins on May data may lose on June data. Document the limitation; promote with caution.
- **Shadow profile sprawl.** Users will create shadows and forget about them. Add a 30-day TTL on inactive shadows.

---

## PR5 — LLM-assisted post-mortems (parallelizable with PR4)

### Goal

Use the (now-hydrated) debate transcripts and decision context to generate human-readable explanations of why each trade won or lost. The "second brain" in the literal sense — not just a record, but a narrator.

### Behavior change to live trading

Read-only. Generates LLM-authored text from existing data; doesn't change trading.

### Dependencies

**Hard prerequisite: A.1 (debate hydration) must be complete.** As of 2026-05-04, A.1 has the env-name reconciliation shipped (autonomous-execution-2026-05-01) but the actual LLM round-trip is unverified. Generating post-mortems on placeholder transcripts is worse than not generating them — DO NOT START PR5 until `debate_transcripts` has ≥80% real (non-`Failed%`) rows.

Also depends on:
- PR1 audit chain
- PR2 close-reason taxonomy (for the period summaries)
- LLM provider key working end-to-end (Anthropic API or local SLM via PR A.2)

### Files to create / modify

**New:**
- `services/analyst/src/postmortem_writer.py` — per-trade narrator, runs on each closed trade
- `services/analyst/src/period_summarizer.py` — daily/weekly portfolio summaries
- `services/analyst/src/operator_query.py` — natural-language → SQL translator for the audit chain
- `prompts/postmortem/` — prompt templates (per_trade.txt, period_summary.txt, operator_query.txt)
- `services/api_gateway/src/routes/postmortems.py`
- `frontend/components/Trades/PostmortemPanel.tsx` — renders narrative on each closed trade detail page
- `frontend/components/Dashboard/PeriodSummaryWidget.tsx` — daily/weekly summary on the main dashboard
- `frontend/components/Audit/OperatorQueryBox.tsx` — natural-language query interface

### Migration

`022_trade_postmortems.sql`:

```sql
CREATE TABLE IF NOT EXISTS trade_postmortems (
    position_id      UUID PRIMARY KEY REFERENCES positions(position_id) ON DELETE CASCADE,
    profile_id       UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    narrative        TEXT NOT NULL,
    structured       JSONB,                     -- {entry_thesis, market_response, exit_assessment} for downstream queries
    llm_provider     TEXT NOT NULL,             -- 'anthropic' | 'local_slm'
    llm_model        TEXT NOT NULL,             -- e.g. 'claude-haiku-4-5-20251001'
    tokens_used      INT,
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS period_summaries (
    summary_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(user_id),
    period_kind      TEXT NOT NULL,              -- 'daily' | 'weekly'
    period_start     DATE NOT NULL,
    period_end       DATE NOT NULL,
    narrative        TEXT NOT NULL,
    metrics          JSONB NOT NULL,             -- {pnl_pct, n_trades, top_winner, dominant_loss_reason}
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, period_kind, period_start)
);
CREATE INDEX idx_period_summaries_user ON period_summaries (user_id, period_end DESC);
```

### Implementation steps

1. **Per-trade post-mortem worker.** Triggered by close events (sub to `pubsub:closed_trade` or poll `closed_trades` for rows missing a `trade_postmortems` row).

   For each closed trade, gather:
   - The originating decision row (indicators + agent scores + gate verdicts)
   - The debate transcript for that timestamp (from `debate_transcripts`)
   - The next K candles after entry (from `market_data_ohlcv`)
   - The close reason and realized P&L

   Render into a 3-section prompt:
   - **Thesis section:** "At entry, RSI was X, MACD was Y, the bull agent argued Z, the bear agent countered W"
   - **Market section:** "Price moved A% before reversing at time T"
   - **Outcome section:** "The position closed via stop_loss at -B%, consistent / inconsistent with the entry thesis"

   Call LLM (provider configurable: Anthropic via the existing key, or local SLM if PR A.2 is live). Persist the narrative + structured JSON.

2. **Period summarizer.** Daily cron (00:05 UTC, like the existing daily_report). Aggregate the day's closed trades, group by close_reason and outcome, identify top winner and dominant loss reason. Pass to LLM with a "summarize this trader's day" prompt. Persist.

3. **Operator query.** A natural-language query box on the audit page. Steps:
   - User types "show me trades where TA disagreed with sentiment and we lost money"
   - Backend constructs an LLM prompt with the schema of `trade_decisions`, `closed_trades`, `agent_score_history`
   - LLM generates SQL
   - Backend validates the SQL is read-only (SELECT only, no DML/DDL), runs it with a timeout, returns results
   - Frontend renders as a table

   Safety: parameterized inputs only, statement-timeout enforced, query plan size capped, results limited to 1000 rows.

4. **Frontend.** Each surface is a thin renderer. Post-mortem panel hangs off the existing closed-trade detail page. Period summary widget on the dashboard. Operator query gets its own audit-page tab.

### Acceptance criteria

> *"Pick a closed trade at random. Read its post-mortem. Without looking at the raw audit data, can a human understand why the trade happened and why it ended the way it did?"*

Specifically:
- `trade_postmortems` populated for every `closed_trades` row generated after PR5 lands
- Period summaries generated daily, queryable by user
- Operator query box produces working SQL for at least these three test queries:
  - "trades where TA disagreed with sentiment and we lost money"
  - "average win rate by regime over the last 30 days"
  - "profiles whose abstention block rate exceeded 90% in the last week"

### Out of scope

- Real-time post-mortems (generate as the trade closes vs as a batch). Batch is fine; latency budget is hours not seconds.
- Multi-language narratives. English only.
- Post-mortems for blocked decisions (only for closed trades). PR2 already covers what blocked decisions tell us.

### Effort

- Per-trade writer: 3-4 days
- Period summarizer: 2 days
- Operator query: 3-4 days (SQL safety is the hard part)
- Total: 8-10 days

### Risks

- **LLM cost.** A 3-paragraph post-mortem at ~600 tokens × ~50 trades/day × 30 days = 900K tokens/month per user. With Sonnet pricing that's a noticeable bill. Default to Haiku for post-mortems; reserve Sonnet for period summaries.
- **Hallucinated SQL.** The operator query LLM will sometimes generate SQL that runs but returns the wrong thing. Whitelist tables and columns; show the generated SQL alongside results so the user can sanity-check.
- **Stale narratives.** A post-mortem written today may contradict updated context (e.g. a regime relabel by an HMM retrain). Treat post-mortems as point-in-time; never auto-update.

---

## Sequencing across the four PRs

```
PR2  ────────┬─→  PR3 (needs PR2 metrics + C.5 shadow data)
             │
             └─→  PR4 (needs PR2 rule heatmap, independent of PR3)
                       │
PR5 (needs A.1 hydrated debate transcripts) ───────────────┘
       — can start in parallel with PR4 once A.1 lands
```

**Dependencies summary:**

| PR | Depends on | Unblocks |
|----|-----------|----------|
| PR2 | PR1 (done) | PR3, PR4 |
| PR3 | PR2 + C.5 (done) | nothing direct |
| PR4 | PR2 + C.1, C.2 (done) | nothing direct |
| PR5 | A.1 (partial — env shipped, smoke-test pending) + PR1 | nothing |

**Realistic order if executing sequentially:**

1. **PR2 gate efficacy MVP** (3-4 days) — fastest path to partner-visible value.
2. **PR2 full** (3-4 days more) — agent attribution, rule heatmap, close-reason taxonomy.
3. **PR3 weight tuner only** (3-4 days) — first writeback, contained scope.
4. **A.1 full hydration** (½-1 day) — gating dependency for PR5; if not done in parallel earlier.
5. **PR3 gate calibrator + revert UI** (5 days) — rest of PR3.
6. **PR4 mutation generator + UI** (8-10 days) — substantial frontend.
7. **PR5 per-trade post-mortems** (3-4 days) — once debate transcripts are real.
8. **PR5 period summaries + operator query** (5-6 days).

**Total: 30-40 dev-days end-to-end.** That's 6-8 weeks of focused work for one engineer; faster with parallelization (PR4 and PR5 can run in parallel once PR3 + A.1 are done).

---

## Decision points before starting any of these

1. **Auto-apply vs HITL on PR3 gate calibrator.** Auto-apply means the system relaxes/tightens gates without human approval. Safer default is `proposed` status requiring a human click in the dashboard. Worth deciding before implementation, not after.

2. **LLM provider for PR5.** Anthropic via existing key, or route through `services/slm_inference/` (depends on A.2 landing)? Cost vs latency tradeoff. Recommendation: Anthropic for narrative quality on per-trade post-mortems, local SLM for high-volume operator queries (where cost dominates and quality matters less).

3. **PR4 shadow profile UX.** Should shadows count against the user's profile limit (if any)? Should shadows show in the main strategies list or in a separate "Shadows" section? Worth a UX decision before frontend work begins.

4. **Operator query SQL safety.** Whitelisting columns is conservative but limits expressiveness. Allowing arbitrary SELECT with statement timeout is permissive but riskier. Pick a posture before implementation.

5. **Post-mortem retention.** With 50 trades/day × 600 tokens narrative × N users, the `trade_postmortems` table grows fast. Decide retention policy upfront (e.g. archive narratives older than 1 year to cold storage, keep structured JSON only).

---

## What's NOT in this document

- **PR0 / pre-work fixes.** A.1 hydration completion, A.2 SLM model loading, A.3 HMM retraining — covered separately in [`AUTONOMOUS-EXECUTION-BRIEF.md`](./AUTONOMOUS-EXECUTION-BRIEF.md).
- **Pre-existing tech debt.** See [`TECH-DEBT-REGISTRY.md`](./TECH-DEBT-REGISTRY.md) — none is a hard blocker for any of PR2-PR5.
- **Operational runbooks** for when the second brain misbehaves (oscillating weights, runaway suggestor backtests, LLM rate limit hits). Worth writing once the corresponding PR ships, not before.
