# Execution Service

## Purpose and Responsibility

The Execution Service receives approved trade signals from the Hot-Path Processor, places orders on cryptocurrency exchanges via adapter classes, and manages the full order lifecycle through an optimistic ledger pattern. It owns order persistence, position creation, and periodic balance reconciliation against exchange accounts.

## Public Interface

### `OrderExecutor`

```python
class OrderExecutor:
    def __init__(
        self,
        publisher: StreamPublisher,
        consumer: StreamConsumer,
        order_repo: OrderRepository,
        position_repo: PositionRepository,
        audit_repo: AuditRepository,
        ledger: OptimisticLedger,
        orders_channel: str,
        profile_repo: ProfileRepository = None,
        secret_manager: SecretManager = None,
    )
    async def run(self) -> None
```

### `OptimisticLedger`

```python
class OptimisticLedger:
    def __init__(self, repo: OrderRepository, redis_client=None)
    async def submit(self, order_id: UUID) -> bool
    async def confirm(self, order_id: UUID, fill_price: float,
                      profile_id: str = None, quantity: float = None) -> bool
    async def rollback(self, order_id: UUID, reason: str) -> bool
```

### `BalanceReconciler`

```python
class BalanceReconciler:
    def __init__(self, position_repo: PositionRepository,
                 profile_repo: ProfileRepository = None,
                 pubsub=None, secret_manager: SecretManager = None)
    async def run_cron(self, interval_seconds: int = 300) -> None
```

## Internal Architecture

### Order Execution Pipeline

The executor consumes `OrderApprovedEvent` messages from `stream:orders` in batches of 10 and processes each through a 7-step pipeline:

1. **Resolve Exchange Adapter** -- Loads the user's API credentials from GCP Secret Manager via the profile's `exchange_key_ref`. Derives the exchange name from the key reference convention (`usr-{uid}-{exchange}-keys`) and instantiates the appropriate CCXT adapter.

2. **Create Order Record** -- Writes an `Order` row to TimescaleDB with status `PENDING`.

3. **Optimistic Ledger Submit** -- Transitions the order to `SUBMITTED`. If this fails, the order is skipped and an audit event is written.

4. **Exchange Execution** -- Calls `adapter.place_order()` to submit the order to the exchange. Limit orders are used by default.

5. **Ledger Confirm** -- On success, transitions to `CONFIRMED` and updates the fill price. Also atomically increments the profile's allocation tracking in Redis via a Lua script.

6. **Position Creation** -- Creates a `Position` record with calculated entry fees based on exchange-specific taker rates (Binance: 0.10%, Coinbase: 0.60%, fallback: 0.20%).

7. **Event Emission** -- Publishes an `OrderExecutedEvent` back to `stream:orders`.

On any failure during steps 4-6, the ledger rolls back the order to `ROLLED_BACK` status and emits an `OrderRejectedEvent`. If the rollback itself fails, a `CRITICAL` log is emitted flagging manual intervention.

### Optimistic Ledger State Machine

```
PENDING --> SUBMITTED --> CONFIRMED
                |
                +--> ROLLED_BACK
```

The ledger uses the `OrderRepository` for state transitions and an embedded Lua script for atomic allocation tracking in Redis. The Lua script increments `risk:allocation:{profile_id}` with a 24-hour TTL.

### Balance Reconciliation

`BalanceReconciler` runs on a 5-minute cron cycle and compares exchange balances against the database position ledger for every active profile:

1. Fetches API credentials from Secret Manager for each profile.
2. Calls `adapter.get_balance()` to retrieve exchange-side balances.
3. Aggregates open positions from the DB by base currency.
4. Calculates drift as `|exchange_qty - db_qty| / |db_qty|` per currency.
5. If any currency drifts beyond 0.1%, logs a `CRITICAL` reconciliation error and publishes an `AlertEvent` (level `RED`) to `pubsub:system_alerts`.

### Consumer Group

The executor uses consumer group `executor_group` with consumer ID `executor_1`. All messages in a batch are acknowledged together after processing.

## Dependencies

### Upstream (consumes from)

| Source | Channel | Event Type |
|--------|---------|------------|
| Hot-Path Processor | `stream:orders` | `OrderApprovedEvent` |

### Downstream (publishes to)

| Target | Channel | Event Type |
|--------|---------|------------|
| Platform (various) | `stream:orders` | `OrderExecutedEvent`, `OrderRejectedEvent` |
| Alerting | PubSub `pubsub:system_alerts` | `AlertEvent` (reconciliation drift) |

### Infrastructure Dependencies

- **TimescaleDB** -- Orders table, positions table, audit events
- **Redis** -- Stream consumption, allocation tracking (`risk:allocation:{profile_id}`)
- **GCP Secret Manager** -- Exchange API key retrieval
- **CCXT Pro** -- Exchange communication via `BinanceAdapter` / `CoinbaseAdapter`

### Library Dependencies

- `libs.exchange` -- `get_adapter()` factory
- `libs.storage` -- `OrderRepository`, `PositionRepository`, `AuditRepository`
- `libs.messaging` -- `StreamConsumer`, `StreamPublisher`
- `libs.core.secrets` -- `SecretManager`
- `libs.config` -- `settings.DATABASE_URL`, `settings.REDIS_URL`, `settings.GCP_PROJECT_ID`, `settings.BINANCE_TESTNET`, `settings.COINBASE_SANDBOX`

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Ledger submit fails | Order skipped, audit event written with `SUBMIT_FAILED` |
| Exchange returns unexpected status | Exception caught, ledger rolled back, `OrderRejectedEvent` emitted |
| Ledger confirm fails after exchange success | Rollback attempted; if rollback also fails, `CRITICAL` log for manual intervention |
| Ledger rollback fails | `CRITICAL` log emitted -- this is the worst-case scenario requiring human intervention |
| Secret Manager key not found | Falls back to testnet credentials with a warning |
| Profile load failure | Falls back to default Binance testnet adapter |
| Reconciliation drift > 0.1% | `CRITICAL` log, `AlertEvent` published to system alerts |
| Adapter cleanup | `adapter.close()` called in `finally` block; exceptions swallowed |

## Configuration

| Setting | Source | Default | Description |
|---------|--------|---------|-------------|
| `DATABASE_URL` | `libs.config.settings` | -- | TimescaleDB connection string |
| `REDIS_URL` | `libs.config.settings` | -- | Redis connection string |
| `GCP_PROJECT_ID` | `libs.config.settings` | -- | GCP project for Secret Manager |
| `BINANCE_TESTNET` | `libs.config.settings` | -- | Whether to use Binance sandbox mode |
| `COINBASE_SANDBOX` | `libs.config.settings` | -- | Whether to use Coinbase sandbox mode |
| Reconciliation interval | Hardcoded | `300s` (5 min) | Cron interval for balance checks |
| Reconciliation drift threshold | Hardcoded | `0.001` (0.1%) | Alert threshold for balance drift |
| Consumer batch size | Hardcoded | `10` | Max orders consumed per loop iteration |
| Allocation TTL | Hardcoded (Lua) | `86400s` (24h) | Redis TTL for allocation tracking keys |

### Exchange Fee Rates

| Exchange | Taker Fee Rate |
|----------|---------------|
| Binance | 0.10% |
| Coinbase | 0.60% |
| Fallback | 0.20% |

## Known Issues and Technical Debt

1. **One adapter per order** -- A new CCXT adapter instance is created and closed for every order. This adds latency from credential resolution and connection setup. A connection pool or cached adapter per profile would be more efficient.

2. **Single consumer instance** -- Consumer ID `executor_1` is hardcoded, preventing horizontal scaling without code changes.

3. **No idempotency guard** -- If the same `OrderApprovedEvent` is delivered twice (consumer re-delivery), a duplicate order will be created. There is no deduplication on `event_id`.

4. **Reconciler requires profile_repo** -- If `profile_repo` is not injected (as in the `main.py` lifespan), reconciliation silently skips with a warning. The `main.py` does not currently inject `profile_repo` into `BalanceReconciler`.

5. **Hardcoded fee rates** -- Exchange fee rates are hardcoded constants. They should be loaded from configuration or queried from the exchange, as rates vary by tier.

6. **Allocation Lua script assumes JSON structure** -- The Redis allocation tracking Lua script uses `cjson.decode`/`cjson.encode`. If the key contains corrupt data, the script will fail silently.

7. **No circuit breaker on exchange calls** -- If the exchange API is down, every order will fail and roll back individually. A circuit breaker pattern on the adapter would prevent repeated failures.

8. **datetime.utcnow() usage** -- Several timestamps use the deprecated `datetime.utcnow()` instead of `datetime.now(timezone.utc)`, which can cause timezone-related bugs.
