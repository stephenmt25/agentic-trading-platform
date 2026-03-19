# PnL Service

## Purpose and Responsibility

The PnL Service computes real-time profit-and-loss for all open positions in the Aion Trading Platform. It subscribes to live price ticks via Pub/Sub, calculates gross PnL, fees, tax estimates, and net returns for each position, and publishes updates through three channels: Pub/Sub for the dashboard, Redis for instant cache reads, and TimescaleDB for historical snapshots. It also maintains daily PnL totals and drawdown metrics in Redis for the risk management pipeline.

## Public Interface

### `PnLCalculator`

```python
@dataclass
class PnLSnapshot:
    position_id: str
    symbol: str
    gross_pnl: float
    fees: float
    net_pre_tax: float
    net_post_tax: float
    pct_return: float
    tax_estimate: float

class PnLCalculator:
    @staticmethod
    def calculate(position: Position, current_price: float,
                  taker_rate: float, tax_result: Optional[TaxEstimate] = None) -> PnLSnapshot
```

### `PnLPublisher`

```python
class PnLPublisher:
    def __init__(self, redis_client: RedisClient, pubsub: PubSubBroadcaster,
                 pnl_repo: PnlRepository)
    async def publish_update(self, profile_id: str, snapshot: PnLSnapshot) -> None
```

## Internal Architecture

### Tick Processing Loop

The service runs a single background task that subscribes to `pubsub:price_ticks` and processes each tick:

1. Looks up open positions for the tick's symbol in an in-memory cache (`active_positions_cache`).
2. For each matching position, computes the holding duration in days.
3. Calculates preliminary gross PnL for tax estimation purposes.
4. Calls `USTaxCalculator.calculate()` with the holding period and estimated gains.
5. Determines the exchange-specific taker fee rate (Binance: 0.10%, Coinbase: 0.60%, fallback: 0.20%).
6. Calls `PnLCalculator.calculate()` to produce a full `PnLSnapshot`.
7. Passes the snapshot to `PnLPublisher.publish_update()`.

### PnL Calculation

`PnLCalculator.calculate()` performs the following computation:

```
gross_pnl   = (current_price - entry_price) * quantity    [BUY]
              (entry_price - current_price) * quantity    [SHORT]

exit_fee    = current_price * quantity * taker_rate
total_fees  = entry_fee + exit_fee

net_pre_tax  = gross_pnl - total_fees
net_post_tax = net_pre_tax - tax_estimate
cost_basis   = entry_price * quantity
pct_return   = net_post_tax / cost_basis
```

### Publishing Pipeline

`PnLPublisher.publish_update()` writes to five destinations per update:

1. **Pub/Sub broadcast** -- Publishes a `PnlUpdateEvent` to `pubsub:pnl_updates` for real-time dashboard consumption.

2. **Redis latest cache** -- Writes the latest PnL snapshot as JSON to `pnl:{profile_id}:{position_id}:latest` so the dashboard can load current values instantly without waiting for a Pub/Sub message.

3. **Daily PnL accumulator** (Sprint 10.1) -- Maintains a running daily PnL total at `pnl:daily:{profile_id}` with a TTL that expires at midnight UTC. This value is consumed by the circuit breaker in the Hot-Path.

4. **Drawdown tracker** (Sprint 10.3) -- Tracks the maximum drawdown for the day at `risk:drawdown:{profile_id}` with a 24-hour TTL. Records the worst observed negative return.

5. **TimescaleDB periodic snapshot** -- Writes to `pnl_snapshots` only when the percentage return changes by more than 0.5% from the last persisted value. This throttles database writes for high-frequency tick updates.

### Position Cache

Open positions are loaded from TimescaleDB into `active_positions_cache` at startup via `hydrate_positions()`. The cache is a module-level dictionary keyed by symbol, mapping to lists of `Position` objects. The cache is not refreshed after startup -- new positions opened during runtime are not visible to the PnL service until it restarts.

### Startup Sequence

1. Initialise Redis and TimescaleDB connections.
2. Create `PubSubBroadcaster`, `PositionRepository`, `PnlRepository`, and `PnLPublisher`.
3. Hydrate the position cache from the database.
4. Start the Pub/Sub listener task.

## Dependencies

### Upstream (consumes from)

| Source | Channel | Event Type |
|--------|---------|------------|
| Market Data / Pricing | PubSub `pubsub:price_ticks` | Price tick dict |

### Downstream (publishes to)

| Target | Channel | Format |
|--------|---------|--------|
| Dashboard | PubSub `pubsub:pnl_updates` | `PnlUpdateEvent` |
| Dashboard cache | Redis key `pnl:{profile_id}:{position_id}:latest` | JSON |
| Hot-Path circuit breaker | Redis key `pnl:daily:{profile_id}` | JSON |
| Hot-Path risk gate | Redis key `risk:drawdown:{profile_id}` | JSON |
| Historical storage | TimescaleDB `pnl_snapshots` table | Row insert |

### Infrastructure Dependencies

- **Redis** -- Pub/Sub subscription, cache writes, daily PnL/drawdown tracking
- **TimescaleDB** -- Position reads, PnL snapshot writes

### Library Dependencies

- `libs.storage` -- `RedisClient`, `TimescaleClient`, `PositionRepository`, `PnlRepository`
- `libs.messaging` -- `PubSubBroadcaster`
- `libs.messaging.channels` -- `PUBSUB_PRICE_TICKS`, `PUBSUB_PNL_UPDATES`
- `libs.core.schemas` -- `PnlUpdateEvent`
- `libs.core.models` -- `Position`
- `libs.core.enums` -- `SignalDirection`
- `services.tax.src.us_tax` -- `USTaxCalculator`, `TaxEstimate`

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Position cache empty for symbol | Tick silently ignored (no positions to compute) |
| Tax calculator failure | Not handled; exception would crash the tick processor task |
| Redis write failure in publisher | Not handled; exception propagates |
| TimescaleDB write failure | Not handled; exception propagates |
| Daily PnL TTL overflow | Capped at 86400s (24h) via `max(1, min(ttl, 86400))` |

## Configuration

| Setting | Source | Default | Description |
|---------|--------|---------|-------------|
| `REDIS_URL` | `libs.config.settings` | -- | Redis connection string |
| `DATABASE_URL` | `libs.config.settings` | -- | TimescaleDB connection string |
| Snapshot write threshold | Hardcoded | `0.005` (0.5%) | Min pct_return change to trigger DB write |
| Daily PnL key TTL | Computed | Midnight UTC | Expires at next midnight UTC |
| Drawdown key TTL | Hardcoded | `86400s` (24h) | Fixed 24-hour expiry |
| Taker fee rates | Hardcoded dict | See below | Per-exchange fee rates |

### Fee Rates

| Exchange | Rate |
|----------|------|
| Binance | 0.001 (0.10%) |
| Coinbase | 0.006 (0.60%) |
| Fallback | 0.002 (0.20%) |

## Known Issues and Technical Debt

1. **Position cache is never refreshed** -- `active_positions_cache` is populated once at startup and never updated. Positions opened or closed after boot are invisible to the PnL service. A subscription to order execution events or a periodic refresh is needed.

2. **Module-level mutable state** -- `active_positions_cache` is a module-level global dictionary, making it impossible to test the service in isolation and preventing multiple instances from running in the same process.

3. **No error handling in tick processor** -- If any exception occurs during PnL calculation or publishing, the entire tick processor task will crash with no recovery. There are no try/except blocks in the main processing loop.

4. **Daily PnL accumulation is additive per tick** -- The `_update_daily_pnl` method adds `pct_return` to a running total on every tick update, but `pct_return` is the cumulative return of the position, not the incremental change since the last tick. This means the daily total will be grossly inflated.

5. **Drawdown calculation is simplistic** -- The drawdown tracker records `max(0, -pct_return)` which is the negative of the current return, not the true drawdown from peak equity. A proper drawdown calculation requires tracking the peak value.

6. **Tax calculation on every tick** -- `USTaxCalculator.calculate()` is called on every price tick for every position. This is computationally wasteful for a value that changes slowly (only the holding period matters, and PnL changes marginally per tick).

7. **Fee rates duplicated** -- The same fee rate constants appear in both the Execution Service and the PnL Service. They should be centralised in a shared configuration.

8. **PubSub subscription pattern differs from other services** -- The main.py uses `async for channel, tick_data in pubsub.subscribe()` which does not match the `PubSubSubscriber.subscribe(channel, callback)` API defined in the messaging library. This suggests either a different subscriber implementation or a mismatch.
