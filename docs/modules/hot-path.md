# Hot-Path Processor

## Purpose and Responsibility

The Hot-Path Processor is the latency-critical core of the Praxis Trading Platform. It consumes normalised market data ticks from a Redis stream, evaluates trading strategies against every active profile in real time, and emits `OrderApprovedEvent` messages for signals that survive a multi-stage filtering pipeline. The entire tick-to-order path is designed to complete in single-digit milliseconds per profile.

## Public Interface

### `HotPathProcessor`

```python
class HotPathProcessor:
    def __init__(
        self,
        state_cache: ProfileStateCache,
        consumer: StreamConsumer,
        publisher: StreamPublisher,
        pubsub: PubSubBroadcaster,
        validation_client: ValidationClient,
        tick_channel: str,
        orders_channel: str,
        proximity_pubsub_channel: str,
        redis_client=None,
    )
    async def run(self) -> None
```

### `ProfileState`

```python
class ProfileState:
    profile_id: str
    compiled_rules: CompiledRuleSet
    risk_limits: RiskLimits
    blacklist: frozenset
    indicators: IndicatorSet
    regime: Optional[Regime]
    daily_realised_pnl_pct: float
    current_drawdown_pct: float
    current_allocation_pct: float
    is_active: bool
```

### `ProfileStateCache`

```python
class ProfileStateCache:
    def add(self, state: ProfileState) -> None
    def get(self, profile_id: str) -> Optional[ProfileState]
    def itervalues(self) -> ValuesView[ProfileState]
```

### `StrategyEvaluator`

```python
class StrategyEvaluator:
    @staticmethod
    def evaluate(state: ProfileState, tick: NormalisedTick)
        -> Optional[tuple[SignalResult, EvaluatedIndicators]]
```

### `ValidationClient`

```python
class ValidationClient:
    def __init__(self, publisher, consumer, req_channel, resp_channel, timeout_ms=50)
    async def fast_gate(self, request: ValidationRequestEvent) -> Optional[ValidationResponseEvent]
```

### Data Classes

```python
@dataclass(frozen=True, slots=True)
class SignalResult:
    direction: SignalDirection
    confidence: float
    rule_matched: bool

@dataclass(frozen=True, slots=True)
class EvaluatedIndicators:
    rsi: float
    macd_line: float
    signal_line: float
    histogram: float
    atr: float
    adx: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_pct_b: Optional[float] = None
    bb_bandwidth: Optional[float] = None
    obv: Optional[float] = None
    choppiness: Optional[float] = None
```

## Internal Architecture

The processor runs a continuous consume loop that reads up to 100 ticks per heartbeat (50ms block) from the `stream:market_data` Redis stream. For each tick, it iterates over every active profile in the in-memory `ProfileStateCache` and applies an 11-stage pipeline:

1. **Strategy Evaluation** -- Updates all 8 indicators (RSI, MACD, ATR, ADX, Bollinger, OBV, Choppiness) incrementally from the tick price, then evaluates the profile's compiled rule set. New indicators are added to `eval_dict` when primed; core indicators (RSI, MACD, ATR) must be primed before any signal can fire. Returns a `SignalResult` with direction and confidence, or `None` if no rule fires.

2. **Threshold Proximity Check** -- If no signal fires but RSI is within a configurable band of its trigger threshold (e.g., RSI between 30 and 30 * 1.05), a `ThresholdProximityEvent` is broadcast via PubSub to allow downstream services to pre-fetch data.

3. **Abstention Check** -- `AbstentionChecker.check()` filters out signals that should not proceed (details in a separate module).

4. **Regime Dampener** -- Async check that adjusts signal confidence based on the current market regime (trending, range-bound, crisis). Returns a `confidence_multiplier` applied to the signal. Signals that should not proceed are dropped.

5. **Agent Modifier** -- Blends TA scores, sentiment scores, and debate scores into the signal confidence using **dynamic weights** from `agent:weights:{symbol}` Redis hash. Weights are computed by the Analyst service (Phase 2 EWMA tracking). Falls back to default weights (TA=0.20, sentiment=0.15, debate=0.25) when dynamic weights are unavailable. All agent reads are pipelined into a single Redis round trip.

6. **Circuit Breaker** -- `CircuitBreaker.check()` blocks trading for profiles that have hit daily loss limits.

7. **Blacklist Check** -- `BlacklistChecker.check()` drops signals for symbols in the profile's blacklist.

8. **Risk Gate** -- `RiskGate.check()` evaluates position sizing and risk limits. Returns a `RiskGateResult` with a `suggested_quantity` for dynamic sizing.

9. **HITL Gate** -- (Phase 3) `HITLGate.check()` evaluates whether human approval is required based on configurable triggers: low confidence, HIGH_VOLATILITY regime, or large trade size. If not triggered, passes through with zero latency. If triggered, publishes an `HITLApprovalRequest` to `pubsub:hitl_pending`, waits for a response via Redis BLPOP with configurable timeout (default 60s). Fail-safe: timeout or error = reject. Disabled by default (`PRAXIS_HITL_ENABLED=false`).

10. **Validation Fast Gate** -- Sends a `ValidationRequestEvent` to the Validation Service via a synchronous Redis BLPOP RPC pattern. If the response verdict is `RED`, the signal is blocked.

11. **Order Emission** -- Publishes an `OrderApprovedEvent` to `stream:orders` with the dynamically sized quantity.

### Startup Sequence

The FastAPI lifespan handler orchestrates startup:

1. Initialise Redis, stream consumer/publisher, and PubSub connections.
2. Create `ValidationClient` with configurable timeout (`FAST_GATE_TIMEOUT_MS`).
3. Wait for the Strategy Agent to complete hydration of all profile states (polls `hydration:{profile_id}:status` keys in Redis).
4. Start PnL sync background task to keep `daily_realised_pnl_pct` current.
5. Start the processor's main consume loop.

### Consumer Group

The processor uses Redis consumer group `hotpath_engine` with consumer ID `processor_1`. Message acknowledgement is batched at the end of each consume cycle.

## Dependencies

### Upstream (consumes from)

| Source | Channel | Event Type |
|--------|---------|------------|
| Market Data Ingest | `stream:market_data` | `MarketTickEvent` |
| Strategy Agent | Redis keys `hydration:{profile_id}:status` | Hydration signal |
| PnL Service | PubSub `pubsub:pnl_updates` | PnL sync for daily PnL/drawdown |

### Downstream (publishes to)

| Target | Channel | Event Type |
|--------|---------|------------|
| Execution Service | `stream:orders` | `OrderApprovedEvent` |
| Validation Service | `stream:validation` | `ValidationRequestEvent` |
| Dashboard / Pre-fetch | PubSub `pubsub:threshold_proximity` | `ThresholdProximityEvent` |
| HITL Approval UI | PubSub `pubsub:hitl_pending` | `HITLApprovalRequest` |

### Library Dependencies

- `libs.messaging` -- Stream consumer/publisher, PubSub
- `libs.indicators` -- `IndicatorSet` (RSI, MACD, ATR, ADX, Bollinger, OBV, Choppiness)
- `libs.core.agent_registry` -- `AgentPerformanceTracker` (dynamic weight reads)
- `libs.core` -- Enums, models, schemas, constants
- `libs.config` -- `settings.REDIS_URL`, `settings.FAST_GATE_TIMEOUT_MS`
- `libs.observability` -- Structured logging, `timer()` context manager, `MetricsCollector`
- `services.strategy.src.compiler` -- `CompiledRuleSet` for O(1) rule evaluation

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Validation timeout (BLPOP expires) | Returns `None`; signal proceeds (fail-open). A warning is logged. |
| Decode error on validation response | Logs error, returns `None` (fail-open). |
| Invalid/missing tick event | Message is acknowledged and skipped silently. |
| Indicators still priming (insufficient data) | `StrategyEvaluator.evaluate()` returns `None`; tick is skipped for that profile. |
| Redis connection failure | Unhandled -- the consume loop will raise and crash the task. FastAPI lifespan will log shutdown. |

## Configuration

| Setting | Source | Default | Description |
|---------|--------|---------|-------------|
| `REDIS_URL` | `libs.config.settings` | -- | Redis connection string |
| `FAST_GATE_TIMEOUT_MS` | `libs.config.settings` | `50` | Max wait for validation RPC response |
| `THRESHOLD_PROXIMITY_BAND_PCT` | `libs.core.constants` | -- | RSI proximity band for pre-fetch events |
| `HITL_ENABLED` | `libs.config.settings` | `false` | Enable HITL execution gate |
| `HITL_SIZE_THRESHOLD_PCT` | `libs.config.settings` | `5.0` | Trade size % triggering HITL |
| `HITL_CONFIDENCE_THRESHOLD` | `libs.config.settings` | `0.5` | Confidence below this triggers HITL |
| `HITL_TIMEOUT_S` | `libs.config.settings` | `60` | HITL response timeout (fail-safe: reject) |
| Consumer batch size | Hardcoded | `100` | Max ticks consumed per heartbeat |
| Consumer block time | Hardcoded | `50ms` | XREADGROUP block duration |

## Known Issues and Technical Debt

1. **Fail-open on validation timeout** -- When the validation service is slow or unreachable, the hot path defaults to allowing the trade. This is a deliberate latency trade-off but represents a risk if validation is down for an extended period.

2. **Single consumer instance** -- The consumer ID is hardcoded to `processor_1`. Horizontal scaling would require parameterising the consumer name and partitioning profiles across instances.

3. **No dead-letter handling** -- Invalid tick events are acknowledged and discarded with no DLQ routing. Malformed data is silently lost.

4. **Hardcoded batch and block parameters** -- The consume batch size (100) and block time (50ms) are not configurable. Tuning these for different load profiles requires a code change.

5. **Indicator priming gap** -- After startup, each profile silently drops ticks until its indicators have received enough data points to produce values (14+ for RSI, 26+ for MACD slow EMA). No telemetry reports when priming completes.

6. **Validation client accesses internal Redis** -- `ValidationClient` reaches into `consumer._redis` to access the underlying Redis client for BLPOP, breaking the `StreamConsumer` abstraction.

7. **PnL sync coupling** -- The `PnlSync` background task is started within the hot-path lifespan rather than running as a separate sidecar, mixing concerns in the process lifecycle.
