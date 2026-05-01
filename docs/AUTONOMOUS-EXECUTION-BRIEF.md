# Autonomous execution brief — all four tracks in one session

> **Purpose:** This document is a self-contained prompt for a Claude Code session
> tasked with executing Tracks A, B, C, and D from
> [`PARTNER-DEMO-SCRIPT.md`](./PARTNER-DEMO-SCRIPT.md) §4 in a single sitting.
> It assumes the executing agent has **no prior conversation context**.
> Read top-to-bottom before touching code.
>
> **Reviewer note (the human):** Edit anything below — provider choices,
> deferral lines, model picks. The execution session will follow this brief
> as written.

---

## 0 · Pre-flight context (read first, in this order)

Before any code change, load context. Spend ≤10 minutes here, then stop reading and start working.

1. `CLAUDE.md` (top-to-bottom; financial-precision rules, hooks, anti-patterns)
2. `docs/PARTNER-DEMO-SCRIPT.md` §4 (the roadmap this brief executes)
3. `docs/SECOND-BRAIN-ROADMAP.md` (PR2-PR5 detail)
4. `docs/SECOND-BRAIN-PR1-PLAN.md` (the audit chain PR2 reads from)
5. `libs/core/schemas.py` (StrategyRulesInput, StrategySignal — these get amended in C.1)
6. `libs/messaging/channels.py` (don't invent channel names)
7. `libs/core/enums.py` (Regime, AgentType, etc.)
8. `services/hot_path/src/processor.py` (the decision pipeline you'll be modifying)
9. `services/ta_agent/src/main.py` (where C.2 indicators land)
10. `run_all.sh` (the only legal way to start/stop services)
11. The `scripts/` directory listing (many helpers already exist — reuse, don't rebuild)

After step 11, **write down on a scratchpad**:
- All services + their ports
- All Redis channels you'll touch
- All `Decimal`-bearing tables and columns
- Any existing scripts that already do something useful

Refer to the scratchpad as you work; the conversation context will get long.

---

## 1 · Mission

Execute all five sub-items of Track A, both items of Track B, all five of Track C, and as much of Track D as fits. **Do not pretend you finished what you didn't.** Honest partial completion (with clear PR-by-PR acceptance verified) is the goal, not optimistic claims of "all done."

Order of work is fixed below. Each item ends with explicit acceptance criteria that **must be verified by running code**, not by reading the diff. If acceptance fails, stop and fix before moving on.

---

## 2 · Hard rules (non-negotiable; from CLAUDE.md)

These rules supersede convenience. Do not violate them even if it would be faster.

1. **`Decimal` for all financial values.** Never `float`. Never `double`. Type aliases live in `libs/core/types.py`. The `edit-validator.sh` PreToolUse hook will block introductions of `float(` in `services/{execution,pnl,risk,strategy}/`.
2. **Redis channels are defined in `libs/messaging/channels.py`.** Do not invent channel names. The hook blocks invented names.
3. **All schemas in `libs/core/schemas.py`.** All enums in `libs/core/enums.py`. Do not duplicate elsewhere.
4. **`bash run_all.sh` is the only legal way to start/stop services.** Use `--stop` to halt, then `--local-frontend` to start. Never start individual services. Never use `kill -9` on tracked PIDs.
5. **Phase boundary respected.** Don't pull Phase 2 patterns (multi-agent, ML-heavy) into Phase 1 unless they're explicitly part of these tracks.
6. **Profile config: `pipeline_config` is authoritative.** `strategy_rules` is a build artifact compiled from the canvas. See `libs/core/pipeline_compiler.py`.
7. **No opportunistic refactors.** When you encounter unrelated tech debt, append to `docs/TECH-DEBT-REGISTRY.md` and move on.
8. **Stale-read guard active.** You must `Read` a file before editing it (in this session); the hook will block otherwise.
9. **No comments narrating what code does.** Only comment when *why* is non-obvious (a constraint, a workaround, a subtle invariant). Never `// added for X`, `// removed because Y`.
10. **Don't fix tests by softening assertions.** If a test fails, the code is wrong (or the test is wrong for principled reasons stated in the PR).

---

## 3 · Tool strategy

The conversation context will fill up. Plan accordingly.

- **Use the `Explore` subagent** for read-only investigations that span >3 files (e.g., "find every place that references `max_allocation_pct`"). Do not use it for editing.
- **Use the `general-purpose` subagent** when you need a heavier multi-step research task with potential synthesis.
- **Parallelize independent calls.** When two file reads or two grep queries don't depend on each other, send them in a single tool message.
- **Use the `Plan` subagent** before starting Track D PR2 / PR3 — these are large enough that an explicit plan prevents drift.
- **Use Grep with `output_mode: "files_with_matches"`** for "where does X live" — cheap, narrow result.
- **Use Read with `offset`/`limit`** when you know roughly where to look in a long file.
- **Don't re-read files** you've already seen this session unless you suspect the on-disk version changed.
- **Save checkpoint state to a small scratchpad markdown file** (e.g., `.execution_scratchpad.md` — not committed) so you can recover if context truncates.

---

## 4 · Verification discipline

After every numbered sub-item:

1. **Run the acceptance test** stated for that item. Don't move on until it passes.
2. **Restart only what's necessary** via `bash run_all.sh --stop && bash run_all.sh --local-frontend`. Wait until all 18 backend `/health` endpoints return 200 before testing the change.
3. **Probe the live behavior** using existing scripts under `scripts/` (e.g., `scripts/probe_state.py`, `scripts/watch_demo_decisions.py`, `scripts/verify_ledger.py`, `scripts/verify_hitl_pending.py`).
4. **Commit the work** with a focused message. **One commit per sub-item; do not bundle.** Use the heredoc commit pattern from CLAUDE.md. Every commit produced in this session must include the umbrella trailers below so the entire session is searchable and revertable as a unit.

### Commit message format (mandatory for every commit in this session)

```
<type>(<scope>): <one-line summary>

<optional body explaining why, not what>

Track-Item: <e.g. A.1, C.2, D.PR2>
Session-Tag: autonomous-execution-<YYYY-MM-DD>
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

`<YYYY-MM-DD>` is fixed for the duration of the session (use the date the session started; do not advance it across midnight). At session start, run `date +%Y-%m-%d` once and reuse the value throughout. Example: `Session-Tag: autonomous-execution-2026-05-01`.

`Track-Item` matches the section heading exactly. For Track D items use `D.PR2`, `D.PR3`, etc. For multi-track work that genuinely cannot be split, use a comma list: `Track-Item: C.1, C.2`. Resist this — splitting is almost always possible.

### At session end

After the final commit, create an annotated git tag pointing at the tip:

```bash
git tag -a session/autonomous-execution-<YYYY-MM-DD> -m "Autonomous execution session — Tracks A/B/C/D"
```

The tag plus the trailer-grep give the human two ways to scope the session:
```bash
git log --grep "Session-Tag: autonomous-execution-2026-05-01"
git log session/autonomous-execution-2026-05-01 --not session/autonomous-execution-2026-05-01^{}~1
```

### Between tracks

Also run:

```bash
poetry run python -m pytest tests/unit/ -x -q 2>&1 | tail -20
```

If any unit test fails, **stop and fix before continuing**. Don't accumulate broken tests across multiple sub-items — the blast radius gets impossible to debug.

---

## 5 · Demo session state (the system you start with)

This brief assumes the system is in roughly the state captured in `PARTNER-DEMO-SCRIPT.md` §3:

- **Mode:** `effective_mode: PAPER`, kill switch off
- **Active profile:** "Demo · Pullback Long" (`c557fcdc-2bc2-4ef3-8004-102cd71859c0`) — RSI<50 AND MACD>0
- **All decisions BLOCKED_HITL** because HITL is enabled and triggers on size
- **TA agent live** producing real scores; sentiment, debate, regime are dark
- **PR1 audit chain merged**, 100% coverage on existing data
- **HITL pending endpoint** `GET /hitl/pending` exists
- **HITL unit math fix** landed; tests in `tests/unit/test_hitl_gate.py` all pass

### Pre-launch prerequisites (verified by the human before this session starts)

- ✅ `ANTHROPIC_API_KEY` set in `.env` at line 25. **Note:** `libs/config/settings.py:35` reads from `LLM_API_KEY` (becomes `PRAXIS_LLM_API_KEY` after env_prefix). Item A.1 must reconcile these two names — see A.1 steps for the alias change.
- ✅ ~94 GB free disk space (verified via `df -h`). Plenty for the ~3 GB SLM model in A.2.
- ⚠️ **`market_data_ohlcv` 1h candles: only ~30 days available** for both BTC/USDT and ETH/USDT (720 bars each, span 2026-04-01 to 2026-05-01). Item A.3's "12 months" assumption does not hold — train on what's available, document the limitation, and accept that 4-state HMM assignment may be noisy on 30 days of data. Do **not** delay A.3 to backfill more history; that's a separate exercise.
- ✅ **Session-bridge env override applied:** `PRAXIS_HITL_CONFIDENCE_THRESHOLD=0.3` (was implicitly `0.5` via default). Reason: with regime currently null and the hardcoded `confidence_multiplier=0.7` fallback in hot_path, the demo profile's `base_confidence=0.65` collapses to `confidence_after=0.455` — below the 0.5 HITL floor — so 84% of decisions were getting blocked by `low_confidence` HITL. With the 0.3 floor, typical confident matches reach APPROVED, giving Tracks A.4, D.PR2, and D.PR3 actual closed-trade signal to consume. **The override is annotated in `.env` lines 18-23 with a `revert when A.3 lands` note** — once HMM emits real regimes (TRENDING_UP → multiplier 1.0), the original 0.5 floor will pass naturally on confident matches and this override should be removed at session end. **`PRAXIS_HITL_SIZE_THRESHOLD_PCT=100` was already in `.env` and remains** — that trigger is fully neutralized; no further change needed there.

If actual state diverges, run `scripts/probe_state.py`, `scripts/watch_demo_decisions.py`, `scripts/verify_ledger.py`, `scripts/check_candle_history.py`, and `scripts/dump_settings.py` to recalibrate before starting.

---

## 6 · Sequenced work plan

### Week 1 layout (do in this order — dependencies inline)

```
Phase 1 (no inter-dependencies; do in parallel where mechanical):
  C.1  Long+short schema           [hot_path + schema]
  C.2  New indicators              [ta_agent only]
  A.1  LLM hydration               [debate + sentiment services]
  A.2  slm_inference model         [slm_inference service]
  A.3  HMM training                [regime_hmm service]
  B.1  Pipeline editor live state  [frontend only]
  B.2  Backtest history            [api_gateway + frontend]

Phase 2 (depends on Phase 1):
  C.3  Profile templates           [needs C.1 schema, C.2 indicators]
  C.4  Regime-gated profiles       [needs A.3 hydrated regimes]
  C.5  Shadow trades flag          [small, can do anytime]
  A.4  ML validation               [needs A.1 + A.2 + A.3]

Phase 3 (Second Brain):
  D.PR2  Insight engine            [reads PR1 ledger + Track A signals]
  D.PR3  Adaptive weights          [needs PR2 metrics + C.5 shadow data]
  D.PR4  Profile auto-tuning       [stretch — only if Phase 1+2 finished cleanly]
  D.PR5  LLM post-mortems          [stretch — needs A.1 working]
```

When in doubt about dependencies, check the dependency graph in `PARTNER-DEMO-SCRIPT.md` §4.

---

## 7 · Per-item briefs

Each block has: **Goal**, **Files**, **Steps**, **Acceptance**, **Test command**, **Out of scope**.

When the brief says "do X", do exactly X. When it says "consider Y", that's a hint. When it says "NEVER Z", that's a hard constraint.

---

### Item C.1 — Long + short conditions in one profile

**Goal:** A single profile can declare `entry_long` and/or `entry_short` rule blocks. The hot-path evaluates both each tick.

**Files:**
- `libs/core/schemas.py` — `StrategyRulesInput`, `StrategySignal`, `strategy_rules_to_canonical`, `strategy_rules_from_canonical`
- `services/hot_path/src/strategy_eval.py` (or wherever rules are evaluated; grep first)
- `services/strategy/src/compiler.py` — `CompiledRuleSet`
- New migration `migrations/versions/018_long_short_profiles.sql` to backfill existing profiles
- `tests/unit/test_strategy_*.py` — extend coverage

**Steps:**
1. Read `libs/core/schemas.py` lines 415-480 to understand current shape.
2. Add a `StrategyRulesInputV2` (or extend `StrategyRulesInput` with optional fields) supporting:
   - `entry_long: Optional[List[StrategySignal]]`
   - `entry_short: Optional[List[StrategySignal]]`
   - `match_mode_long: Optional[Literal["all","any"]]`
   - `match_mode_short: Optional[Literal["all","any"]]`
   - `confidence: float` (shared)
3. Maintain back-compat: a profile with only the legacy `direction`+`signals` parses as one-sided.
4. Update canonical converter so the canonical form has both legs explicitly (`{"entry_long": {...}, "entry_short": {...}}`).
5. Update `CompiledRuleSet` to carry both legs.
6. In `strategy_eval`, evaluate long block then short block; emit BUY signal, SELL signal, or none. If both match in the same tick → log a warning and emit neither (avoid contradictory simultaneous signals; see "Out of scope").
7. Write migration 018 that converts every existing profile's canonical `strategy_rules` to the new shape (`direction: BUY` → `entry_long: {...}`, etc.). Idempotent.
8. Hot-path stays single-symbol single-direction in execution — long and short signals emit independent decisions.
9. Frontend already accepts arbitrary `rules_json`, so no UI change is strictly needed for this item — C.3 templates will exercise both legs.

**Acceptance:**
- A profile with both `entry_long` and `entry_short` produces BUY decisions when long conditions match, SELL decisions when short conditions match.
- Existing single-direction profiles continue producing the same decisions they did before.
- New unit tests cover: legacy parses, both-legs parses, only-long parses, only-short parses, both-match-tick (warning + no signal).

**Test command:**
```bash
poetry run python -m pytest tests/unit/test_strategy_eval.py tests/unit/test_schemas.py -v
# Plus a manual smoke test: create a both-legs profile via API, watch decisions appear
poetry run python scripts/create_demo_profile.py  # adapt to create a both-legs profile
```

**Out of scope:**
- Multi-leg simultaneous orders (pairs trading). A single profile firing both BUY and SELL on the same tick is a *warning condition*, not a feature.
- Cross-symbol correlation. Each profile remains tied to its symbol-stream, no cross-symbol logic.

---

### Item C.2 — New indicators in TA agent

**Goal:** Five new indicators emitted by the TA agent and queryable via the strategy DSL: VWAP, Keltner Channel, RVOL, Z-Score, Hurst Exponent.

**Files:**
- `libs/indicators/` — implementations
- `services/ta_agent/src/main.py` — emit the new fields
- `libs/core/schemas.py` — extend `StrategySignal.indicator` Literal
- Tests in `tests/unit/test_indicators_*.py`

**Steps:**
1. Read `libs/indicators/__init__.py` to see existing convention.
2. Implement each indicator as a pure function over OHLCV with `Decimal` math:
   - **VWAP:** rolling cumulative `Σ(close × volume) / Σ(volume)` since session start (or a 24h rolling window — pick one and document).
   - **Keltner Channel:** EMA(close, 20) ± 2 × ATR(20). Returns upper/middle/lower.
   - **RVOL:** `current_volume / SMA(volume, 20)`.
   - **Z-Score:** `(close - SMA(close, 20)) / stdev(close, 20)`. Numerator is in price units; denominator the same; result dimensionless.
   - **Hurst Exponent:** R/S analysis over a rolling 50-bar window. Use `numpy` and document the algorithm choice. Latency target: <5ms per tick on consumer hardware. If too slow, drop to 30-bar window.
3. Add unit tests with hand-computed expected values for each indicator (one canonical test case per indicator, asserting Decimal equality to 6 decimal places).
4. Expose each as a field in `EvaluatedIndicators` and emit on the agent's published payload.
5. Extend `StrategySignal.indicator` Literal: `"vwap"`, `"keltner.upper"`, `"keltner.middle"`, `"keltner.lower"`, `"rvol"`, `"z_score"`, `"hurst"`.
6. Update `strategy_rules_to_canonical` mapping for new indicators.
7. Update `_INDICATOR_USER_TO_CANONICAL` map (grep `libs/core/schemas.py`).

**Acceptance:**
- A profile with `entry_long: [{indicator: "vwap", comparison: "above", threshold: 0}]` (treating threshold as "vs price") produces matched decisions when close > vwap.
- Each indicator has a unit test with hand-computed canonical values.
- TA agent's published payload includes all five new fields.

**Test command:**
```bash
poetry run python -m pytest tests/unit/test_indicators_vwap.py tests/unit/test_indicators_keltner.py tests/unit/test_indicators_rvol.py tests/unit/test_indicators_zscore.py tests/unit/test_indicators_hurst.py -v
# Live verification:
curl -s http://localhost:8090/health  # ta_agent
poetry run python scripts/probe_state.py  # check /agents/status payload (extend the probe script if needed)
```

**Out of scope:**
- Alternative VWAP windows. Pick one (24h rolling is sensible for crypto), document, ship.
- Order-book-derived indicators (e.g., bid-ask spread). That's market-making territory; deferred.
- Streaming Hurst with live update. A simple recompute-on-each-tick is fine if it stays under budget.

---

### Item A.1 — LLM-driven agents (Debate + Sentiment hydration)

**Goal:** Debate engine produces real bull/bear arguments. Sentiment agent emits non-zero scores from real headlines.

**Files:**
- `services/debate/src/engine.py`
- `services/sentiment/src/main.py`
- `.env` — `PRAXIS_LLM_API_KEY` (the human will set this, do **not** generate keys)
- `libs/config/settings.py` — confirm the env name expected
- A new sentiment ingestion worker if needed

**Steps:**
1. **Reconcile the env name.** The human's `.env` has `ANTHROPIC_API_KEY` (no `PRAXIS_` prefix), but `libs/config/settings.py:35` reads `LLM_API_KEY` (resolved as `PRAXIS_LLM_API_KEY` via the `PRAXIS_` env_prefix). Two acceptable fixes; pick one and apply it once:
   - **Option A (preferred):** add `validation_alias=AliasChoices("PRAXIS_LLM_API_KEY", "ANTHROPIC_API_KEY")` to the `LLM_API_KEY` field so it reads from either. Add `from pydantic import AliasChoices` if missing.
   - **Option B:** add a line `PRAXIS_LLM_API_KEY=${ANTHROPIC_API_KEY}` (or copy the literal value) to `.env`.
   Document the choice in the commit message.
2. **Verify the value loads.** `poetry run python -c "from libs.config import settings; print(bool(settings.LLM_API_KEY))"` should print `True`. If it doesn't, stop and ask the human — don't proceed with a missing key.
3. **Smoke-test debate manually.** Send one bull/bear cycle programmatically (call the engine's generate function directly from a one-off script in `scripts/smoke_debate.py`). Log the raw LLM response, confirm the parser doesn't fail.
3. **Fix the parser if it fails.** Common failure modes: response has extra prose around the JSON; truncation; unexpected punctuation. Use `pydantic` model `model_validate_json` with a tolerant pre-clean pass.
4. **Confirm transcripts persist.** Run for ~5 minutes, query `debate_transcripts` table; expect ≥1 row with `bull_argument NOT LIKE 'Failed%'`.
5. **For sentiment:** wire a minimal news source. Recommended path of least resistance: free RSS feeds from CoinDesk / CryptoSlate / Reddit `/r/CryptoCurrency`. Use `feedparser`.
6. **Score each headline with the same LLM.** Prompt: "On a scale -1.0 (very bearish) to +1.0 (very bullish), score this headline for {symbol}: {headline}. Respond with only a number."
7. **Publish to the existing Redis key** `agent:sentiment:{symbol}` (verify the exact key name with `grep -rn "agent:sentiment" libs/ services/`). Hot-path already reads it.
8. **Run-rate guardrail.** If sentiment scoring exceeds N requests/min, downsample. Don't take down the LLM bill.

**Acceptance:**
- `scripts/debate_quality.py` reports ≥80% real (non-"Failed") arguments after 30 min of runtime.
- `/agents/status` returns non-zero `sentiment_score` for at least BTC/USDT and ETH/USDT.
- The `dark` chip on Sentiment + Debate disappears in the chart legend on `/trade`.

**Test command:**
```bash
poetry run python scripts/debate_quality.py
poetry run python scripts/probe_state.py | grep -A3 'AGENTS STATUS'
```

**Out of scope:**
- Twitter/X API integration (paid).
- Custom-fine-tuned sentiment model (Phase 2 stretch goal).
- Multi-language headlines.

---

### Item A.2 — slm_inference model loading

**Goal:** `services/slm_inference/` reports `model_loaded: true` and serves inference under 100ms p99.

**Files:**
- `services/slm_inference/src/main.py`
- `docker/slm_inference.Dockerfile` (if it exists; otherwise create)
- `.env` — `PRAXIS_SLM_MODEL_PATH`

**Steps:**
1. Pick model: **Phi-3-mini-4k-instruct GGUF Q4_K_M** (~2.4GB). Download from HuggingFace via `huggingface-cli download microsoft/Phi-3-mini-4k-instruct-gguf Phi-3-mini-4k-instruct-q4.gguf` to `models/slm/`.
2. Wire the service to load via `llama-cpp-python` (CPU-first; GPU only if explicitly enabled).
3. Set `PRAXIS_SLM_MODEL_PATH=models/slm/Phi-3-mini-4k-instruct-q4.gguf` in `.env`.
4. Add `models/` to `.gitignore` if it isn't already.
5. On service startup, load model; on success update `/health` to report `model_loaded: true` and `model_path: <abs path>`.
6. Add a `POST /infer` endpoint accepting `{prompt: str, max_tokens: int}` and returning the generated text.
7. Benchmark: 20 sequential requests with 50-token prompts; p99 latency must be <100ms (or note the actual number; 100ms is aspirational on CPU).

**Acceptance:**
- `curl :8095/health` returns `{"status":"healthy","model_loaded":true,"model_path":"...","load_time_ms":<n>}`.
- `curl -X POST :8095/infer -d '{"prompt":"hello","max_tokens":10}'` returns text within budget.

**Test command:**
```bash
curl -s http://localhost:8095/health | python -m json.tool
poetry run python scripts/benchmark_slm.py  # write this if missing; 20 requests, report p50/p95/p99
```

**Out of scope:**
- Routing debate/sentiment through `slm_inference` instead of remote API. That's a follow-up optimization. A.2 just makes the service real.
- Quantization beyond Q4_K_M.
- Fine-tuning on financial data.

---

### Item A.3 — HMM regime classifier

**Goal:** `services/regime_hmm/` emits non-null `regime` for live symbols based on a trained HMM.

**Files:**
- `services/regime_hmm/src/main.py`
- `services/regime_hmm/src/trainer.py` (new — training script)
- `models/regime_hmm_{symbol}.pkl` (artifact, not committed; add `models/` to `.gitignore` if needed)
- `libs/core/enums.py` — confirm `Regime` states
- `services/hot_path/src/processor.py` — wire `confidence_multiplier` per regime

**Steps:**
1. **Confirm `Regime` enum.** If states aren't exactly `TRENDING_UP`, `TRENDING_DOWN`, `RANGING`, `HIGH_VOLATILITY` (4 states), **note the actual states and use those**. Do not silently re-define the enum.
2. **Pull training data.** As of session start, only ~30 days of 1h candles exist per symbol (720 bars each). Use all of it. **Caveat to record in the commit message and the validation report:** 4-state HMM assignment on 30 days of data will be noisy and is a known limitation. Do not attempt to backfill candle history or aggregate up from 1m as part of this item — record the limitation, ship what we can, move on.
3. **Feature engineering.** Per-bar features: `log_return = ln(close_t / close_{t-1})`, `realized_vol = stdev(log_return, 24)`, `range_ratio = (high - low) / atr_24`. Standardize per-symbol before fitting.
4. **Fit Gaussian HMM** with 4 components using `hmmlearn.hmm.GaussianHMM`. Random seed fixed; document it.
5. **Map states to regimes.** After fit, inspect each state's mean feature vector to assign Regime labels (highest mean log_return → TRENDING_UP, lowest → TRENDING_DOWN, lowest realized_vol → RANGING, highest realized_vol → HIGH_VOLATILITY). Persist this mapping with the checkpoint.
6. **Persist** to `models/regime_hmm_{symbol}.pkl` with `{model, scaler, state_mapping, trained_at, training_window}`.
7. **Service startup:** load checkpoint per symbol. Reject if `trained_at` is older than 30 days (forces retrain).
8. **Live emission:** on each new candle, transform features, run `predict_proba`, take argmax → regime. Publish to `agent:hmm_regime:{symbol}` Redis key (verify exact key name in `libs/messaging/channels.py`).
9. **Hot-path consumer:** confirm `confidence_multiplier` is now driven by the live regime instead of the hardcoded 0.7. Multipliers (configurable via env):
   - `TRENDING_UP=1.0`
   - `TRENDING_DOWN=0.5` (long-only stops)
   - `RANGING=0.8`
   - `HIGH_VOLATILITY=0.6`
10. Add a one-shot training script `scripts/train_hmm.py` runnable from CLI; `services/regime_hmm/` retrains on schedule (cron not required for this brief).

**Acceptance:**
- `/agents/status` returns non-null `hmm_regime` and `hmm_state_index` for BTC/USDT and ETH/USDT.
- `dark` chip on REGIME disappears in the chart legend.
- Hot-path applies regime-specific confidence multiplier (verify by reading a fresh trade decision's `regime.confidence_multiplier`).

**Test command:**
```bash
poetry run python scripts/train_hmm.py --symbol BTC/USDT
poetry run python scripts/train_hmm.py --symbol ETH/USDT
bash run_all.sh --stop && bash run_all.sh --local-frontend
poetry run python scripts/probe_state.py | grep -A3 'AGENTS STATUS'
```

**Out of scope:**
- More than 4 states.
- Deep-learning regime classifiers.
- Per-timeframe regimes.
- Retraining cron.

---

### Item A.4 — ML stack validation

**Goal:** Quantify whether the hydrated stack actually changes decisions, and produce a partner-facing receipt.

**Files:**
- New `scripts/ml_validation.py`

**Steps:**
1. **Snapshot pre-hydration outcome distribution.** From `trade_decisions` over the last 24h before A.1-A.3 landed: counts by outcome.
2. **Wait 24h post-hydration** (or, for this brief's purposes, a documented shorter window with a caveat).
3. **Compare distributions.** Expected: more APPROVED, more BLOCKED_REGIME (which was 0 before), shifted abstention rate.
4. **Backtest replay.** Run `services/backtesting/` with a representative profile against the same 14-day historical window twice: once with hydrated agents (current state), once with hydrated=false flag. Compare:
   - Win rate
   - Sharpe
   - Max drawdown
   - Total trades
5. **Write the result to `docs/ML-VALIDATION-{date}.md`** with one paragraph of interpretation. If hydrated stack doesn't beat TA-only by ≥10% on Sharpe, **flag it** — that means PR3 (adaptive weights) is more urgent than expected and the regime calibration probably needs work.

**Acceptance:**
- A markdown report exists at `docs/ML-VALIDATION-{date}.md` with pre/post outcome distributions and backtest comparison.

**Test command:**
```bash
poetry run python scripts/ml_validation.py --output docs/ML-VALIDATION-$(date +%Y-%m-%d).md
```

**Out of scope:**
- Statistical significance testing (sample sizes are too small for robust p-values; descriptive stats are fine).
- A/B test infrastructure.

---

### Item B.1 — Pipeline editor live state + controls

**Goal:** `/strategies` → Builder tab (which embeds `/pipeline`) shows each gate node colored by live state with live block-rate counters; toggle controls hot-apply via `config_changes`.

**Files:**
- `frontend/app/pipeline/page.tsx`
- `frontend/components/pipeline/*.tsx` — node renderers
- `frontend/lib/api/client.ts` — add gate analytics + toggle endpoints
- `services/api_gateway/src/routes/agent_config.py` — gate toggle endpoint (if missing)
- `services/hot_path/src/main.py` — consume gate config from Redis

**Steps:**
1. **Verify the gate analytics endpoint exists** (`GET /agent-performance/gate-analytics/{symbol}`). It does — it powers the Performance Review drawer. Reuse.
2. **Add a `GET /agent-config/gates`** endpoint returning current state of every gate (enabled/disabled, threshold, last block rate). Backed by Redis key `gate_config:*`.
3. **Add `PATCH /agent-config/gates/{gate_name}`** accepting `{enabled?: bool, threshold?: number}`. Writes to Redis, logs to `config_changes` table, hot_path picks up on next tick.
4. **In `pipeline/page.tsx`,** add a poll loop (every 10s) to fetch gate analytics and gate config.
5. **Color nodes** by live state:
   - `enabled && block_rate < 50%` → green
   - `enabled && block_rate >= 50%` → amber
   - `!enabled` → grey, with "DISABLED" label overlay
6. **Annotate each gate node** with its block rate ("blocked 83% of last hour").
7. **Toggle UI:** right-click a gate node → context menu with "Enable / Disable" and a slider for threshold. Apply via `PATCH`.
8. **Show "Live" indicator** somewhere prominent so users know the canvas reflects reality, not just the saved config.

**Acceptance:**
- Open `/strategies` → Builder tab. Every gate node has a color reflecting its live state. The regime gate (currently disabled per the demo) shows grey.
- Toggle the regime gate via the UI; verify within 10s that the block rate counter starts changing.
- `config_changes` table has a new row for the toggle.

**Test command:**
```bash
curl -s http://localhost:8000/agent-config/gates -H "Authorization: Bearer $TOKEN" | python -m json.tool
# UI test: visual inspection at http://localhost:3000/strategies
```

**Out of scope:**
- Editing gate logic itself (e.g., changing what abstention checks). Only enabled/disabled + threshold.
- Per-profile gate overrides. Global only.
- Undo/redo. The `config_changes` log is the audit trail; manual revert via a follow-up PATCH is fine.

---

### Item B.2 — Backtest history persistence + UI

**Goal:** Completed backtest runs persist to `backtest_results` table; `/backtest` shows a "Run history" panel with sortable past runs.

**Files:**
- `services/backtesting/src/job_runner.py` — write results to DB on completion
- `migrations/versions/019_backtest_results_extra_fields.sql` (if existing schema lacks fields)
- `services/api_gateway/src/routes/backtest.py` — add `GET /backtest/history`
- `frontend/app/backtest/page.tsx` — add Run history panel
- `frontend/lib/api/client.ts` — add `api.backtest.history`

**Steps:**
1. **Confirm `backtest_results` table exists and has the right columns** (per CLAUDE.md §2D, migration 009 made it Decimal). If it lacks `created_by` (user_id) or `profile_id`, add migration 019.
2. **Patch `job_runner.py`** to insert a row into `backtest_results` on completion. Include all metrics + a JSONB column for the equity curve.
3. **Add `GET /backtest/history?profile_id=&user_id=&limit=20`** in api_gateway. Returns rows newest-first.
4. **Frontend:** new `RunHistoryPanel` component on `/backtest` showing list with date, symbol, period, headline metrics, "load" button.
5. **Click "load"** → fetch full result via existing `GET /backtest/{job_id}` and inject into the comparison table as if it were a fresh run.
6. **Pin/unpin** persisted in localStorage (no schema change needed).

**Acceptance:**
- Run a backtest. Refresh the page. The run appears in Run history.
- Click load on a past run. Equity curve overlays the comparison table.

**Test command:**
```bash
# Submit a backtest via the UI or:
curl -X POST http://localhost:8000/backtest/ -H "Authorization: Bearer $TOKEN" -d '{...}'
# Wait for completion, then:
curl -s http://localhost:8000/backtest/history -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

**Out of scope:**
- Cross-user run sharing. user-scoped only.
- Run replay against fresh data (a different feature).

---

### Item C.3 — Profile templates

**Goal:** `/strategies` shows a "Templates" section with one-click profile creation for four strategies.

**Files:**
- `frontend/app/strategies/templates.json` (new)
- `frontend/components/strategies/TemplateGallery.tsx` (new)
- `frontend/app/strategies/page.tsx` — include the gallery on the Profiles tab

**Steps:**
1. Create `templates.json` with entries:
   ```json
   [
     {
       "id": "mean-reversion",
       "name": "Mean Reversion",
       "description": "Buy oversold dips, sell overbought peaks. Best in ranging markets.",
       "preferred_regimes": ["RANGING"],
       "rules": {
         "entry_long":  {"match_mode": "all", "signals": [{"indicator": "rsi", "comparison": "below", "threshold": 30}, {"indicator": "z_score", "comparison": "below", "threshold": -2.0}]},
         "entry_short": {"match_mode": "all", "signals": [{"indicator": "rsi", "comparison": "above", "threshold": 70}, {"indicator": "z_score", "comparison": "above", "threshold": 2.0}]},
         "confidence": 0.65
       }
     },
     {"id": "trend-following", ... },
     {"id": "volatility-squeeze", ... },
     {"id": "vwap-breakout", ... }
   ]
   ```
2. `TemplateGallery` renders cards for each entry with a "Create profile" button.
3. Clicking creates a profile via `api.profiles.create({name: template.name, rules_json: template.rules, allocation_pct: 1.0})`.
4. After creation, navigate to the Profiles tab with the new profile selected.

**Acceptance:**
- Each template clones into a working profile with one click.
- Created profile fires decisions matching its rules.

**Test command:**
- Manual UI test only (this is a UX item).

**Out of scope:**
- Editing template rules (just pre-populate; user edits via the regular profile editor).
- Custom user-saved templates (Phase 2).

---

### Item C.4 — Regime-gated profile activation

**Goal:** A profile with `preferred_regimes` set produces zero live decisions outside those regimes; instead emits `BLOCKED_REGIME_MISMATCH` shadow decisions (paired with C.5).

**Files:**
- `libs/core/schemas.py` — add field to canonical/user shapes
- `libs/core/models.py` — `TradingProfile`
- `services/hot_path/src/processor.py` — gate logic
- `migrations/versions/020_preferred_regimes.sql`
- `libs/core/enums.py` — confirm `Outcome` enum has `BLOCKED_REGIME_MISMATCH` (add if not)

**Steps:**
1. Add `preferred_regimes: List[str]` to `StrategyRulesInput` (canonical converter passes through).
2. Migration 020 adds `preferred_regimes JSONB DEFAULT '[]'` to `trading_profiles` (or stores it inside `strategy_rules` JSONB — pick one and document).
3. **Hot-path:** before `strategy_eval`, check `current_regime in profile.preferred_regimes`. If not (and `preferred_regimes` is non-empty), short-circuit with `outcome=BLOCKED_REGIME_MISMATCH`, `shadow=true`. Continue to record agent scores etc. for shadow analysis.
4. Add `BLOCKED_REGIME_MISMATCH` to the `Outcome` enum.

**Acceptance:**
- A profile with `preferred_regimes: ["RANGING"]` produces zero live decisions while regime is `TRENDING_UP`. Shadow decisions still appear with `shadow=true` and `outcome=BLOCKED_REGIME_MISMATCH`.

**Test command:**
```bash
# Set demo profile's preferred_regimes to a regime != current
poetry run python scripts/set_preferred_regimes.py --profile c557fcdc-... --regimes RANGING
poetry run python scripts/watch_demo_decisions.py  # confirm BLOCKED_REGIME_MISMATCH appears
```

**Out of scope:**
- Per-condition regime preferences. Profile-level only.
- Allowing the user to override regime in the UI mid-trade.

---

### Item C.5 — Shadow trades flag

**Goal:** Trade decisions blocked by C.4 still record in `trade_decisions` with `shadow=true`. PR3 (Track D) consumes them.

**Files:**
- `migrations/versions/021_shadow_decisions.sql` — add `shadow BOOLEAN DEFAULT FALSE` to `trade_decisions`
- `libs/storage/repositories/decision_repo.py` — accept `shadow` flag
- `services/hot_path/src/processor.py` — set `shadow=true` for regime-mismatch decisions
- `services/api_gateway/src/routes/paper_trading.py` — `decisions` endpoint should optionally filter by shadow

**Steps:**
1. Migration 021 — additive column, backfill existing rows to `shadow=false`.
2. Decision repo's insert accepts optional `shadow` param (default false).
3. C.4's BLOCKED_REGIME_MISMATCH path passes `shadow=true`.
4. `/paper-trading/decisions?shadow=false` (default) excludes shadow rows so the Decision Feed UI is unchanged.

**Acceptance:**
- After C.4 takes effect, `SELECT COUNT(*) FROM trade_decisions WHERE shadow=true` increases over time.
- Default Decision Feed (no `shadow` param) shows no shadow rows.
- `/paper-trading/decisions?shadow=true` returns shadow rows.

**Test command:**
```bash
psql $PRAXIS_DATABASE_URL -c "SELECT shadow, COUNT(*) FROM trade_decisions GROUP BY shadow"
```

**Out of scope:**
- UI surface for shadow rows. PR3 / drawer surfaces them; this just plumbs the data.

---

### Item D.PR2 — Insight Engine

**Goal:** Worker computes gate efficacy + agent attribution + close-reason taxonomy + strategy-rule heatmap from the audit chain. Endpoints + UI panels expose them.

This is a multi-day item. **Do an explicit Plan subagent call before starting.** The brief in `SECOND-BRAIN-ROADMAP.md` is the source of truth.

Sketch:
- `services/analyst/src/insight_engine.py` — periodic worker (6h cadence)
- New table `gate_efficacy_reports` (migration 022)
- Endpoints `GET /agent-performance/gate-efficacy/{symbol}`, extend `/agent-performance/attribution/{symbol}` for agreement-pattern
- New panels in Performance Review drawer

**Acceptance (minimum viable):**
- Gate efficacy report runs against the demo profile's history, returns "blocked-set would-be P&L" vs "passed-set realized P&L" per gate.
- New table populated; endpoint returns it.
- Drawer has a new "Gate Efficacy" sub-panel rendering it.

If the full PR2 doesn't fit the session, do at minimum: gate efficacy. Skip attribution + heatmap + close-reason for a follow-up.

---

### Item D.PR3 — Adaptive weights

**Goal:** Worker reads PR2 metrics + C.5 shadow data, retunes agent weights and gate thresholds, writes to `config_changes`.

**Heavy item; do a Plan subagent call before starting.** Source of truth is `SECOND-BRAIN-ROADMAP.md` PR3 section.

Sketch:
- `services/analyst/src/weight_tuner.py` — hourly cadence
- `services/analyst/src/gate_calibrator.py` — separate worker for gate threshold proposals
- Bounds: ±5% per cycle for weights, ±10% for gate thresholds, hard floors/ceilings
- Min sample size: 50 closed trades before any weight change

**Acceptance (minimum viable):**
- Weight tuner runs once and writes ≥1 row to `agent_weight_history` based on real EWMA accuracy from `closed_trades`.
- Hot-path Analyst reads the new weight on next tick.
- `config_changes` has a row documenting the tune.

If the gate calibrator doesn't fit, ship the weight tuner only.

---

### Item D.PR4 — Profile auto-tuning (stretch)

**Only attempt if Phases 1+2 finished cleanly with time remaining.** This is a substantial feature (suggestor + shadow profile mode + UI). If skipping, write a brief paragraph in the ML validation report explaining why.

---

### Item D.PR5 — LLM post-mortems (stretch, depends on A.1)

**Only attempt if A.1 is fully working** (debate transcripts hydrated). If A.1 is partial, skip — generating post-mortems on placeholder transcripts is worse than not generating them.

If shipping: write `services/analyst/src/postmortem_writer.py` that takes a `closed_trades.position_id` + the joined audit chain + the debate transcript and produces a 2-3 paragraph narrative, persisted to a new `trade_postmortems` table.

---

## 8 · Final acceptance — full system test

After all (or as many as fit) tracks land, run end-to-end:

```bash
# 1. All services healthy
for port in 8000 8080 8081 8082 8083 8084 8085 8086 8087 8088 8089 8090 8091 8092 8093 8094 8095 8096; do
  curl -s -m 1 -f http://localhost:$port/health > /dev/null && echo "OK $port" || echo "FAIL $port"
done

# 2. Frontend renders all main pages
for path in / /trade /strategies /backtest /pipeline /profiles; do
  curl -s -o /dev/null -m 5 -w "$path %{http_code}\n" http://localhost:3000$path
done

# 3. PR1 audit chain still verified
poetry run python scripts/verify_ledger.py

# 4. ML hydration verified
poetry run python scripts/probe_state.py
# Expect: TA, sentiment, hmm_regime all non-null/non-zero

# 5. Decision feed has APPROVED outcomes (HITL fix should now let real trades through given the broader gate behaviors)
poetry run python scripts/watch_demo_decisions.py

# 6. Unit tests
poetry run python -m pytest tests/unit/ -q

# 7. ML validation report
ls -la docs/ML-VALIDATION-*.md
```

Then, **write a session report** to `docs/EXECUTION-REPORT-{date}.md` containing:
- Items completed (with commit SHAs)
- Items partial (with state and what's blocking finish)
- Items skipped (with reason)
- New tech debt added to `docs/TECH-DEBT-REGISTRY.md`
- Any deviations from this brief

---

## 9 · Anti-patterns to actively avoid

In a session this large, the easy mistakes are predictable. Stay alert for:

- **Over-confident "all done" claims.** Every acceptance criterion is verified by a command, not by a glance at the diff. If the command wasn't run, don't claim done.
- **Generic exception swallowing.** `except Exception: pass` in financial code is malpractice. Failures must propagate or be explicitly handled with a logged reason.
- **Adding columns to tables that contradict CLAUDE.md §2A.** All new financial columns are `NUMERIC` / `Decimal`. Period.
- **Inventing Redis keys or channels.** If a key doesn't exist in `libs/messaging/channels.py` or isn't already in use somewhere, you're inventing. Stop and check.
- **Touching unrelated files because "while I'm here."** No. `TECH-DEBT-REGISTRY.md` is the only valid response to opportunistic improvements.
- **Commit-bombing.** One commit per sub-item; the diff should be reviewable. If a sub-item touches >20 files and you can't articulate why, that's a sign of scope creep.
- **Assuming the human's intent.** When the brief says "ask the human," ask. Don't guess.

---

## 10 · When to stop and ask

Stop the session and ask the human if any of these happen:

- A required env var (`PRAXIS_LLM_API_KEY`, etc.) is missing.
- A migration would require dropping or altering a column with existing data of unknown structure.
- A unit test fails *for a principled reason* (not a typo) and the right fix is non-obvious.
- An acceptance criterion is met by the diff but not by the live system, and you can't reconcile.
- The conversation context is approaching its limit and you've completed a full track but not the next one — checkpoint and ask before continuing.
- You realize a deferred item (pairs trading, market making, Rust rewrite) was being snuck in via the back door of one of the in-scope items.

In all cases, write a checkpoint note in the scratchpad and explicitly state what you're stopping on.

---

## 11 · Honesty hooks

The post-execution session report must explicitly call out:

- **Untested assumptions.** Anything written without a command verifying it.
- **Test cases that mocked things that should be real.** "I had to mock X because Y" — useful information.
- **Code paths that compile but might be wrong.** "The HMM training fits without errors but I haven't validated state assignment is right."
- **Performance numbers that are estimates rather than measurements.** "p99 latency *should* be under 100ms based on the algorithm; I didn't benchmark."

A long session that ships partial work *honestly* is more valuable than one that ships full work with hidden brittleness.

---

## 12 · The end

When all in-scope items are either landed or honestly reported as partial:

1. Write the session report to `docs/EXECUTION-REPORT-{date}.md`.
2. Commit it with the same trailer convention (Track-Item: `session-report`).
3. Create the umbrella git tag:
   ```bash
   git tag -a session/autonomous-execution-$(date +%Y-%m-%d) -m "Autonomous execution session — Tracks A/B/C/D"
   ```
4. Stop. Do not pile on optional polish — the marginal value is low and the regression risk is high.

Good luck.
