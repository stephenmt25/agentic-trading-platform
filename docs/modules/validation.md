# Validation Service

## Purpose and Responsibility

The Validation Service provides a two-tier safety layer that sits between the Hot-Path Processor and order execution. The synchronous **Fast Gate** performs sub-35ms checks on every trade signal before it can proceed, while the **Async Audit** runs deeper, non-blocking analysis on the same signals after the fact. A **Learning Loop** scans audit results hourly and triggers automated backtests to improve future decision quality.

## Public Interface

### `FastGateHandler`

```python
class FastGateHandler:
    def __init__(self, check1: StrategyRecheck, check6: RiskLevelRecheck)
    async def handle(self, req: ValidationRequestEvent) -> ValidationResponseEvent
```

### `AsyncAuditHandler`

```python
class AsyncAuditHandler:
    def __init__(
        self,
        consumer: StreamConsumer,
        validation_repo: ValidationRepository,
        check2: HallucinationCheck,
        check3: BiasCheck,
        check4: DriftCheck,
        check5: EscalationCheck,
        channel: str,
    )
    async def run(self) -> None
```

### `StrategyRecheck` (Check 1)

```python
class StrategyRecheck:
    def __init__(self, market_repo, redis_client)
    async def check(self, request: ValidationRequestEvent) -> CheckResult

@dataclass
class CheckResult:
    passed: bool
    reason: Optional[str] = None
```

### `RiskLevelRecheck` (Check 6)

```python
class RiskLevelRecheck:
    def __init__(self, profile_repo)
    async def check(self, request: ValidationRequestEvent) -> CheckResult
```

### `LearningLoop`

```python
class LearningLoop:
    def __init__(self, validation_repo: ValidationRepository, publisher: StreamPublisher)
    async def run_hourly_scan(self, interval_seconds: int = 3600) -> None
```

## Internal Architecture

### Fast Gate (Synchronous Path)

The Fast Gate runs as a high-priority consumer loop on `stream:validation` (group `fastgate_group`). It consumes up to 100 events per iteration with a 5ms block time and runs two checks in parallel using `asyncio.gather`:

**Check 1 -- Strategy Recheck**: Compares the hot RSI value computed by the Hot-Path Processor against an independently computed RSI from a wider 5-minute candle window (20 candles from TimescaleDB). If the two values diverge by more than 25%, the check fails. Results are cached in Redis for 1 second (`fast_gate:chk1:{profile_id}:{symbol}`) to provide burst protection. Falls open -- if TimescaleDB is unreachable, the hot value is trusted.

**Check 6 -- Risk Level Recheck**: Loads the trading profile's risk limits from the database and validates:
- (a) Order value does not exceed `max_allocation_pct` of the profile budget
- (b) Stop-loss percentage does not exceed the profile's `stop_loss_pct` limit
- (c) Current drawdown has not breached `max_drawdown_pct`
- (d) Absolute quantity does not exceed a hard cap of 10,000 units

If the profile cannot be loaded, the check fails closed as a safety measure.

The response is delivered back to the Hot-Path via two mechanisms:
1. Published to `stream:validation_response` (stream-based)
2. `LPUSH` to a per-request Redis key `validation:resp:{event_id}` with a 5-second TTL (BLPOP RPC pattern)

A warning is logged if the combined gate latency exceeds 35ms.

### Async Audit (Background Path)

The async auditor runs as a separate consumer on `stream:validation` (group `async_val_group`) and executes four additional checks sequentially on each validation request:

- **Check 2 -- Hallucination**: Detects signals based on fabricated or stale data.
- **Check 3 -- Bias**: Identifies systematic directional bias in trading decisions.
- **Check 4 -- Drift**: Compares live performance against backtest expectations. Results tagged as `RED` or `AMBER`.
- **Check 5 -- Escalation**: Aggregates failures from checks 2-4 and escalates via PubSub alerts when patterns emerge.

All results are persisted to the `validation_events` table via `ValidationRepository`.

### Learning Loop

Runs hourly, scanning recent `RED` and `AMBER` events across all check types. Maps failure patterns to automated backtest jobs:

| Failure Type | Backtest Job |
|-------------|-------------|
| Drift RED | `what_if_halted` |
| Hallucination | `zero_sentiment_backtest` |
| Bias | `neutral_bias_backtest` |

Jobs are published to the `auto_backtest_queue` stream.

### Background Tasks (Lifespan)

Three concurrent tasks are started during the FastAPI lifespan:
1. `fast_gate_loop` -- High-priority validation consumer
2. `async_auditor.run()` -- Background audit consumer
3. `learning_loop.run_hourly_scan()` -- Hourly scan cron

## Dependencies

### Upstream (consumes from)

| Source | Channel | Event Type |
|--------|---------|------------|
| Hot-Path Processor | `stream:validation` | `ValidationRequestEvent` |

### Downstream (publishes to)

| Target | Channel | Event Type |
|--------|---------|------------|
| Hot-Path Processor | `stream:validation_response` + per-request BLPOP key | `ValidationResponseEvent` |
| Backtest Service | `auto_backtest_queue` | Backtest job payload |
| Alerting | PubSub (via Check 5 Escalation) | Alert events |

### Infrastructure Dependencies

- **TimescaleDB** -- Market data candles, trading profiles, validation events, PnL snapshots, backtest results
- **Redis** -- Stream consumption, fast gate result caching, BLPOP RPC response delivery

### Library Dependencies

- `libs.storage` -- `MarketDataRepository`, `ProfileRepository`, `ValidationRepository`, `PnlRepository`, `BacktestRepository`
- `libs.messaging` -- `StreamConsumer`, `StreamPublisher`, `PubSubBroadcaster`
- `libs.messaging._serialisation` -- `encode_event` for LPUSH response encoding
- `libs.config` -- `settings.REDIS_URL`, `settings.DATABASE_URL`

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| TimescaleDB unreachable during Check 1 | Falls back to hot RSI value (fail-open) |
| Profile not found during Check 6 | Returns `CheckResult(passed=False)` (fail-closed) |
| Risk limits JSON parse failure | Defaults to empty dict, effectively skipping allocation/stop-loss checks |
| Fast Gate exceeds 35ms | Warning logged, response still delivered |
| Learning Loop scan error | Exception caught and swallowed silently (no logging) |
| Async audit check failure | Escalated to Check 5; audit event still written |

## Configuration

| Setting | Source | Default | Description |
|---------|--------|---------|-------------|
| `DATABASE_URL` | `libs.config.settings` | -- | TimescaleDB connection string |
| `REDIS_URL` | `libs.config.settings` | -- | Redis connection string |
| Fast Gate batch size | Hardcoded | `100` | Max events per fast gate loop iteration |
| Fast Gate block time | Hardcoded | `5ms` | XREADGROUP block duration (tuned for low latency) |
| Async audit batch size | Hardcoded | `50` | Max events per audit loop iteration |
| Check 1 cache TTL | Hardcoded | `1s` | Redis cache for burst protection |
| Check 1 divergence threshold | Hardcoded | `0.25` (25%) | Max allowed RSI divergence |
| Check 6 hard quantity cap | Hardcoded | `10,000` | Absolute quantity safety guard |
| BLPOP response TTL | Hardcoded | `5s` | Per-request Redis key expiry |
| Learning Loop interval | Default parameter | `3600s` (1h) | Scan frequency |

## Known Issues and Technical Debt

1. **Shared stream, dual consumer groups** -- Both the Fast Gate and Async Audit consume from `stream:validation` under different consumer groups. This means every validation event is processed twice (once for the fast gate, once for the audit). This is intentional for the two-tier design but doubles Redis read load.

2. **Learning Loop error swallowing** -- The hourly scan catches all exceptions with a bare `except Exception` and has no logging. Failures in the learning loop are completely invisible.

3. **Check 6 risk_limits parsing fragility** -- The risk limits field is parsed from a potentially stringified JSON blob stored in the profile record. If the structure is unexpected, individual sub-checks silently fall back to permissive defaults (`max_allocation_pct=1.0`, `stop_loss_pct=0.05`).

4. **Check 1 independent RSI uses 5-minute candles** -- The wider-window RSI is computed from 5-minute candles, while the hot RSI is computed from tick data. Comparing these two RSI values at a 25% threshold is a heuristic, not a mathematically equivalent check.

5. **No retry on LPUSH failure** -- If the Redis LPUSH for the BLPOP response key fails, the Hot-Path will timeout waiting for a response and default to fail-open.

6. **Async audit checks run sequentially** -- Checks 2-4 run one after another rather than in parallel, adding unnecessary latency to the audit path.

7. **No backpressure or rate limiting** -- If the fast gate falls behind, the consumer group will accumulate a growing pending entry list with no mechanism to shed load or alert on lag.
