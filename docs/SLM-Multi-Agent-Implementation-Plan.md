# Multi-Agent SLM Trading Engine — Implementation Plan

## Context

The Gemini blueprint describes an ideal multi-agent SLM-driven trading engine with local model inference, adversarial debate, statistical arbitrage, candlestick CNNs, knowledge graphs, and more. The Aion platform already has a solid foundation — 17 microservices, 3 ML agents (TA, Sentiment, Regime HMM), a 9-stage hot-path pipeline, and Redis-based agent score aggregation. This plan identifies what to build incrementally, prioritized by impact and feasibility for a solo developer.

## Gap Analysis (Blueprint vs Current State)

| Blueprint Feature | Current State | Priority |
|---|---|---|
| Extended indicators (ADX, BB, OBV, CHOP) | Only RSI, MACD, ATR, EMA | **P1** |
| Dynamic agent weighting | Hardcoded ±0.20 TA, ±0.15 sentiment | **P1** |
| HITL execution gate | No approval workflow, no kill switch | **P2** |
| Local SLM inference | Cloud Claude Haiku API only | **P2** |
| Adversarial bull/bear debate | Not implemented | **P3** |
| VectorBT backtesting | Custom sequential simulator only | **P3** |
| Statistical arbitrage | Not implemented | **Deferred** |
| Candlestick CNN | Not implemented | **Deferred** |
| Knowledge graph / 2nd brain | Redis cache only | **Deferred** |
| LoRA fine-tuning pipeline | Not implemented | **Deferred** |

---

## Phase 1: Expand Technical Indicator Library

**Why**: Zero-risk, pure library additions that immediately enrich TA Agent scoring and enable new strategy rules. No hot-path latency impact (each indicator is O(1) incremental).

### New files to create in `libs/indicators/`:

- **`_adx.py`** — ADX/DMI (Wilder smoothing). `update(high, low, close) -> Optional[float]`. Same pattern as `ATRCalculator`.
- **`_bollinger.py`** — Bollinger Bands returning `BollingerResult(upper, middle, lower, bandwidth, pct_b)`. Rolling window.
- **`_obv.py`** — On-Balance Volume. `update(close, volume) -> Optional[float]`. Cumulative sum.
- **`_choppiness.py`** — Choppiness Index. `update(high, low, close) -> Optional[float]`. Uses ATR sum / range.

### Files to modify:

- **`libs/indicators/__init__.py`** — Add new imports, extend `IndicatorSet.__slots__` with optional fields (default `None` for backward compat), update `create_indicator_set()`
- **`services/ta_agent/src/confluence.py`** — Add ADX trend-strength weighting, Bollinger %B as 3rd signal dimension, Choppiness as regime filter
- **`services/hot_path/src/strategy_eval.py`** — Compute new indicators, add to `EvaluatedIndicators` dataclass and `eval_dict`
- **`services/strategy/src/compiler.py`** — Register new indicator keys (`adx`, `bb.pct_b`, `bb.bandwidth`, `obv`, `choppiness`)
- **`services/backtesting/src/simulator.py`** — Compute new indicators in replay loop

### Verification:
- Unit tests for each new indicator against known reference values
- Run existing TA agent and verify enriched confluence scores
- Backtest a strategy using new indicators (e.g., RSI < 30 AND bb.pct_b < 0)

---

## Phase 2: Dynamic Agent Weighting (Matrix-Weighted Consensus)

**Why**: Highest-impact architectural change. Replaces hardcoded magic constants in `agent_modifier.py:64,90` with performance-tracked dynamic weights. The blueprint's "matrix-weighted consensus" directly maps here.

### Integration point: `services/hot_path/src/agent_modifier.py`

Current code (line 32): `new_confidence = signal.confidence + ta_adj + sentiment_adj`
- TA max adjustment: hardcoded ±0.20
- Sentiment max adjustment: hardcoded ±0.15

### New files:

- **`libs/core/agent_registry.py`** — `AgentPerformanceTracker` backed by Redis hashes
  - Stores rolling window of (prediction, actual_outcome) per agent per symbol
  - `get_weight(agent_name, symbol) -> float` returns EWMA accuracy in [0.05, 1.0]
  - Weights written to `agent:weights:{symbol}` Redis hash by background task

### Files to modify:

- **`services/hot_path/src/agent_modifier.py`** — Read weights from `agent:weights:{symbol}` (one extra key in existing pipeline). Replace `0.20` and `0.15` with dynamic values. Make modifier extensible: accept list of `(key_pattern, agent_name, max_adj)` tuples.
- **`services/analyst/src/`** — Repurpose the currently-unused analyst service as the weight computation engine. Every 5 min: compare historical agent predictions vs actual price moves, write updated weights to Redis.
- **`services/execution/src/`** — After order execution, record contributing agent scores to `agent:outcomes:{symbol}` stream.
- **`services/pnl/src/`** — On position close, tag outcome (profit/loss) against contributing agents.

### Verification:
- Simulate 100 signals with known outcomes, verify weight convergence
- Backtest with dynamic weights vs fixed weights, compare Sharpe ratios
- Verify hot-path latency unchanged (net zero: replace 2 floats with 1 Redis hash read)

---

## Phase 3: HITL Execution Gate

**Why**: Critical safety feature. No kill switch or position stop-loss exists (known defects). HITL provides an immediate safety net.

### New channels in `libs/messaging/channels.py`:
- `PUBSUB_HITL_PENDING = "pubsub:hitl_pending"`
- `HITL_RESPONSE_STREAM = "stream:hitl_response"`

### New enums/schemas:
- `HITLStatus` enum: `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`
- `HITLApprovalRequest` / `HITLApprovalResponse` schemas

### New file: `services/hot_path/src/hitl_gate.py`
- Inserts between risk_gate (stage 6, line 127) and validation fast_gate (stage 7, line 132) in `processor.py`
- Configurable triggers: trade size > X%, confidence < threshold, regime == HIGH_VOLATILITY
- If not triggered: pass-through (zero latency impact on most trades)
- If triggered: publish to HITL channel, await response with timeout (default 60s, fail-safe = reject)

### Settings in `libs/config/settings.py`:
- `HITL_ENABLED`, `HITL_SIZE_THRESHOLD_PCT`, `HITL_CONFIDENCE_THRESHOLD`, `HITL_TIMEOUT_S`

### Frontend: New approval page
- WebSocket subscription to `pubsub:hitl_pending`
- Signal details, agent scores, risk metrics display
- Approve/Reject buttons → `stream:hitl_response`

### Verification:
- Test with HITL disabled (no behavior change)
- Test approval flow end-to-end via WebSocket
- Test timeout → rejection (fail-safe)

---

## Phase 4: Local SLM Inference Service

**Why**: Eliminates API costs, reduces sentiment latency from 2-10s to ~200ms, enables offline operation. Required before Phase 5 (debate needs many inference calls).

### New service: `services/slm_inference/src/main.py`
- FastAPI service hosting quantized SLM (GGUF via `llama-cpp-python`)
- Endpoints: `POST /v1/completions` (OpenAI-compatible), `POST /v1/sentiment` (structured)
- Recommended model: Phi-3-mini-4k-instruct Q4 (~2.3GB VRAM on consumer GPU)
- Health endpoint with GPU memory + inference latency metrics

### Refactor: `services/sentiment/src/scorer.py`
- Abstract behind `LLMBackend` protocol: `async def complete(prompt) -> str`
- `CloudLLMBackend` (current Claude code) + `LocalLLMBackend` (calls slm_inference)
- Config-driven: `AION_LLM_BACKEND = "cloud" | "local"`, fallback chain

### New settings:
- `AION_SLM_MODEL_PATH`, `AION_SLM_CONTEXT_LENGTH`, `AION_LLM_BACKEND`

### Verification:
- Compare local SLM sentiment scores vs Claude Haiku on same headlines
- Measure inference latency p50/p99
- Test fallback: kill local service, verify cloud fallback works

---

## Phase 5: Adversarial Bull/Bear Debate

**Why**: The blueprint's signature feature. Depends on Phase 4 (local SLM) for cost-effective multi-round inference and Phase 2 (dynamic weights) for scoring debate outcomes.

### New service: `services/debate/src/main.py`
- Runs async every 5 min per symbol (same cadence as sentiment)
- 2-3 rounds: Bull agent argues long, Bear argues short, Judge synthesizes
- Output: `debate_score` (-1.0 to 1.0) + `debate_confidence` → Redis key `agent:debate:{symbol}`

### Prompt templates in `prompts/debate/`:
- `bull.txt`, `bear.txt`, `judge.txt` — include indicator values, regime, other agent scores as context

### Integration: `services/hot_path/src/agent_modifier.py`
- Add `agent:debate:{symbol}` to pipelined Redis read (one more key)
- Debate gets dynamic weight via Phase 2 tracker, max adjustment ±0.25

### Verification:
- Review debate transcripts for logical coherence
- Backtest with debate agent vs without, compare risk-adjusted returns
- Monitor inference time per debate round

---

## Phase 6: VectorBT Backtesting

**Why**: Current simulator processes candles sequentially. VectorBT enables 100-1000x faster parameter sweeps.

### New file: `services/backtesting/src/vectorbt_runner.py`
- Adapter: same `BacktestJob` input, same `BacktestResult` output
- Converts strategy rules to vectorized numpy signal arrays

### Modified: `services/backtesting/src/job_runner.py`
- Route by `engine` field: `"sequential"` (default) or `"vectorbt"`

### New endpoint: `POST /backtest/sweep` for parameter grid search

### Verification:
- Run same strategy through both engines, verify matching results
- Benchmark: time comparison on 1 year of 1m candles

---

## Deferred (Not in Scope)

- **Statistical Arbitrage**: Needs multi-exchange price feeds + cross-exchange execution
- **Candlestick CNN**: High ML infra cost; simpler rule-based pattern detection can be added as indicators instead
- **Knowledge Graph / 2nd Brain**: Premature — agents don't produce enough structured knowledge yet
- **LoRA Fine-Tuning**: Needs 6+ months of labeled trading data from production SLM

---

## Dependency Graph

```
Phase 1 (Indicators) ─────────────────────────┐
                                               ├──> Phase 6 (VectorBT)
Phase 2 (Dynamic Weights) ────┐                │
                               ├──> Phase 5 (Debate)
Phase 4 (Local SLM) ──────────┘

Phase 3 (HITL) ── independent, start anytime
```

Phases 1 + 3 can be developed in parallel. Phase 2 can overlap with Phase 1. Phase 4 is independent of 1-3 but must precede Phase 5.
