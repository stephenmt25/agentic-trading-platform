# Partner demo — walkthrough script & supporting reference

> Self-contained reference for a live demo of the Praxis trading platform.
> Three sections: the spoken dialogue (read aloud), the trade-influence
> truth table (Q&A backup), and the live demo state cheat sheet.
>
> Captured 2026-05-01 against a fresh paper-trading session with the
> "Demo · Pullback Long" profile. State numbers are point-in-time —
> verify with `scripts/probe_state.py` and `scripts/watch_demo_decisions.py`
> before reusing.

---

## 1 · Dialogue script (read aloud)

Read slowly. Square brackets are stage directions, not lines.

---

> "The platform's mission is **observability for agent-driven trading.** Every other trading bot you've seen is a black box — it makes a decision, you see the P&L, and you guess. What we're building is a glass box: every trade is reconstructable from the candle that triggered it, through the agents that scored it, through the gates that approved or blocked it, all the way to the close reason and the realized P&L. That's the *product*. The strategy and the ML are inhabitants of the platform, not the platform itself."

> [Show `/trade` page.]
>
> "This page is the live operations view. The chart is real-time market data — that's wired. These three numbers — TA, sentiment, regime — are the agent scores feeding into every decision. Today, **only TA is actually producing signal.** Sentiment falls back to neutral; the regime classifier is wired up but not yet hydrated. I want to be transparent: the multi-agent intelligence is what we *measure* and *render*, but only one of three agents is contributing today. Everything else is observable in the audit even when it's silent."

> [Show `/strategies` or `/profiles`.]
>
> "This is where strategies are defined — the rules, the indicators, the thresholds. A user can wire up a strategy here and it generates trade signals. **Here's where it gets interesting:** signals are not orders. Every signal goes through three gates."

> [Pull up the gate-block analytics or the trade page's engine totals.]
>
> "The **abstention gate** is the first filter — it asks 'is this signal high-confidence enough to act on?' In the last 24 hours, this gate has blocked **83 percent** of signals. The **circuit breaker** is the second filter — it asks 'is the system in a state where any trade is safe?' That blocks another **17 percent**. The **regime gate** blocks a tiny fraction. Out of every thousand signals, roughly one becomes an order. That's by design — the platform is paranoid, and we want it that way for live trading." - #we can show this well in the pipeline editor page, add functionality to reflect current state of system (we disabled regime gate so maybe show this in the editor somehow also maybe add controls) 

> [Show `/backtest` or run history.]
>
> "Backtest is where strategies are validated before going live. A user uploads a profile, runs it against historical candles, and gets a full P&L curve, win rate, drawdown, Sharpe. We're using this internally too — when we propose a tuning change, we backtest the proposed change against the live one before promoting." - #still need to show completed backtest run results in some way

> [Show audit endpoints — `/audit/chain/{decision_event_id}` or the closed_trades table in the DB.]
>
> "This is what I want to spend a minute on. We just landed the foundational piece called **the second brain — PR1.** Until last week, you could see a closed trade and you couldn't reconstruct it. The decision UUID didn't link to the order UUID. Closed-trade reasons weren't recorded as their own row. Debate transcripts were summarized into a one-liner and the actual back-and-forth was lost. **PR1 fixes all three.** Right now, every trade in our database can be joined back to the originating decision, the indicators at the moment, the agent scores, the gate verdicts, the order, the position, the close reason, and the realized P&L. **I verified this this morning** — every order has its decision link populated; every closed trade has a reason and a P&L attached."

> "Why does this matter? Because PR1 is the foundation for everything that turns this from an *observable* system into a *self-improving* one."

> [Pivot.]
>
> "Today, the agents have static weights. The strategy rules are static. The gate thresholds are static. The platform watches everything but it doesn't yet *learn* from anything. **PR2 is the insight engine.** It will read the audit chain and answer questions like 'when the abstention gate blocks a signal, would that signal have been profitable?' If abstention is blocking trades that would have won, it's a bad gate and we should relax it. If it's blocking trades that would have lost, it's earning its keep. Today we have no idea — we have the data but no consumer."

> "**PR3 is adaptive weights.** Once PR2 produces those metrics, PR3 closes the loop — the system updates agent weights, gate thresholds, and eventually strategy rules based on actual realized performance. Every change flows through a version-controlled `config_changes` log, so it's reversible and visible. That is when the platform stops being a static rules engine and starts being agentic."

> "**PR4 is profile auto-tuning** — the system shadow-runs micromutations of a user's strategy and surfaces winning variants as suggestions. **PR5 is LLM-assisted post-mortems** — once the debate transcripts are hydrated, we can generate human-readable explanations of every win and every loss."

> [Final sweep.]
>
> "So to summarize: **the chassis is built and verified.** Live data flowing, signals generating, gates filtering, orders executing, audit reconstructing. **The intelligence layer is partially wired and minimally hydrated** — TA is contributing, sentiment and regime and debate are observable but silent. **The feedback loop — the part that turns this into a self-improving system — is the next milestone, PR2. That's where I want to focus next.** And the reason I built PR1 first instead of jumping to ML is that without a verified audit chain, none of the learning that comes after has data it can trust."

---

## 2 · Trade-influence truth table (Q&A backup)

If your partner asks "what's actually moving trades?":

### What's affecting decisions today
| Component | Status | What it does |
|---|---|---|
| Ingestion (OHLCV via `watch_ohlcv`) | ✅ live | Feeds candles |
| TA agent (RSI, MACD, BB, ADX, ATR, OBV, choppiness) | ✅ live | Real TA score |
| Strategy rule evaluator | ✅ live | Matches indicators against profile thresholds |
| Abstention gate | ✅ live, **dominant filter** | Blocks 82–91% of matches |
| Circuit breaker | ✅ live | Risk-side block (DD/loss limits) |
| Stop-loss monitor | ✅ live | Closes positions at SL |
| Kill switch | ✅ live | Halts trading on demand |
| Rate limiter | ✅ live | Redis sliding-window |
| HITL gate | ✅ live | Holds approved trades for human approval |
| PR1 audit chain | ✅ live, plumbing verified | Reconstructs trades end-to-end |

### What's wired but not hydrated (zero influence on trades)
| Component | Why it doesn't influence | What it needs |
|---|---|---|
| **HMM regime classifier** | Service up, regime returns `null`; `confidence_multiplier` defaults to 0.7 | Trained checkpoint loaded; states emitted |
| **Sentiment agent** | Falls back to neutral 0.0 | News/social feed wired + LLM prompt for scoring |
| **Debate engine** | 100% "Failed to generate argument" rows | LLM provider key + prompt verification |
| **slm_inference** | Service up, `model_loaded: false` | Model checkpoint provisioned + path config |
| **Agent weight learning** | History table populated, no consumer reading from it | PR3 |

**Critical line for the partner:** "The system today trades on **TA + rules + risk gates only**. Every multi-agent path is observable but contributing zero signal. That's why TA is the only positive number in `/agents/status`."

---

## 3 · Live demo state cheat sheet

- **Mode:** PAPER (`binance_testnet=true`, `coinbase_sandbox=true`)
- **Kill switch:** off
- **Active profile:** "Demo · Pullback Long" (`c557fcdc-...`) — RSI<50 AND MACD>0
- **Decisions flowing:** ~1.3/min on ETH/USDT (BTC RSI is currently >50, doesn't match)
- **All decisions are `BLOCKED_HITL`** — you can demo this as the safety net, OR if you want to see APPROVED flow you'd need to set `PRAXIS_HITL_ENABLED=false` and restart, OR raise `PRAXIS_HITL_SIZE_THRESHOLD_PCT` to ~70
- **PR1 ledger:** 100% chain coverage on existing data, acceptance join works
- **`dark` chips:** visible on sentiment / debate / regime in the chart legend and Current Agent Weights — that's the "honesty as a feature" moment
- **Performance Review button:** top of Live Activity section, opens drawer with Gate Analytics + Weight Evolution + Trade Attribution

---

## 4 · Forward-looking roadmap

Four parallel tracks. **Track A** (ML hydration) is the highest-visibility short-term work — it makes the `dark` chips disappear. **Track B** is UI honesty (the two gaps the dialogue review surfaced). **Track C** is strategy expressiveness — the partner-feedback work that lets a single profile go long *and* short, adds the indicators behind named strategies (Mean Reversion, Volatility Squeeze, VWAP Breakout), and gates profiles on regime. **Track D** is the Second Brain feedback loop, which compounds on top of A and C.

### Track A — ML stack hydration (~5–7 dev days total)

Each piece has a service in place; the work is provisioning + wiring, not building from scratch.

#### A.1 — LLM-driven agents (Debate + Sentiment)
**Effort:** ~1 day. **Visible impact:** dark chips on Sentiment + Debate disappear within hours of the API key landing.

- `services/debate/src/engine.py` produces `"Failed to generate argument"` for 100% of rounds (1,468 historical rows are placeholder). The wiring is correct; the LLM call inside is failing.
- `services/sentiment/` returns neutral `0.0` because no live source is connected.

Steps:
1. Pick a provider (Anthropic Claude or OpenAI). Anthropic is the lower-friction choice given existing tooling.
2. Set `PRAXIS_LLM_API_KEY` in `.env`. Verify the env name expected by `engine.py`.
3. Smoke-test one bull/bear cycle manually; confirm the parser handles the response shape.
4. Wire sentiment to the same LLM with a "score this headline -1 to +1" prompt. Source: NewsAPI / Polygon news / a free Reddit-or-X firehose for crypto. Publish to `agent:sentiment:{symbol}` in Redis (the channel hot_path already reads).

**Acceptance:** `scripts/debate_quality.py` shows ≥80% real arguments; `/agents/status` returns non-zero `sentiment_score`.

#### A.2 — slm_inference model loading
**Effort:** ~1–2 days. **Visible impact:** local fast-inference path; alternative to paid LLM for hot-path latency.

`/health` currently returns `model_loaded: false`. Service stub runs but no checkpoint is provisioned.

Steps:
1. Pick a model. Phi-3-mini quantized (Q4_K_M, ~2.4GB) is the practical default for sub-100ms inference on consumer hardware. Alternatives: Llama-3-8B-instruct, Qwen2.5-7B, finance-specialized fine-tunes.
2. Provision the checkpoint — pull from HuggingFace at boot or pre-bake into `docker/slm_inference.Dockerfile`.
3. Wire `PRAXIS_SLM_MODEL_PATH` to the cache. Service should detect and report `model_loaded: true`.
4. Validate p99 inference latency stays under hot_path's tolerance (~100ms).

**Acceptance:** `model_loaded: true`; debate + sentiment can optionally route through here for cost control.

#### A.3 — HMM regime classifier
**Effort:** ~2–3 days. **Visible impact:** regime-aware sizing, BLOCKED_REGIME outcomes start appearing.

Service emits `regime: null` today, so `confidence_multiplier` defaults to 0.7 across the board.

Steps:
1. Confirm state space against `Regime` enum in `libs/core/enums.py` (likely `TRENDING_UP`, `TRENDING_DOWN`, `RANGING`, `HIGH_VOLATILITY`).
2. Train on ~12 months of 1h candles per symbol from `market_data_ohlcv`. Features: log-returns, realized volatility, range/ATR ratio. Fit Gaussian HMM with 4 components.
3. Persist checkpoint to `models/regime_hmm_{symbol}.pkl`. Reject if older than N days (forces retraining).
4. Emit live: consume new candles, run `predict()`, publish `agent:hmm_regime:{symbol}` to Redis.
5. Define per-regime confidence multipliers in config. Retire the hardcoded 0.7.

**Acceptance:** `/agents/status` returns non-null `hmm_regime`; the dark chip on REGIME disappears.

#### A.4 — Validation
**Effort:** ~1 day. **Confirms ML actually changes decisions, doesn't just decorate the dashboard.**

- Compare outcome distributions pre/post hydration (today: 91% BLOCKED_ABSTENTION).
- Run a 14-day backtest replay with hydrated agents vs. without. **This is the partner-facing receipt that ML adds value.**
- If hydrated stack doesn't beat TA-only by a meaningful margin, that's a finding — agents are miscalibrated and PR3 (adaptive weights) becomes more urgent.

---

### Track B — UI honesty (parallelizable with Track A)

Two gaps surfaced during the dialogue review.

#### B.1 — Pipeline editor reflects live gate state + offers controls
**Effort:** ~2–3 days.

The dialogue currently says "every signal goes through three gates" and lists them generically. The pipeline editor should be the place where the partner can *see* the live gate topology — and ideally toggle them.

Surface:
- Each gate node colored by current state: green (active and passing traffic), amber (active and blocking heavily), grey (disabled).
- Live counters per node ("blocked 83% of last hour").
- Toggle controls: enable/disable a gate, adjust its threshold, all hot-applied via `config_changes`.
- Show the regime gate as currently disabled — visually distinct from "active and quiet."

Source: the gate analytics endpoints (`/agent-performance/gate-analytics/...`) already produce the data. The work is rendering it on the canvas + adding the control surfaces.

#### B.2 — Completed backtest results presentation
**Effort:** ~1–2 days.

Today the dialogue says "backtest is where strategies are validated" but a partner clicking into `/backtest` after a run sees only the comparison table for the active session. There's no persistent run history to point at — last week's runs are gone.

Surface:
- Persist completed backtest runs to a new `backtest_results` table (already exists per migration 009 in CLAUDE.md §2D).
- New `/backtest/history?profile_id=` endpoint returns past runs.
- New panel in `/backtest`: "Run history" with sortable list (date, symbol, period, headline metrics).
- Click a row → loads its equity curve into the comparison table.
- Pin/unpin to keep noteworthy runs across sessions.

Bonus: link from `/strategies/Verify` to the run history so a backtest done from the strategy editor shows up in both places.

---

### Track C — Strategy expressiveness (~5 dev days)

Triaged from a partner-feedback session that surfaced new strategy ideas (pairs trading, market making, regime-driven specialist agents, etc.). Most of those proposals turned out to already exist in the system or to be expressible via the existing strategy DSL — what's actually new and worth building is below. The deferred items are listed under "Considered and deferred" at the end of this track.

#### C.1 — Long + short conditions in one profile
**Effort:** ~1 day. **Why:** Today a profile is `direction: "long"` OR `direction: "short"`. A single coherent strategy like Mean Reversion can't say "go long on RSI<30, go short on RSI>70" without two profiles, two HITL queues, and two parallel audit chains. Adding `entry_long` + `entry_short` rule blocks to `StrategyRulesInput` collapses that into one profile.

Steps:
1. Schema change in `libs/core/schemas.py`: replace `direction` + `signals` with optional `entry_long: List[StrategySignal]` + `entry_short: List[StrategySignal]` (legacy single-direction profiles still parse via a back-compat path).
2. Hot-path `strategy_eval` evaluates both per tick; emits a BUY signal, SELL signal, or none.
3. Update `strategy_rules_to_canonical` so the canonical shape carries both legs.
4. Migration backfilling existing profiles into the new shape.

**Acceptance:** A single profile generates buy *and* sell decisions on the same symbol when the respective conditions match.

#### C.2 — New indicators in TA agent
**Effort:** ~2 days. **Why:** Three of the partner's named strategies (Volatility Squeeze, VWAP Breakout, Z-Score mean reversion) need indicators we don't currently emit. Adding them gives those strategies "for free" via the existing rule DSL — no new agents, no new microservices.

Add to `services/ta_agent/`:
- **VWAP** (volume-weighted average price)
- **Keltner Channel** (upper / middle / lower)
- **RVOL** (relative volume = current vol / SMA(vol, 20))
- **Z-Score** (rolling 20-period; (price − SMA) / stdev)
- **Hurst Exponent** (rolling 50-bar; the partner's "Math of the Market" classifier)

All are deterministic numeric calculations on existing OHLCV. Each becomes a new entry in the `StrategySignal.indicator` Literal, queryable from the rule DSL.

**Acceptance:** A profile can reference any of the new indicators and `strategy_eval` matches correctly.

#### C.3 — Profile templates (one-click strategies)
**Effort:** ~1 day. **Why:** The partner asked specifically about Mean Reversion, Trend Following, Volatility Squeeze, and VWAP Breakout. Once C.1 + C.2 land, all four are expressible in the rule DSL. Ship them as one-click templates in `/strategies` so the partner can spin up any of them during a demo.

Templates to ship:
- **Mean Reversion** — `entry_long: rsi<30 AND z_score<-2.0`, `entry_short: rsi>70 AND z_score>2.0`
- **Trend Following (MA cross)** — `entry_long: ma_50 > ma_200 AND macd_line > 0`
- **Volatility Squeeze** — `entry_long: bb_upper < kc_upper AND bb_lower > kc_lower AND close > kc_upper`
- **VWAP Breakout** — `entry_long: close > vwap AND rvol > 2.0`

These live in a `templates.json` consumed by the strategies UI; clicking a template seeds a new profile with the rules pre-populated.

**Acceptance:** Each template clones into a working profile with one click.

#### C.4 — Regime-gated profile activation
**Effort:** ~1 day (blocked on A.3 HMM hydration). **Why:** The partner's "Mean Reversion Agent activates only in Ranging regime" — but expressed as a profile property, not a separate agent. Mean reversion gets crushed in trends; trend following gets crushed in chop. Letting profiles declare which regimes they prefer means each strategy quietly steps aside when the market isn't right for it — without spawning a new microservice per strategy.

Steps:
1. Add `preferred_regimes: List[Regime]` to profile schema (optional; empty = "any").
2. Hot-path checks current regime against `preferred_regimes` early in evaluation.
3. Mismatch → emit `BLOCKED_REGIME_MISMATCH` decision (distinct from `BLOCKED_REGIME` which is risk-side).

**Acceptance:** A profile with `preferred_regimes: [RANGING]` produces zero live decisions during a TRENDING regime, but still records shadow decisions (see C.5).

#### C.5 — Shadow trades for regime-gated misses
**Effort:** ~½ day. **Why:** The partner's "shadow trading" idea aligns directly with PR3's adaptive-weights mechanism — it's how the 2nd Brain validates whether the regime gating is making the right call. Promoted from "later" to "now" because it's a one-column flag with disproportionate learning value.

When C.4 gates a profile out of a regime, still record the trade decision with `shadow=true`. PR3's Analyst then compares shadow-set realized P&L vs. live-set P&L. If shadow trades consistently out-perform live trades for a given regime, the gating is wrong and the regime preferences (or HMM thresholds) need adjustment.

**Acceptance:** Decisions blocked by regime mismatch appear in `trade_decisions` with `shadow=true`; PR3's gate-efficacy metrics consume them.

#### Considered and deferred

The partner's feedback included several larger suggestions evaluated and explicitly *not* taken — listing them here so it's clear they were considered, not missed:

| Suggestion | Verdict |
|---|---|
| **Pairs trading / statistical arbitrage** (multi-leg orders, dollar-neutral correlation matrix) | Defer. Real value but requires multi-asset position grouping, dual-leg fills that succeed/fail atomically, and a correlation matrix that doesn't exist today. Earns its own milestone if/when validated. |
| **High-frequency market making** (sub-second cancel/replace on order book depth) | Skip. Different latency regime than the minute-bar setup; would require Rust execution + order book depth ingestion + an entirely different exchange integration. Wrong phase of the company. |
| **Rust hot-path rewrite** | Skip until measured bottleneck. Python at 1-minute bar latency is not GC-bound; the partner's argument about HFT GC pauses doesn't apply at this resolution. Revisit if/when execution becomes a measured constraint. |
| **Document store / S3 for LLM logs** | Skip. JSONB columns in TimescaleDB handle current log volume; revisit when log volume actually pressures the DB. |
| **Dedicated "Specialist Agent" microservice per strategy** | Reframe. The partner's mental model collapses into "profile templates + regime gating" (C.3 + C.4) — same outcome, half the moving parts. No new microservices. |

---

### Track D — Second Brain (PR2 → PR5)

Detail in [`SECOND-BRAIN-ROADMAP.md`](./SECOND-BRAIN-ROADMAP.md). High-level summary for the demo:

| PR | What | Effort | Behavior change |
|---|---|---|---|
| **PR2 — Insight Engine** | Reads ledger; computes gate efficacy, agent attribution, rule heatmaps, close-reason taxonomy | ~1 week | None — pure observability |
| **PR3 — Adaptive weights** | Reads PR2 metrics; auto-tunes agent weights, gate thresholds; logs everything to `config_changes` | ~1–2 weeks | First PR that retunes live trading |
| **PR4 — Profile auto-tuning** | Suggests strategy mutations based on backtested neighbors; shadow-mode validation before promoting | ~1 week | User-facing suggestions |
| **PR5 — LLM post-mortems** | Generates human-readable narratives per closed trade + period summaries | ~1 week | Read-only, **gated on A.1** (debate hydration) |

PR2 doesn't depend on ML hydration but benefits from it (more agents to attribute over). PR3 consumes Track C.5 shadow-trade data to validate regime gating. PR5 hard-depends on A.1 since it needs real debate transcripts to narrate from.

---

### Dependency graph & sequencing

```
Week 1   ┌────────────────────────────────────────────────────────────┐
         │ A.1 (Debate+Sentiment LLM)  │ B.1 (Pipeline editor live)   │
         │ A.2 (slm_inference)         │ B.2 (Backtest history)       │
         │ A.3 (HMM training)          │ C.1 (Long+short schema)      │
         │ A.4 (Validation)            │ C.2 (New indicators)         │
         │                             │ C.3 (Profile templates)      │
         │                             │ C.5 (Shadow trades flag)     │
         └────────────────────────────────────────────────────────────┘

Week 2   ┌────────────────────────────────────────────────────────────┐
         │ C.4 (Regime-gated profiles — blocked on A.3)               │
         └────────────────────────────────────────────────────────────┘

Week 2-3 ┌────────────────────────────────────────────────────────────┐
         │ PR2 (Insight Engine — reads PR1 ledger + Track A signals)  │
         └────────────────────────────────────────────────────────────┘

Week 4-5 ┌────────────────────────────────────────────────────────────┐
         │ PR3 (Adaptive weights — consumes C.5 shadow trades too)    │
         └────────────────────────────────────────────────────────────┘

Week 6+  ┌────────────────────────────────────────────────────────────┐
         │ PR4 (Profile auto-tune)   │  PR5 (LLM post-mortems)        │
         │                           │  ↑ depends on A.1              │
         └────────────────────────────────────────────────────────────┘
```

### What to tell your partner about timing

> "The ML stack is roughly a week of focused work to hydrate — we built it as a configurable shell deliberately so we could verify the audit and gate logic before pouring in agent intelligence that would make those things harder to debug. **The strategy expressiveness work that came out of your feedback adds another ~5 days** — long-and-short within a single profile, the indicators behind the named strategies you mentioned (VWAP, Keltner, Hurst, Z-Score, RVOL), one-click templates for Mean Reversion / Trend Following / Volatility Squeeze / VWAP Breakout, and regime-gated profile activation so each strategy steps aside when the market isn't right for it. The Second Brain feedback loop on top of that is another month of compounding work. **End of next month, the platform should be measurably self-improving** — observably retuning gate thresholds and agent weights based on its own realized performance, with every change reversible from the dashboard. **That's the milestone where 'observability for agent-driven trading' becomes 'agent-driven trading that observes and improves itself.'**"

### A note on what your feedback already shaped

Your specific suggestions either (a) already exist in the system, (b) were taken into Track C above, or (c) were deferred with a stated reason. The "Considered and deferred" block under Track C lists the items intentionally left out — pairs trading, market making, Rust rewrite, and the dedicated "Specialist Agent per strategy" microservice model. We can revisit any of those if priorities shift; for now they're held back to keep complexity low and make the next-month milestone tractable.

---

## Companion documents

- [`SECOND-BRAIN-PR1-PLAN.md`](./SECOND-BRAIN-PR1-PLAN.md) — what PR1 was and why
- [`SECOND-BRAIN-ROADMAP.md`](./SECOND-BRAIN-ROADMAP.md) — PR2 → PR5 detail (referenced in the dialogue and Track C above)
