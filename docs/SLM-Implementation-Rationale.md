# Multi-Agent SLM Trading Engine — Design Rationale

This document provides detailed reasoning behind every feature selection, prioritization decision, and deferral in the implementation plan. It serves as the "why" companion to the plan's "what".

---

## 1. Feature Selection Rationale

### 1.1 Extended Technical Indicators (ADX, Bollinger Bands, OBV, Choppiness Index)

**What the blueprint proposes**: The blueprint describes agents that consume multi-dimensional inputs including MACD histogram, ADX for trend strength, OBV for volume confirmation, Bollinger Bands for volatility-adjusted extremes, and the Choppiness Index for regime filtering.

**What we currently have**: Only RSI (14-period), MACD (12/26/9), ATR (14-period), and EMA. The TA Agent's confluence scorer (`ta_agent/src/confluence.py`) currently scores across 4 timeframes using only RSI and MACD — just 2 signal dimensions weighted 50/50.

**Why these 4 specific indicators were chosen**:

- **ADX (Average Directional Index)**: The blueprint's momentum strategy explicitly requires ADX to "quantify the absolute strength of the trend." Without ADX, the current system cannot distinguish between a strong directional move and a weak, choppy drift — both produce the same MACD crossover signal. ADX directly addresses the platform's biggest weakness: false breakout signals in low-conviction environments. ADX > 25 confirms trend strength; ADX < 20 signals ranging conditions. This single indicator gates whether momentum signals should be trusted.

- **Bollinger Bands**: The blueprint's mean reversion strategy is entirely built on Bollinger Bands + RSI. The current platform has RSI but no volatility-adjusted price bands, meaning it cannot detect statistically extreme price deviations from the mean. Bollinger %B (the position of price within the bands, 0.0 = lower band, 1.0 = upper band) provides a normalized measure that works across assets with wildly different price scales — critical for a crypto platform where BTC trades at $60K and altcoins at $0.50. The bandwidth metric additionally signals volatility regime shifts (Bollinger squeeze → expansion).

- **OBV (On-Balance Volume)**: The blueprint requires OBV to "confirm that institutional liquidity supports the price action." Price moves without volume confirmation are unreliable — a key principle in technical analysis. The current system processes volume data (it arrives in every tick from Binance/Coinbase) but never uses it analytically. OBV is the simplest volume indicator to implement (cumulative sum: add volume on up-closes, subtract on down-closes) and provides immediate value as a divergence detector: price making new highs while OBV declining = distribution/weakening trend.

- **Choppiness Index**: The blueprint uses this for regime detection — specifically to determine if an asset is "genuinely range-bound or entering a new sustained momentum phase." The current `SimpleRegimeClassifier` in `libs/indicators/_regime.py` uses a 200-period SMA crossover and ATR percentiles, which is coarse-grained. Choppiness Index (values 0-100, where >61.8 = choppy, <38.2 = trending) provides a continuous, granular measure that the TA Agent can use to dynamically weight its momentum vs mean-reversion signal components. This directly enables the blueprint's concept of "regime-based signal suppression."

**Why not other indicators mentioned in the blueprint** (e.g., Variance Ratio, Z-Score for spreads): These are specific to the Statistical Arbitrage strategy, which is deferred. Adding them now without the accompanying pairs-trading logic would create unused code.

---

### 1.2 Dynamic Agent Weighting (Matrix-Weighted Consensus)

**What the blueprint proposes**: A dynamic weight matrix W where each agent's influence is "explicitly scaled based on its historical reliability and real-time contextual relevance." The blueprint also describes regime-based hierarchies where market conditions suppress certain agents automatically.

**What we currently have**: The `AgentModifier` in `hot_path/src/agent_modifier.py` uses fixed constants: TA agent adjusts confidence by ±0.20 and sentiment by ±0.15. These values were chosen during initial development and never validated against actual trading outcomes. The regime dampener (`regime_dampener.py`) provides partial regime-based suppression (blocks signals during CRISIS, reduces confidence 30% during HIGH_VOLATILITY) but doesn't dynamically adjust individual agent weights.

**Why this is the highest-impact change**:

The fixed weights create two problems:
1. **No learning**: If the sentiment agent has been consistently wrong for the past week (e.g., bullish headlines during a correction), it still gets full ±0.15 influence on every signal. A dynamic system would automatically downweight it.
2. **No regime adaptation**: The TA agent gets ±0.20 whether the market is trending (where TA is most reliable) or ranging (where TA crossovers generate whipsaws). The blueprint's key insight is that agent reliability is regime-dependent.

The proposed `AgentPerformanceTracker` implements an Exponentially Weighted Moving Average (EWMA) of each agent's directional accuracy over the last 100 signals. EWMA (vs simple average) gives more weight to recent performance, allowing the system to adapt within days rather than weeks. The floor of 0.05 (never fully mute an agent) prevents catastrophic situations where a temporarily poor agent is silenced and then misses a genuine signal.

**Why repurpose the analyst service**: The `analyst` service (`services/analyst/`) currently contains an unused keyword-based sentiment scorer that was superseded by the LLM-based sentiment service. Rather than creating a new service (which adds Docker container overhead, port allocation, and operational complexity), repurposing this idle service as the weight computation engine is operationally cleaner.

**Why additive weights remain (not multiplicative)**: The existing comment in `agent_modifier.py:30` explains the design: "Additive adjustment with clamp avoids multiplicative compounding that can drive confidence toward zero when multiple agents disagree." This principle is sound and should be preserved. The change is making the additive bounds dynamic, not changing the aggregation formula.

---

### 1.3 HITL (Human-in-the-Loop) Execution Gate

**What the blueprint proposes**: A structured approval workflow where the system generates a "proposed action" payload and routes it to a human reviewer before execution. The human acts as "the final gatekeeper, reviewing the 2nd brain's auditable logs."

**What we currently have**: No trade approval workflow. The hot-path pipeline processes ticks and emits `OrderApprovedEvent` directly to the execution service without human intervention. The only safety mechanisms are automated: circuit breaker (daily loss limit), validation fast-gate (35ms check), and risk gate (position sizing). The CLAUDE.md explicitly lists "Kill switch / emergency shutdown is NOT IMPLEMENTED" and "Position-level stop-loss enforcement is NOT IMPLEMENTED" as known defects.

**Why this is a P2 priority (not P1)**:

While safety is critical, the HITL gate is P2 rather than P1 because:
1. The platform currently operates in `PAPER_TRADING_MODE` with a mandatory 30-day dry run before live capital — there's a built-in safety buffer.
2. The existing circuit breaker provides coarse protection against catastrophic loss.
3. Phases 1 and 2 (indicators + dynamic weights) improve signal quality at the source, which reduces the number of bad signals that would need to be caught by HITL.

**Why fail-safe (reject on timeout) instead of fail-open**: The blueprint explicitly states this design choice and the reasoning is straightforward: a missed trade opportunity costs the spread; an unauthorized bad trade can cost a percentage of the portfolio. The asymmetric risk profile demands conservative defaults.

**Why insert between risk_gate and validation_fast_gate**: The HITL gate must come after risk_gate (stage 6) because the risk gate computes the `suggested_quantity` — the human reviewer needs to see the actual proposed position size, not just the raw signal. It must come before validation_fast_gate (stage 7) because validation is a technical check that should still run on HITL-approved trades to catch any remaining issues.

**Why configurable triggers instead of gating all trades**: Gating every trade on human approval defeats the purpose of an automated system. The blueprint recommends "selective triggering" — only escalating trades that exceed risk thresholds, occur during unusual market conditions, or involve low-confidence signals. This preserves the speed advantage of automation for routine trades while adding oversight for high-stakes decisions.

---

### 1.4 Local SLM Inference Service

**What the blueprint proposes**: On-premises deployment of Small Language Models (Phi-3, Mistral 7B, Llama 3) for "fully localized" inference that eliminates API costs, reduces latency, and maintains data sovereignty.

**What we currently have**: The sentiment agent calls `api.anthropic.com` (Claude Haiku) via HTTP with a 10-second timeout, 2-second minimum interval between calls, and a 15-minute Redis cache. This means sentiment scores update at most every 5 minutes per symbol and each API call costs tokens.

**Why Phi-3-mini-4k-instruct is the recommended model**:

- **Parameter count (3.8B)**: Small enough to run on a consumer GPU (8GB VRAM) with Q4 quantization (~2.3GB VRAM), leaving headroom for other GPU tasks. The blueprint explicitly recommends Phi-3-Mini for "real-time risk assessment" due to its "ultra-fast cold starts."
- **Mathematical reasoning**: Phi-3 was trained on "curated, textbook-quality synthetic datasets" and excels at the kind of structured analytical tasks we need (parsing JSON, evaluating numerical indicators, classifying sentiment). Benchmarks show Phi-3-Mini outperforms many 7B models on reasoning tasks despite being half the size.
- **MIT license**: Zero commercial restrictions. Mistral 7B (Apache 2.0) is also unrestricted, but Llama 3's custom license has some distribution constraints.
- **Inference speed**: At 3.8B parameters with Q4 quantization, expect 150-300 tokens/second on a modern GPU vs the ~50-100 tokens/second typical of 7B+ models. For sentiment scoring (requiring ~50-100 output tokens), this translates to sub-second inference.

**Why an abstraction layer (LLMBackend protocol) instead of just swapping the API**:

The sentiment scorer currently has Claude-specific logic (API key handling, retry logic, JSON extraction with regex fallback). Rather than replacing this wholesale, abstracting behind a `LLMBackend` protocol preserves the cloud path as a fallback. This is operationally critical: if the local GPU server goes down (hardware failure, OOM), sentiment scoring degrades to cloud API rather than going offline entirely. The config-driven selection (`AION_LLM_BACKEND`) also enables A/B testing between local and cloud models to validate that the local SLM achieves comparable sentiment accuracy.

**Why this must precede Phase 5 (Debate)**: The adversarial debate framework requires 6-9 SLM invocations per debate round (bull prompt + bear prompt + judge prompt, for 2-3 rounds). At cloud API pricing, running this every 5 minutes for each tracked symbol would be expensive. Local inference makes the debate framework economically viable for continuous operation.

---

### 1.5 Adversarial Bull/Bear Debate

**What the blueprint proposes**: An adversarial debate framework where a Bull Agent and Bear Agent "aggressively stress-test opposing hypotheses" through multi-round dialogue, with a Judge Agent synthesizing the debate into a final recommendation.

**What we currently have**: No debate mechanism. The three existing agents (TA, Sentiment, Regime HMM) operate independently and their outputs are combined through simple additive modifiers. There is no mechanism for agents to challenge each other's reasoning or for the system to explicitly consider counter-arguments before trading.

**Why this is a P3 priority**:

The debate framework is architecturally the most novel feature from the blueprint, but it has significant dependencies:
1. **Requires local SLM (Phase 4)**: 6-9 inference calls per debate at cloud API prices is unsustainable.
2. **Requires dynamic weights (Phase 2)**: The debate agent's output needs to be weighted against other agents based on performance — without dynamic weighting, we'd need to guess the debate's influence, which defeats the purpose.
3. **Requires enriched indicators (Phase 1)**: The debate prompts need ADX, Bollinger, and other indicators as context to make informed arguments. Without them, the bull/bear agents would be reasoning from the same limited RSI/MACD data, producing shallow debates.

**Why 2-3 rounds (not more)**: Each round adds ~1-2 seconds of inference latency. The debate runs asynchronously (every 5 min, same as sentiment), so latency isn't blocking the hot-path, but we need results within a reasonable window. 2-3 rounds provide enough depth for meaningful argumentation without diminishing returns. The blueprint itself describes "multi-round, iterative dialogue" without specifying a count; empirical testing during development will determine the optimal round count.

**Why the debate score feeds into the existing AgentModifier**: Rather than creating a separate aggregation mechanism, the debate output follows the same pattern as TA and sentiment: write a score to Redis, let the AgentModifier read it in the pipelined round-trip. This keeps the hot-path architecture unchanged (just one more key in the pipeline) and allows the Phase 2 dynamic weighting system to naturally track the debate agent's accuracy alongside other agents. The proposed ±0.25 max adjustment (higher than TA's ±0.20 or sentiment's ±0.15) reflects the blueprint's premise that the debate synthesizes multiple viewpoints and should carry more weight — but this cap will be validated through backtesting.

---

### 1.6 VectorBT Backtesting

**What the blueprint proposes**: "Highly performant, array-based libraries such as VectorBT" that "performs vectorized computations across the entire historical dataset simultaneously," enabling "massive parameter grid searches in seconds rather than hours."

**What we currently have**: A custom `TradingSimulator` (`backtesting/src/simulator.py`) that replays candles sequentially through compiled strategy rules. It works but is slow for parameter optimization — testing 1000 parameter combinations across 1 year of 1-minute data would take hours.

**Why this is P3 and not higher**:

VectorBT is a developer productivity tool, not a production-path component. It doesn't change how the live system trades; it changes how quickly developers can test strategy variations. The current sequential backtester is functionally correct — it just needs patience. Phases 1-5 all improve the live trading engine directly, making them higher priority.

**Why the adapter pattern (same BacktestJob/BacktestResult interface)**: The frontend backtesting page (`frontend/app/backtest/page.tsx`) and the job queue system (`backtesting/src/job_runner.py`) already work with the current simulator's input/output format. By implementing VectorBT behind the same interface, the entire existing UI and job infrastructure works unchanged — the user just selects an engine type. This avoids rewriting the frontend or API layer.

**Why not replace the sequential simulator entirely**: VectorBT's vectorized approach requires translating arbitrary strategy rules into numpy array operations, which doesn't perfectly map to every rule type the `CompiledRuleSet` supports. The sequential simulator handles edge cases (complex AND/OR logic, multi-indicator conditions) more naturally. Keeping both engines ensures no regression in strategy coverage.

---

## 2. Phasing Rationale

### Why This Specific Order

The phases are ordered by a combination of three factors:

1. **Dependency chain**: Some phases technically require others (Phase 5 needs Phase 4 for inference, Phase 5 needs Phase 2 for weighting).
2. **Risk gradient**: Earlier phases are lower risk (library additions, config changes) while later phases involve more complex infrastructure (GPU servers, multi-round inference).
3. **Value accumulation**: Each phase makes subsequent phases more valuable (better indicators → better debate arguments → better consensus).

### Phase 1 First: Foundation Without Risk

Adding indicators is pure library code with zero production risk. Every new indicator follows the exact same `update() -> Optional[float]` pattern established by the existing RSI, MACD, and ATR calculators. They can be unit-tested in complete isolation (pass known inputs, verify outputs against reference implementations like TA-Lib). Once verified, they plug into the existing `IndicatorSet` and `StrategyEvaluator` through slot additions and dict key registrations — all backward-compatible changes.

This phase also produces immediate visible value: users can create strategy rules referencing new indicators (e.g., "buy when RSI < 30 AND bb.pct_b < 0.1 AND choppiness > 61.8") through the existing JSON rule editor in the frontend.

### Phase 2 Early: Multiplier Effect

Dynamic weighting is positioned early because it creates a multiplier effect on every subsequent phase. Once the `AgentPerformanceTracker` is in place, every new agent added in later phases (debate, future agents) automatically gets performance-tracked weighting — no additional work per agent. If this were deferred to after Phase 5, we'd need to manually guess the debate agent's weight and hope it's right.

### Phase 3 Independent: Safety Shouldn't Wait

HITL is marked as independent because it has no technical dependencies on other phases. It can be developed in parallel with Phase 1 or Phase 2. The reason it's not Phase 1 is pragmatic: the platform currently runs in paper-trading mode only, so the urgency of a safety gate is lower than improving signal quality. But for any path toward live capital deployment, HITL must be in place.

### Phases 4→5 Sequential: Infrastructure Then Application

Phase 4 (local SLM) is pure infrastructure — setting up model serving, abstracting the LLM backend, testing inference quality. Phase 5 (debate) is an application built on that infrastructure. Attempting Phase 5 without Phase 4 would mean running debates through the cloud API, which is both expensive (6-9 API calls every 5 minutes per symbol) and slow (compounding API latency across multiple sequential calls).

### Phase 6 Last: Developer Tooling

VectorBT improves the developer's ability to iterate on strategies but doesn't change production behavior. It's last because all other phases directly improve the live trading engine. However, once Phase 1's indicators are in place, VectorBT becomes significantly more valuable — you can sweep across ADX thresholds, Bollinger widths, and Choppiness cutoffs to find optimal parameter combinations, which would be painfully slow with the sequential simulator.

---

## 3. Deferred Features — Detailed Analysis

### 3.1 Statistical Arbitrage (Pairs Trading)

**What the blueprint describes**: Tracking the historical price relationship between correlated assets, running Augmented Dickey-Fuller (ADF) tests for cointegration, monitoring Z-scores of the spread, and simultaneously shorting the overperformer while going long on the underperformer.

**Why deferred — not just deprioritized**:

Statistical arbitrage requires fundamental architectural changes that go beyond adding a new agent:

1. **Multi-asset signal generation**: The current hot-path processes ticks per-profile, evaluating one symbol at a time. StatArb requires correlating two symbols simultaneously — their spreads, their cointegration scores, their relative Z-scores. This means the signal generation must consider pairs of assets, not individual assets, requiring a new processing paradigm.

2. **Cross-exchange execution**: True StatArb often exploits pricing differences between exchanges. The current ingestion service processes Binance and Coinbase feeds independently. Correlating prices across exchanges requires timestamp synchronization, latency normalization, and cross-exchange order routing — none of which exist.

3. **Dual-leg order management**: A StatArb trade consists of two simultaneous orders (long one asset, short the other). The execution service currently handles single-sided orders. Implementing atomic dual-leg execution with proper handling of partial fills (what if one leg fills and the other doesn't?) is a significant engineering challenge.

4. **Short selling on crypto exchanges**: Many crypto exchanges have restrictions on short selling or require margin accounts. The current exchange adapters (`libs/exchange/`) don't implement margin trading or short selling APIs.

**When to revisit**: After the platform has proven profitability with directional strategies (Phases 1-5), and after the execution service is extended to support margin accounts and multi-leg orders. This is likely a 6+ month horizon item.

### 3.2 Candlestick Pattern Recognition (CNN)

**What the blueprint describes**: "Convolutional Neural Networks which treat candlestick charts as visual images, achieving up to 99.3% accuracy in predicting subsequent directional movements." Agents that detect complex multi-candle formations like Bullish Engulfing, Morning Star, and Bearish Harami.

**Why deferred**:

1. **The 99.3% accuracy claim is misleading**: This figure likely comes from controlled academic studies with cherry-picked datasets and specific pattern classes. In live markets with noisy data, class imbalance (most candles are not meaningful patterns), and transaction costs, the real edge from candlestick patterns is marginal. Academic literature consistently shows that candlestick patterns alone have weak predictive power — their value comes from confluence with other signals (volume, trend context, support/resistance levels).

2. **CNN infrastructure is heavy**: Training a CNN requires labeled training data (thousands of annotated chart images), a training pipeline (data augmentation, hyperparameter tuning, validation), and inference infrastructure (model serving, GPU allocation). This is a full ML project in itself.

3. **Rule-based patterns are a simpler alternative**: The most common candlestick patterns (engulfing, hammer, doji, morning/evening star) can be detected with straightforward OHLC comparisons — no neural network required. For example, a Bullish Engulfing is simply: `current.close > current.open AND prev.close < prev.open AND current.close > prev.open AND current.open < prev.close`. These can be added as additional indicators in Phase 1's framework at minimal cost.

4. **The current data pipeline supports it**: The ingestion service already provides OHLCV data. Adding rule-based pattern detection to the indicator library is a natural extension of Phase 1. A CNN can be explored later if rule-based patterns prove insufficient.

**Recommended alternative**: Add 5-10 common candlestick pattern detectors as rule-based indicators in `libs/indicators/` following the same `update(open, high, low, close) -> Optional[PatternResult]` pattern. This delivers 80% of the blueprint's candlestick value at 5% of the implementation cost.

### 3.3 Knowledge Graph / 2nd Brain

**What the blueprint describes**: A "deeply structured memory layer" combining vector databases for RAG and Knowledge Graphs encoding "financial entities, market relationships, and ongoing performance metrics." Every agent's decision rationale is "continuously documented and persisted," enabling "self-reflection" and learning from historical successes/failures.

**Why deferred**:

1. **Premature optimization of context**: The current agents are relatively simple. The TA agent scores indicators. The sentiment agent classifies headlines. The regime HMM fits a statistical model. None of these agents produce rich, structured knowledge that would benefit from graph relationships. A knowledge graph is valuable when you have entities (companies, sectors, economic indicators) with complex relationships (supply chains, competitive dynamics, regulatory dependencies) — but the current crypto-focused platform trades BTC/USDT and ETH/USDT without deep fundamental entity analysis.

2. **RAG adds latency for uncertain value**: Retrieval-Augmented Generation requires vector similarity search on every query, adding 10-50ms per retrieval. For the sentiment agent running every 5 minutes, this is acceptable. But the blueprint describes RAG as part of the debate framework, where agents query historical analysis during argumentation. The value of recalling what the system thought about BTC 3 months ago during a current debate round is questionable — markets are non-stationary, and historical reasoning may be actively misleading.

3. **Redis already provides sufficient state**: The current architecture uses Redis keys with TTLs for agent scores, which is exactly the right approach for ephemeral, time-decaying signals. The `validation_events` and `audit_log` tables in TimescaleDB already provide persistent audit trails. Adding a graph database (Neo4j, etc.) introduces operational complexity (another service to deploy, backup, monitor) for marginal benefit at this stage.

4. **The dynamic weighting system (Phase 2) captures the key value**: The blueprint's self-reflection concept — "learning from historical successes and failures" — is primarily achieved by tracking agent performance over time and adjusting weights. The `AgentPerformanceTracker` proposed in Phase 2 captures this value without the complexity of a full knowledge graph.

**When to revisit**: When the platform expands beyond crypto to equities (where fundamental entity relationships matter), or when the number of agents exceeds 5-6 and their interactions become complex enough to benefit from graph-based reasoning about inter-agent relationships.

### 3.4 LoRA Fine-Tuning Pipeline

**What the blueprint describes**: "Low-Rank Adaptation (LoRA), a parameter-efficient fine-tuning (PEFT) methodology" that freezes pre-trained weights and injects "small, trainable rank decomposition matrices." Fine-tuning on "historical news headlines mapped to their corresponding intraday stock price deviations."

**Why deferred**:

1. **Data dependency**: Effective fine-tuning requires thousands of labeled examples mapping inputs (headlines, indicator states) to correct outputs (sentiment scores, directional predictions). The platform doesn't currently generate this labeled data at scale. Phase 2's outcome tracking (recording agent predictions against actual results) will begin accumulating this data, but meaningful fine-tuning requires 6+ months of production data.

2. **Baseline first, then optimize**: Fine-tuning is an optimization step. You first need a working system with measurable performance (Phases 1-5), then identify specific areas where the base model underperforms, and then fine-tune to address those specific weaknesses. Fine-tuning without a performance baseline is optimization without a target.

3. **Infrastructure requirements**: LoRA fine-tuning, while more efficient than full fine-tuning, still requires a GPU training pipeline (data loading, training loop, validation split, checkpoint management, model evaluation). This is distinct from the inference pipeline in Phase 4. Setting up both simultaneously is scope creep for a solo developer.

4. **Risk of overfitting**: The blueprint warns about this: "overfitting occurs when a strategy is excessively optimized to capture the noise of a specific historical dataset." Fine-tuning an SLM on crypto sentiment data is particularly risky because crypto market regimes shift rapidly, and a model fine-tuned on bull-market headlines may perform poorly in a bear market. Proper fine-tuning requires walk-forward validation and regular retraining — a continuous process, not a one-time setup.

**When to revisit**: After Phase 4's local SLM has been running in production for 6+ months, accumulating labeled prediction-outcome pairs. At that point, identify the specific prediction categories where the base model underperforms (e.g., misclassifying regulatory news as bullish), create a focused fine-tuning dataset for those categories, and run LoRA training with proper train/validation/test splits.

---

## 4. Architectural Principles Guiding All Decisions

### 4.1 Hot-Path Latency Is Sacred

The 50ms tick-processing budget is the platform's core performance contract. Every feature decision was evaluated against this constraint:
- Phase 1 indicators: O(1) incremental computation — negligible impact
- Phase 2 dynamic weights: Replaces 2 hardcoded floats with 1 Redis hash read — net zero
- Phase 3 HITL: Pass-through for non-triggered trades — zero impact on normal flow
- Phases 4-5: Async services writing to Redis — hot-path just reads one more key
- Phase 6: Developer tooling — doesn't touch hot-path

### 4.2 Agents Write to Redis, Hot-Path Reads

The existing pattern (agents compute asynchronously, write scores to Redis keys with TTLs, hot-path reads in a pipelined batch) is maintained for every new agent. This decouples agent compute time from signal latency and provides natural graceful degradation (expired keys = zero adjustment, not a crash).

### 4.3 Backward Compatibility

Every modification preserves existing behavior by default. New indicators default to `None` in `IndicatorSet`. Dynamic weights fall back to fixed values if the weight Redis key is missing. HITL is opt-in via config. The SLM backend falls back to cloud. No existing strategy rule breaks.

### 4.4 Decimal Discipline

All new financial computations use `Decimal` types per the project convention. The known `float()` conversions in the codebase are tracked defects — the plan does not introduce new ones.
